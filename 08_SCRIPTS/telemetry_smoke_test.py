"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 063
Archivo  : telemetry_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Telemetry Framework.

Escenarios:
- registro exitoso;
- fallo con Retry agotado;
- filtros;
- resumen;
- persistencia JSONL;
- tolerancia a línea dañada;
- carga del resumen.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from telemetry_engine import TelemetryEngine
from telemetry_models import (
    TelemetryAttempt,
    TelemetryEvent,
    TelemetrySummary,
)


TEST_ROOT = (
    Path(__file__).resolve().parents[1]
    / "04_PROYECTOS"
    / "TELEMETRY_SMOKE_TEST"
)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class TelemetrySmokeTest:
    TEST_NAME = "CIPS Telemetry Smoke Test"

    def __init__(self) -> None:
        self.engine = TelemetryEngine()
        self.results: list[ScenarioResult] = []

    def run(self) -> bool:
        self._prepare()

        print(self.TEST_NAME)
        print("=" * 70)
        print("Esta prueba no llama a Gemini ni requiere credenciales.")
        print(f"Proyecto temporal: {TEST_ROOT.name}")
        print(f"Ruta: {TEST_ROOT}")

        scenarios: list[Callable[[], ScenarioResult]] = [
            self._success_event,
            self._retry_failure_event,
            self._query_filters,
            self._summary_rebuild,
            self._jsonl_persistence,
            self._invalid_line_tolerance,
            self._summary_load,
        ]

        for scenario in scenarios:
            result = scenario()
            self.results.append(result)
            self._print_scenario(result)

        return self._print_summary()

    def _prepare(self) -> None:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True, exist_ok=True)

    def _success_event(self) -> ScenarioResult:
        event = TelemetryEvent(
            event_id="",
            timestamp="",
            project_id="PROYECTO_TELEMETRY_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="investigacion",
            event_type="stage_execution",
            success=True,
            message="Stage investigacion validado.",
            provider="gemini",
            model="gemini-3.5-flash",
            thinking_level="low",
            duration_seconds=12.5,
            prompt_characters=42000,
            response_characters=4500,
            prompt_tokens=10000,
            response_tokens=1000,
            thinking_tokens=500,
            total_tokens=11500,
            retry_enabled=True,
            retry_attempts=1,
            retry_count=0,
            validation_score=100,
            validation_passing_score=70,
            validation_approved=True,
        )

        result = self.engine.execute(
            event=event,
            project_path=TEST_ROOT,
        )

        errors: list[str] = []

        if not result.success:
            errors.append("El evento exitoso no pudo registrarse.")
        if not event.event_id:
            errors.append("No se generó event_id.")
        if not event.timestamp:
            errors.append("No se generó timestamp.")
        if not result.metadata.get("summary_updated", False):
            errors.append("El resumen no fue actualizado.")

        return ScenarioResult(
            name="Registro de evento exitoso",
            passed=not errors,
            errors=errors,
            metadata={
                "event_id": event.event_id,
                "timestamp": event.timestamp,
            },
        )

    def _retry_failure_event(self) -> ScenarioResult:
        attempts = [
            TelemetryAttempt(
                attempt_number=1,
                success=False,
                duration_seconds=10.0,
                delay_seconds=5.0,
                retryable=True,
                status_code=503,
                exception_type="ServerError",
                matched_rule="retryable_status_code",
                message="503 UNAVAILABLE",
            ),
            TelemetryAttempt(
                attempt_number=2,
                success=False,
                duration_seconds=2.0,
                delay_seconds=10.0,
                retryable=True,
                status_code=503,
                exception_type="ServerError",
                matched_rule="retryable_status_code",
                message="503 UNAVAILABLE",
            ),
            TelemetryAttempt(
                attempt_number=3,
                success=False,
                duration_seconds=1.0,
                delay_seconds=0.0,
                retryable=False,
                status_code=429,
                exception_type="ClientError",
                matched_rule="retryable_status_code",
                message="429 RESOURCE_EXHAUSTED",
            ),
        ]

        event = TelemetryEvent(
            event_id="",
            timestamp="",
            project_id="PROYECTO_TELEMETRY_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="storyboard",
            event_type="stage_execution",
            success=False,
            message="Google Gemini no pudo completar la solicitud.",
            provider="gemini",
            model="gemini-3.5-flash",
            thinking_level="low",
            duration_seconds=28.0,
            prompt_characters=26779,
            retry_enabled=True,
            retry_attempts=3,
            retry_count=2,
            retry_exhausted=True,
            status_code=429,
            exception_type="ClientError",
            attempts=attempts,
            errors=["429 RESOURCE_EXHAUSTED"],
        )

        result = self.engine.execute(
            event=event,
            project_path=TEST_ROOT,
        )

        errors: list[str] = []

        if not result.success:
            errors.append("El evento fallido no pudo registrarse.")
        if len(event.attempts) != 3:
            errors.append("Debían conservarse 3 intentos.")
        if event.retry_count != 2:
            errors.append("retry_count debía ser 2.")
        if not event.retry_exhausted:
            errors.append("retry_exhausted debía ser True.")

        return ScenarioResult(
            name="Registro de fallo con Retry agotado",
            passed=not errors,
            errors=errors,
            metadata={
                "attempts": len(event.attempts),
                "retry_count": event.retry_count,
                "status_code": event.status_code,
            },
        )

    def _query_filters(self) -> ScenarioResult:
        all_result = self.engine.read_events(project_path=TEST_ROOT)
        failed_result = self.engine.read_events(
            project_path=TEST_ROOT,
            success=False,
        )
        storyboard_result = self.engine.read_events(
            project_path=TEST_ROOT,
            stage="storyboard",
        )

        errors: list[str] = []

        if not all_result.success or len(all_result.data) != 2:
            errors.append("Se esperaban exactamente 2 eventos.")
        if not failed_result.success or len(failed_result.data) != 1:
            errors.append("El filtro de fallos debía devolver 1 evento.")
        if not storyboard_result.success or len(storyboard_result.data) != 1:
            errors.append("El filtro storyboard debía devolver 1 evento.")

        return ScenarioResult(
            name="Consulta y filtrado",
            passed=not errors,
            errors=errors,
            metadata={
                "events_total": len(all_result.data) if all_result.success else 0,
                "failed_events": len(failed_result.data) if failed_result.success else 0,
                "storyboard_events": (
                    len(storyboard_result.data)
                    if storyboard_result.success
                    else 0
                ),
            },
        )

    def _summary_rebuild(self) -> ScenarioResult:
        result = self.engine.rebuild_summary(
            project_path=TEST_ROOT,
            scope="project",
            scope_id="PROYECTO_TELEMETRY_TEST",
        )

        errors: list[str] = []

        if not result.success:
            errors.append("No fue posible reconstruir el resumen.")
            return ScenarioResult(
                name="Reconstrucción de resumen",
                passed=False,
                errors=errors,
            )

        summary = result.data

        expected = {
            "events_total": 2,
            "successful_events": 1,
            "failed_events": 1,
            "success_rate": 50.0,
            "retry_attempts": 4,
            "retry_count": 2,
            "exhausted_events": 1,
            "recovered_events": 0,
            "total_tokens": 11500,
        }

        for field_name, expected_value in expected.items():
            actual = getattr(summary, field_name, None)
            if actual != expected_value:
                errors.append(
                    f"{field_name}: esperado {expected_value}, actual {actual}."
                )

        if summary.status_codes.get("429") != 1:
            errors.append("El resumen debía registrar un código 429.")
        if summary.exception_types.get("ClientError") != 1:
            errors.append("El resumen debía registrar ClientError una vez.")

        return ScenarioResult(
            name="Reconstrucción de resumen",
            passed=not errors,
            errors=errors,
            metadata=summary.to_dict(),
        )

    def _jsonl_persistence(self) -> ScenarioResult:
        telemetry_dir = TEST_ROOT / self.engine.DEFAULT_DIRECTORY
        events_path = telemetry_dir / self.engine.EVENTS_FILENAME

        errors: list[str] = []
        payloads: list[dict[str, Any]] = []

        if not events_path.exists():
            errors.append("TELEMETRY.jsonl no existe.")
        else:
            lines = [
                line
                for line in events_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]

            if len(lines) != 2:
                errors.append("TELEMETRY.jsonl debía contener 2 líneas.")

            for index, line in enumerate(lines, start=1):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    errors.append(
                        f"Línea {index} inválida: {error.msg}."
                    )
                    continue

                if not isinstance(payload, dict):
                    errors.append(f"Línea {index} no es objeto JSON.")
                    continue

                payloads.append(payload)

        return ScenarioResult(
            name="Persistencia JSONL",
            passed=not errors,
            errors=errors,
            metadata={
                "events_path": str(events_path),
                "valid_payloads": len(payloads),
                "size_bytes": (
                    events_path.stat().st_size
                    if events_path.exists()
                    else 0
                ),
            },
        )

    def _invalid_line_tolerance(self) -> ScenarioResult:
        telemetry_dir = TEST_ROOT / self.engine.DEFAULT_DIRECTORY
        events_path = telemetry_dir / self.engine.EVENTS_FILENAME

        with events_path.open(
            mode="a",
            encoding="utf-8",
            newline="\n",
        ) as file:
            file.write("{invalid-json\n")

        result = self.engine.read_events(project_path=TEST_ROOT)

        errors: list[str] = []

        if not result.success:
            errors.append("La consulta no debía fallar.")
        elif len(result.data) != 2:
            errors.append("Debían conservarse los 2 eventos válidos.")
        if not result.warnings:
            errors.append("Debía generarse una advertencia.")

        return ScenarioResult(
            name="Tolerancia a línea dañada",
            passed=not errors,
            errors=errors,
            metadata={
                "events_returned": len(result.data) if result.success else 0,
                "warnings": list(result.warnings),
            },
        )

    def _summary_load(self) -> ScenarioResult:
        result = self.engine.load_summary(project_path=TEST_ROOT)

        errors: list[str] = []

        if not result.success:
            errors.append("No fue posible cargar el resumen.")
        elif not isinstance(result.data, TelemetrySummary):
            errors.append("El resumen no es TelemetrySummary.")
        elif result.data.events_total != 2:
            errors.append("El resumen debía contener 2 eventos.")

        return ScenarioResult(
            name="Carga del resumen",
            passed=not errors,
            errors=errors,
            metadata={
                "summary_path": (
                    result.metadata.get("summary_path")
                    if result.success
                    else ""
                ),
                "events_total": (
                    result.data.events_total
                    if result.success
                    else 0
                ),
            },
        )

    def _print_scenario(self, result: ScenarioResult) -> None:
        print()
        print("-" * 70)
        print(f"Escenario: {result.name}")
        print("-" * 70)
        print(f"Resultado: {'OK' if result.passed else 'ERROR'}")

        if result.metadata:
            print("Datos:")
            for key, value in result.metadata.items():
                if isinstance(value, (dict, list)):
                    print(
                        f"  {key}: "
                        f"{json.dumps(value, ensure_ascii=False)}"
                    )
                else:
                    print(f"  {key}: {value}")

        if result.errors:
            print("Errores:")
            for error in result.errors:
                print(f"- {error}")

    def _print_summary(self) -> bool:
        passed = sum(
            1
            for result in self.results
            if result.passed
        )
        failed = len(self.results) - passed
        overall_valid = failed == 0

        print()
        print("=" * 70)
        print("RESUMEN TELEMETRY")
        print("=" * 70)
        print(f"Escenarios ejecutados: {len(self.results)}")
        print(f"Escenarios aprobados: {passed}")
        print(f"Escenarios fallidos: {failed}")
        print(f"Resultado integral válido: {overall_valid}")
        print()
        print("Artefactos conservados para inspección manual:")
        print(f"- {TEST_ROOT}")

        if overall_valid:
            print()
            print("Telemetry Smoke Test completado correctamente.")

        return overall_valid


def main() -> int:
    test = TelemetrySmokeTest()
    return 0 if test.run() else 1


if __name__ == "__main__":
    sys.exit(main())