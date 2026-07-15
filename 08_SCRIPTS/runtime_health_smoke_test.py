"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 067
Archivo  : runtime_health_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral del Runtime Health Monitor.

Escenarios:
1. Estado UNKNOWN sin telemetría.
2. Estado HEALTHY.
3. Estado DEGRADED.
4. Estado UNHEALTHY.
5. Persistencia JSON y Markdown.
6. Carga del reporte persistido.
7. Ranking de componentes.
8. Detección de Retry y códigos HTTP.

La prueba:
- no llama a Gemini;
- no requiere API Key;
- no modifica proyectos existentes;
- utiliza carpetas temporales propias.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from health_models import HealthStatus, RuntimeHealthReport
from runtime_health_monitor import RuntimeHealthMonitor
from telemetry_engine import TelemetryEngine
from telemetry_models import TelemetryAttempt, TelemetryEvent


TEST_ROOT = (
    Path(__file__).resolve().parents[1]
    / "04_PROYECTOS"
    / "RUNTIME_HEALTH_SMOKE_TEST"
)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeHealthSmokeTest:
    """
    Ejecuta la validación integral del Runtime Health Monitor.
    """

    TEST_NAME = "CIPS Runtime Health Smoke Test"

    def __init__(self) -> None:
        self.telemetry_engine = TelemetryEngine()
        self.monitor = RuntimeHealthMonitor(
            telemetry_engine=self.telemetry_engine
        )
        self.results: list[ScenarioResult] = []

    def run(self) -> bool:
        self._prepare()

        print(self.TEST_NAME)
        print("=" * 70)
        print("Esta prueba no llama a Gemini ni requiere credenciales.")
        print(f"Ruta temporal: {TEST_ROOT}")

        scenarios: list[Callable[[], ScenarioResult]] = [
            self._scenario_unknown,
            self._scenario_healthy,
            self._scenario_degraded,
            self._scenario_unhealthy,
            self._scenario_persistence,
            self._scenario_load_report,
            self._scenario_component_ranking,
            self._scenario_retry_http_detection,
        ]

        for scenario in scenarios:
            result = scenario()
            self.results.append(result)
            self._print_scenario(result)

        return self._print_summary()

    def _prepare(self) -> None:
        shutil.rmtree(
            TEST_ROOT,
            ignore_errors=True,
        )
        TEST_ROOT.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _project_path(self, name: str) -> Path:
        path = TEST_ROOT / name
        path.mkdir(
            parents=True,
            exist_ok=True,
        )
        return path

    def _record(
        self,
        project_path: Path,
        event: TelemetryEvent,
    ) -> None:
        result = self.telemetry_engine.execute(
            event=event,
            project_path=project_path,
        )

        if not result.success:
            raise RuntimeError(
                result.message
            )

    def _scenario_unknown(self) -> ScenarioResult:
        project_path = self._project_path(
            "UNKNOWN_PROJECT"
        )

        result = self.monitor.execute(
            project_path=project_path,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "El monitor no debía fallar sin telemetría."
            )
        elif result.data.status != HealthStatus.UNKNOWN:
            errors.append(
                "El estado esperado era UNKNOWN."
            )
        elif result.data.events_total != 0:
            errors.append(
                "events_total debía ser 0."
            )

        return ScenarioResult(
            name="Estado UNKNOWN sin telemetría",
            passed=not errors,
            errors=errors,
            metadata={
                "status": (
                    result.data.status.value
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

    def _scenario_healthy(self) -> ScenarioResult:
        project_path = self._project_path(
            "HEALTHY_PROJECT"
        )

        for index in range(3):
            self._record(
                project_path,
                TelemetryEvent(
                    event_id="",
                    timestamp="",
                    project_id="HEALTHY_PROJECT",
                    component="pipeline_engine",
                    operation="execute_stage",
                    stage="investigacion",
                    success=True,
                    provider="gemini",
                    model="gemini-3.5-flash",
                    duration_seconds=20 + index,
                    prompt_tokens=100,
                    response_tokens=20,
                    total_tokens=120,
                    retry_enabled=True,
                    retry_attempts=1,
                    retry_count=0,
                ),
            )

        result = self.monitor.execute(
            project_path=project_path,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "El monitor falló en escenario HEALTHY."
            )
        elif result.data.status != HealthStatus.HEALTHY:
            errors.append(
                "El estado esperado era HEALTHY."
            )
        elif result.data.success_rate != 100.0:
            errors.append(
                "success_rate debía ser 100.0."
            )

        return ScenarioResult(
            name="Estado HEALTHY",
            passed=not errors,
            errors=errors,
            metadata={
                "status": (
                    result.data.status.value
                    if result.success
                    else ""
                ),
                "success_rate": (
                    result.data.success_rate
                    if result.success
                    else 0.0
                ),
            },
        )

    def _scenario_degraded(self) -> ScenarioResult:
        project_path = self._project_path(
            "DEGRADED_PROJECT"
        )

        events = [
            TelemetryEvent(
                event_id="",
                timestamp="",
                project_id="DEGRADED_PROJECT",
                component="pipeline_engine",
                operation="execute_stage",
                stage="investigacion",
                success=True,
                provider="gemini",
                model="gemini-3.5-flash",
                duration_seconds=70,
                retry_enabled=True,
                retry_attempts=2,
                retry_count=1,
                succeeded_after_retry=True,
            ),
            TelemetryEvent(
                event_id="",
                timestamp="",
                project_id="DEGRADED_PROJECT",
                component="pipeline_engine",
                operation="execute_stage",
                stage="investigacion",
                success=True,
                provider="gemini",
                model="gemini-3.5-flash",
                duration_seconds=65,
                retry_enabled=True,
                retry_attempts=1,
                retry_count=0,
            ),
            TelemetryEvent(
                event_id="",
                timestamp="",
                project_id="DEGRADED_PROJECT",
                component="pipeline_engine",
                operation="execute_stage",
                stage="investigacion",
                success=True,
                provider="gemini",
                model="gemini-3.5-flash",
                duration_seconds=62,
                retry_enabled=True,
                retry_attempts=1,
                retry_count=0,
            ),
        ]

        for event in events:
            self._record(
                project_path,
                event,
            )

        result = self.monitor.execute(
            project_path=project_path,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "El monitor falló en escenario DEGRADED."
            )
        elif result.data.status != HealthStatus.DEGRADED:
            errors.append(
                "El estado esperado era DEGRADED."
            )

        return ScenarioResult(
            name="Estado DEGRADED",
            passed=not errors,
            errors=errors,
            metadata={
                "status": (
                    result.data.status.value
                    if result.success
                    else ""
                ),
                "average_duration_seconds": (
                    result.data.average_duration_seconds
                    if result.success
                    else 0.0
                ),
                "retry_count": (
                    result.data.retry_count
                    if result.success
                    else 0
                ),
            },
        )

    def _scenario_unhealthy(self) -> ScenarioResult:
        project_path = self._project_path(
            "UNHEALTHY_PROJECT"
        )

        attempts = [
            TelemetryAttempt(
                attempt_number=1,
                success=False,
                duration_seconds=5,
                delay_seconds=5,
                retryable=True,
                status_code=503,
                exception_type="ServerError",
                matched_rule="retryable_status_code",
            ),
            TelemetryAttempt(
                attempt_number=2,
                success=False,
                duration_seconds=1,
                delay_seconds=10,
                retryable=True,
                status_code=503,
                exception_type="ServerError",
                matched_rule="retryable_status_code",
            ),
            TelemetryAttempt(
                attempt_number=3,
                success=False,
                duration_seconds=1,
                delay_seconds=0,
                retryable=False,
                status_code=429,
                exception_type="ClientError",
                matched_rule="retryable_status_code",
            ),
        ]

        self._record(
            project_path,
            TelemetryEvent(
                event_id="",
                timestamp="",
                project_id="UNHEALTHY_PROJECT",
                component="pipeline_engine",
                operation="execute_stage",
                stage="storyboard",
                success=False,
                message="429 RESOURCE_EXHAUSTED quota exceeded",
                provider="gemini",
                model="gemini-3.5-flash",
                duration_seconds=120,
                retry_enabled=True,
                retry_attempts=3,
                retry_count=2,
                retry_exhausted=True,
                status_code=429,
                exception_type="ClientError",
                attempts=attempts,
                errors=[
                    "429 RESOURCE_EXHAUSTED quota exceeded"
                ],
            ),
        )

        self._record(
            project_path,
            TelemetryEvent(
                event_id="",
                timestamp="",
                project_id="UNHEALTHY_PROJECT",
                component="pipeline_engine",
                operation="execute_stage",
                stage="investigacion",
                success=True,
                provider="gemini",
                model="gemini-3.5-flash",
                duration_seconds=30,
                retry_enabled=True,
                retry_attempts=1,
                retry_count=0,
            ),
        )

        result = self.monitor.execute(
            project_path=project_path,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "El monitor falló en escenario UNHEALTHY."
            )
        elif result.data.status != HealthStatus.UNHEALTHY:
            errors.append(
                "El estado esperado era UNHEALTHY."
            )
        elif result.data.exhausted_events != 1:
            errors.append(
                "exhausted_events debía ser 1."
            )

        return ScenarioResult(
            name="Estado UNHEALTHY",
            passed=not errors,
            errors=errors,
            metadata={
                "status": (
                    result.data.status.value
                    if result.success
                    else ""
                ),
                "success_rate": (
                    result.data.success_rate
                    if result.success
                    else 0.0
                ),
                "exhausted_events": (
                    result.data.exhausted_events
                    if result.success
                    else 0
                ),
            },
        )

    def _scenario_persistence(self) -> ScenarioResult:
        project_path = self._project_path(
            "UNHEALTHY_PROJECT"
        )

        telemetry_dir = (
            project_path
            / self.telemetry_engine.DEFAULT_DIRECTORY
        )

        json_path = (
            telemetry_dir
            / self.monitor.HEALTH_JSON_FILENAME
        )

        markdown_path = (
            telemetry_dir
            / self.monitor.HEALTH_MARKDOWN_FILENAME
        )

        errors: list[str] = []

        if not json_path.exists():
            errors.append(
                "RUNTIME_HEALTH.json no existe."
            )

        if not markdown_path.exists():
            errors.append(
                "RUNTIME_HEALTH.md no existe."
            )

        if json_path.exists():
            payload = json.loads(
                json_path.read_text(
                    encoding="utf-8"
                )
            )

            if payload.get(
                "status"
            ) != "UNHEALTHY":
                errors.append(
                    "El JSON debía registrar UNHEALTHY."
                )

        if markdown_path.exists():
            markdown = markdown_path.read_text(
                encoding="utf-8"
            )

            if "CIPS Runtime Health Report" not in markdown:
                errors.append(
                    "El Markdown no contiene el encabezado."
                )

            if "UNHEALTHY" not in markdown:
                errors.append(
                    "El Markdown no contiene UNHEALTHY."
                )

        return ScenarioResult(
            name="Persistencia JSON y Markdown",
            passed=not errors,
            errors=errors,
            metadata={
                "json_path": str(
                    json_path
                ),
                "markdown_path": str(
                    markdown_path
                ),
                "json_size_bytes": (
                    json_path.stat().st_size
                    if json_path.exists()
                    else 0
                ),
                "markdown_size_bytes": (
                    markdown_path.stat().st_size
                    if markdown_path.exists()
                    else 0
                ),
            },
        )

    def _scenario_load_report(self) -> ScenarioResult:
        project_path = self._project_path(
            "UNHEALTHY_PROJECT"
        )

        result = self.monitor.load_report(
            project_path=project_path,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "No fue posible cargar el reporte."
            )
        elif not isinstance(
            result.data,
            RuntimeHealthReport,
        ):
            errors.append(
                "El reporte cargado no es RuntimeHealthReport."
            )
        elif result.data.status != HealthStatus.UNHEALTHY:
            errors.append(
                "El reporte cargado debía ser UNHEALTHY."
            )

        return ScenarioResult(
            name="Carga del reporte persistido",
            passed=not errors,
            errors=errors,
            metadata={
                "status": (
                    result.data.status.value
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

    def _scenario_component_ranking(self) -> ScenarioResult:
        project_path = self._project_path(
            "UNHEALTHY_PROJECT"
        )

        result = self.monitor.load_report(
            project_path=project_path,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "No fue posible cargar el reporte."
            )

            return ScenarioResult(
                name="Ranking de componentes",
                passed=False,
                errors=errors,
            )

        components = sorted(
            result.data.components,
            key=self.monitor._component_sort_key,
        )

        if not components:
            errors.append(
                "No existen componentes analizados."
            )
        elif (
            components[0].status
            != HealthStatus.UNHEALTHY
        ):
            errors.append(
                "El primer componente debía ser UNHEALTHY."
            )

        return ScenarioResult(
            name="Ranking de componentes",
            passed=not errors,
            errors=errors,
            metadata={
                "components_count": len(
                    components
                ),
                "first_component": (
                    components[0].component
                    if components
                    else ""
                ),
                "first_status": (
                    components[0].status.value
                    if components
                    else ""
                ),
            },
        )

    def _scenario_retry_http_detection(self) -> ScenarioResult:
        project_path = self._project_path(
            "UNHEALTHY_PROJECT"
        )

        result = self.monitor.load_report(
            project_path=project_path,
        )

        errors: list[str] = []

        if not result.success:
            errors.append(
                "No fue posible cargar el reporte."
            )

            return ScenarioResult(
                name="Detección de Retry y HTTP",
                passed=False,
                errors=errors,
            )

        indicator_ids = {
            indicator.indicator_id
            for indicator in result.data.indicators
        }

        if "retry_exhaustion_rate" not in indicator_ids:
            errors.append(
                "Falta retry_exhaustion_rate."
            )

        if "http_errors" not in indicator_ids:
            errors.append(
                "Falta http_errors."
            )

        if "quota_pressure" not in indicator_ids:
            errors.append(
                "Falta quota_pressure."
            )

        if result.data.retry_count != 2:
            errors.append(
                "retry_count debía ser 2."
            )

        return ScenarioResult(
            name="Detección de Retry y HTTP",
            passed=not errors,
            errors=errors,
            metadata={
                "retry_count": (
                    result.data.retry_count
                ),
                "indicators": sorted(
                    indicator_ids
                ),
            },
        )

    def _print_scenario(
        self,
        result: ScenarioResult,
    ) -> None:
        print()
        print("-" * 70)
        print(f"Escenario: {result.name}")
        print("-" * 70)
        print(
            f"Resultado: "
            f"{'OK' if result.passed else 'ERROR'}"
        )

        if result.metadata:
            print("Datos:")

            for key, value in result.metadata.items():
                if isinstance(
                    value,
                    (
                        dict,
                        list,
                    ),
                ):
                    print(
                        f"  {key}: "
                        f"{json.dumps(value, ensure_ascii=False)}"
                    )
                else:
                    print(
                        f"  {key}: {value}"
                    )

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

        failed = len(
            self.results
        ) - passed

        overall_valid = (
            failed == 0
        )

        print()
        print("=" * 70)
        print("RESUMEN RUNTIME HEALTH")
        print("=" * 70)
        print(
            f"Escenarios ejecutados: "
            f"{len(self.results)}"
        )
        print(
            f"Escenarios aprobados: "
            f"{passed}"
        )
        print(
            f"Escenarios fallidos: "
            f"{failed}"
        )
        print(
            f"Resultado integral válido: "
            f"{overall_valid}"
        )
        print()
        print(
            "Artefactos conservados para inspección:"
        )
        print(f"- {TEST_ROOT}")

        if overall_valid:
            print()
            print(
                "Runtime Health Smoke Test "
                "completado correctamente."
            )

        return overall_valid


def main() -> int:
    test = RuntimeHealthSmokeTest()
    return 0 if test.run() else 1


if __name__ == "__main__":
    sys.exit(
        main()
    )