"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 074
Archivo  : cost_analytics_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral de Cost & Token Analytics.

Escenarios:
1. Costo de pago estándar.
2. Free tier.
3. Caché de entrada.
4. Modelo desconocido.
5. Proveedor desconocido.
6. Cálculo parcial.
7. Análisis desde TelemetryEvent.
8. Consolidación de ProjectCostReport.
9. Serialización.
10. Selección de tarifas por fecha.

La prueba:
- no llama a Gemini;
- no requiere API Key;
- no modifica proyectos existentes;
- utiliza provider_pricing.yaml;
- utiliza una configuración temporal para cálculo parcial.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from cost_analyzer import CostAnalyzer
from cost_models import (
    CostStatus,
    ProjectCostReport,
    StageCostAnalysis,
)
from telemetry_models import TelemetryEvent


TEST_ROOT = (
    Path(__file__).resolve().parents[1]
    / "04_PROYECTOS"
    / "COST_ANALYTICS_SMOKE_TEST"
)


@dataclass
class ScenarioResult:
    """
    Resultado de un escenario individual.
    """

    name: str
    passed: bool

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class CostAnalyticsSmokeTest:
    """
    Ejecuta la validación integral del Sprint 022B.
    """

    TEST_NAME = "CIPS Cost Analytics Smoke Test"

    def __init__(
        self,
    ) -> None:
        self.analyzer = CostAnalyzer()

        self.results: list[
            ScenarioResult
        ] = []

        self.generated_analyses: list[
            StageCostAnalysis
        ] = []

    def run(
        self,
    ) -> bool:
        """
        Ejecuta todos los escenarios.
        """

        self._prepare()

        print(
            self.TEST_NAME
        )

        print(
            "=" * 70
        )

        print(
            "Esta prueba no llama a Gemini "
            "ni requiere credenciales."
        )

        print(
            f"Ruta temporal: {TEST_ROOT}"
        )

        scenarios: list[
            Callable[
                [],
                ScenarioResult,
            ]
        ] = [
            self._scenario_paid_standard,
            self._scenario_free_tier,
            self._scenario_cached_input,
            self._scenario_unknown_model,
            self._scenario_unknown_provider,
            self._scenario_partial_calculation,
            self._scenario_telemetry_event,
            self._scenario_project_report,
            self._scenario_serialization,
            self._scenario_effective_date,
        ]

        for scenario in scenarios:
            result = scenario()

            self.results.append(
                result
            )

            self._print_scenario(
                result
            )

        return self._print_summary()

    # --------------------------------------------------
    # Preparación
    # --------------------------------------------------

    def _prepare(
        self,
    ) -> None:
        """
        Recrea la carpeta temporal.
        """

        shutil.rmtree(
            TEST_ROOT,
            ignore_errors=True,
        )

        TEST_ROOT.mkdir(
            parents=True,
            exist_ok=True,
        )

    # --------------------------------------------------
    # Escenarios
    # --------------------------------------------------

    def _scenario_paid_standard(
        self,
    ) -> ScenarioResult:
        """
        Valida las tarifas pagadas estándar.
        """

        analysis = self.analyzer.analyze_usage(
            project_id="COST_TEST",
            stage="storyboard",
            provider="gemini",
            model="gemini-3.5-flash",
            prompt_tokens=10_000,
            response_tokens=2_000,
            thinking_tokens=500,
            total_tokens=12_500,
            duration_seconds=60,
            billing_tier="paid",
            billing_mode="standard",
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        expected_input = 0.027
        expected_output = 0.0324
        expected_thinking = 0.0081
        expected_total = 0.0675

        if analysis.status != CostStatus.CALCULATED:
            errors.append(
                "El estado esperado era CALCULATED."
            )

        self._assert_close(
            actual=analysis.cost.input_cost,
            expected=expected_input,
            label="input_cost",
            errors=errors,
        )

        self._assert_close(
            actual=analysis.cost.output_cost,
            expected=expected_output,
            label="output_cost",
            errors=errors,
        )

        self._assert_close(
            actual=analysis.cost.thinking_cost,
            expected=expected_thinking,
            label="thinking_cost",
            errors=errors,
        )

        self._assert_close(
            actual=analysis.cost.total_cost,
            expected=expected_total,
            label="total_cost",
            errors=errors,
        )

        return ScenarioResult(
            name="Costo de pago estándar",
            passed=not errors,
            errors=errors,
            metadata={
                "status": (
                    analysis.status.value
                ),
                "input_cost": (
                    analysis.cost.input_cost
                ),
                "output_cost": (
                    analysis.cost.output_cost
                ),
                "thinking_cost": (
                    analysis.cost.thinking_cost
                ),
                "total_cost": (
                    analysis.cost.total_cost
                ),
            },
        )

    def _scenario_free_tier(
        self,
    ) -> ScenarioResult:
        """
        Valida costo cero en free tier.
        """

        analysis = self.analyzer.analyze_usage(
            project_id="COST_TEST",
            stage="seo",
            provider="gemini",
            model="gemini-3.5-flash",
            prompt_tokens=5_000,
            response_tokens=1_000,
            thinking_tokens=200,
            billing_tier="free_tier",
            billing_mode="standard",
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        if analysis.status != CostStatus.FREE_TIER:
            errors.append(
                "El estado esperado era FREE_TIER."
            )

        if analysis.cost.total_cost != 0.0:
            errors.append(
                "El costo total de free tier debía ser 0."
            )

        if not analysis.cost.is_free():
            errors.append(
                "CostBreakdown.is_free() debía ser True."
            )

        return ScenarioResult(
            name="Free tier",
            passed=not errors,
            errors=errors,
            metadata={
                "status": analysis.status.value,
                "total_cost": (
                    analysis.cost.total_cost
                ),
            },
        )

    def _scenario_cached_input(
        self,
    ) -> ScenarioResult:
        """
        Valida descuento de caché de entrada.
        """

        analysis = self.analyzer.analyze_usage(
            project_id="COST_TEST",
            stage="investigacion",
            provider="gemini",
            model="gemini-3.5-flash",
            prompt_tokens=10_000,
            response_tokens=1_000,
            thinking_tokens=0,
            cached_input_tokens=4_000,
            total_tokens=11_000,
            billing_tier="paid",
            billing_mode="standard",
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        expected_billable_input = 6_000
        expected_input_cost = 0.0162
        expected_cached_cost = 0.00108
        expected_output_cost = 0.0162
        expected_total = 0.03348

        if (
            analysis.metadata.get(
                "billable_input_tokens"
            )
            != expected_billable_input
        ):
            errors.append(
                "billable_input_tokens debía ser 6000."
            )

        self._assert_close(
            actual=analysis.cost.input_cost,
            expected=expected_input_cost,
            label="input_cost con caché",
            errors=errors,
        )

        self._assert_close(
            actual=analysis.cost.cached_input_cost,
            expected=expected_cached_cost,
            label="cached_input_cost",
            errors=errors,
        )

        self._assert_close(
            actual=analysis.cost.output_cost,
            expected=expected_output_cost,
            label="output_cost con caché",
            errors=errors,
        )

        self._assert_close(
            actual=analysis.cost.total_cost,
            expected=expected_total,
            label="total_cost con caché",
            errors=errors,
        )

        return ScenarioResult(
            name="Caché de entrada",
            passed=not errors,
            errors=errors,
            metadata={
                "billable_input_tokens": (
                    analysis.metadata.get(
                        "billable_input_tokens"
                    )
                ),
                "input_cost": (
                    analysis.cost.input_cost
                ),
                "cached_input_cost": (
                    analysis.cost.cached_input_cost
                ),
                "total_cost": (
                    analysis.cost.total_cost
                ),
            },
        )

    def _scenario_unknown_model(
        self,
    ) -> ScenarioResult:
        """
        Valida modelo sin precios.
        """

        analysis = self.analyzer.analyze_usage(
            project_id="COST_TEST",
            stage="guion",
            provider="gemini",
            model="gemini-modelo-inexistente",
            prompt_tokens=1_000,
            response_tokens=200,
            billing_tier="paid",
            billing_mode="standard",
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        if (
            analysis.status
            != CostStatus.UNKNOWN_PRICING
        ):
            errors.append(
                "El estado esperado era UNKNOWN_PRICING."
            )

        if analysis.cost.total_cost != 0.0:
            errors.append(
                "Un modelo desconocido debía producir costo 0."
            )

        if not analysis.warnings:
            errors.append(
                "Debía existir una advertencia."
            )

        return ScenarioResult(
            name="Modelo desconocido",
            passed=not errors,
            errors=errors,
            metadata={
                "status": analysis.status.value,
                "total_cost": (
                    analysis.cost.total_cost
                ),
                "warnings": len(
                    analysis.warnings
                ),
            },
        )

    def _scenario_unknown_provider(
        self,
    ) -> ScenarioResult:
        """
        Valida proveedor sin precios.
        """

        analysis = self.analyzer.analyze_usage(
            project_id="COST_TEST",
            stage="publicacion",
            provider="proveedor-inexistente",
            model="modelo-inexistente",
            prompt_tokens=1_000,
            response_tokens=100,
            billing_tier="paid",
            billing_mode="standard",
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        if (
            analysis.status
            != CostStatus.UNKNOWN_PRICING
        ):
            errors.append(
                "El estado esperado era UNKNOWN_PRICING."
            )

        if analysis.cost.total_cost != 0.0:
            errors.append(
                "Un proveedor desconocido debía producir costo 0."
            )

        if not analysis.warnings:
            errors.append(
                "Debía existir una advertencia."
            )

        return ScenarioResult(
            name="Proveedor desconocido",
            passed=not errors,
            errors=errors,
            metadata={
                "status": analysis.status.value,
                "total_cost": (
                    analysis.cost.total_cost
                ),
                "warnings": len(
                    analysis.warnings
                ),
            },
        )

    def _scenario_partial_calculation(
        self,
    ) -> ScenarioResult:
        """
        Valida estado PARTIAL con tarifa faltante.
        """

        config_path = (
            TEST_ROOT
            / "partial_pricing.yaml"
        )

        config = {
            "schema": {
                "version": "test",
                "currency": "USD",
                "token_unit": 1_000_000,
                "last_verified": "2026-07-15",
                "pricing_is_estimate": True,
            },
            "defaults": {
                "provider": "test-provider",
                "model": "test-model",
                "billing_tier": "paid",
                "billing_mode": "standard",
                "rounding_decimal_places": 8,
            },
            "providers": {
                "test-provider": {
                    "enabled": True,
                    "pricing_source": "test",
                    "models": {
                        "test-model": {
                            "enabled": True,
                            "paid": {
                                "standard": {
                                    "input": 1.0
                                }
                            },
                        }
                    },
                }
            },
        }

        config_path.write_text(
            yaml.safe_dump(
                config,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        analyzer = CostAnalyzer(
            config_path=config_path
        )

        analysis = analyzer.analyze_usage(
            project_id="COST_TEST",
            stage="verificacion",
            provider="test-provider",
            model="test-model",
            prompt_tokens=1_000,
            response_tokens=500,
            billing_tier="paid",
            billing_mode="standard",
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        if analysis.status != CostStatus.PARTIAL:
            errors.append(
                "El estado esperado era PARTIAL."
            )

        if analysis.cost.input_cost <= 0:
            errors.append(
                "input_cost debía calcularse."
            )

        if analysis.cost.output_cost != 0.0:
            errors.append(
                "output_cost debía permanecer en 0."
            )

        if not analysis.warnings:
            errors.append(
                "Debía existir advertencia de cálculo parcial."
            )

        return ScenarioResult(
            name="Cálculo parcial",
            passed=not errors,
            errors=errors,
            metadata={
                "status": analysis.status.value,
                "input_cost": (
                    analysis.cost.input_cost
                ),
                "output_cost": (
                    analysis.cost.output_cost
                ),
                "warnings": len(
                    analysis.warnings
                ),
            },
        )

    def _scenario_telemetry_event(
        self,
    ) -> ScenarioResult:
        """
        Valida integración con TelemetryEvent.
        """

        event = TelemetryEvent(
            event_id="COST-EVENT-001",
            timestamp="2026-07-15T20:00:00Z",
            project_id="COST_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="seo",
            success=True,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=30,
            prompt_tokens=3_000,
            response_tokens=800,
            thinking_tokens=200,
            total_tokens=4_000,
            retry_count=1,
            succeeded_after_retry=True,
            metadata={
                "billing_tier": "paid",
                "billing_mode": "standard",
                "cached_input_tokens": 500,
                "tool_cost": 0.01,
            },
        )

        analysis = self.analyzer.analyze_event(
            event
        )

        self.generated_analyses.append(
            analysis
        )

        errors: list[str] = []

        if analysis.project_id != "COST_TEST":
            errors.append(
                "project_id no se propagó."
            )

        if analysis.stage != "seo":
            errors.append(
                "stage no se propagó."
            )

        if (
            analysis.metadata.get(
                "event_id"
            )
            != "COST-EVENT-001"
        ):
            errors.append(
                "event_id no quedó en metadata."
            )

        if analysis.retry_count != 1:
            errors.append(
                "retry_count no se propagó."
            )

        if analysis.cost.tool_cost != 0.01:
            errors.append(
                "tool_cost no se propagó."
            )

        return ScenarioResult(
            name="Análisis desde TelemetryEvent",
            passed=not errors,
            errors=errors,
            metadata={
                "status": analysis.status.value,
                "stage": analysis.stage,
                "retry_count": (
                    analysis.retry_count
                ),
                "tool_cost": (
                    analysis.cost.tool_cost
                ),
                "total_cost": (
                    analysis.cost.total_cost
                ),
            },
        )

    def _scenario_project_report(
        self,
    ) -> ScenarioResult:
        """
        Valida consolidación del reporte.
        """

        report = ProjectCostReport(
            report_id="COST-REPORT-TEST",
            generated_at="2026-07-15T20:10:00Z",
            project_id="COST_TEST",
            status=CostStatus.INVALID,
            analyses=list(
                self.generated_analyses
            ),
        )

        errors: list[str] = []

        if (
            report.analyses_total
            != len(
                self.generated_analyses
            )
        ):
            errors.append(
                "analyses_total es incorrecto."
            )

        if report.total_tokens <= 0:
            errors.append(
                "total_tokens debía ser mayor a 0."
            )

        if report.total_cost <= 0:
            errors.append(
                "total_cost debía ser mayor a 0."
            )

        if (
            report.status
            != CostStatus.UNKNOWN_PRICING
        ):
            errors.append(
                "El peor estado esperado era UNKNOWN_PRICING."
            )

        if "gemini" not in report.providers:
            errors.append(
                "El reporte debía registrar gemini."
            )

        return ScenarioResult(
            name="Consolidación de ProjectCostReport",
            passed=not errors,
            errors=errors,
            metadata={
                "status": report.status.value,
                "analyses_total": (
                    report.analyses_total
                ),
                "total_tokens": (
                    report.total_tokens
                ),
                "total_cost": (
                    report.total_cost
                ),
                "providers": (
                    report.providers
                ),
            },
        )

    def _scenario_serialization(
        self,
    ) -> ScenarioResult:
        """
        Valida serialización completa.
        """

        report = ProjectCostReport(
            report_id="COST-REPORT-SERIALIZATION",
            generated_at="2026-07-15T20:20:00Z",
            project_id="COST_TEST",
            status=CostStatus.INVALID,
            analyses=list(
                self.generated_analyses
            ),
        )

        payload = report.to_dict()

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
        )

        errors: list[str] = []

        if not serialized:
            errors.append(
                "La serialización quedó vacía."
            )

        if (
            payload.get(
                "analyses_total"
            )
            != len(
                self.generated_analyses
            )
        ):
            errors.append(
                "analyses_total serializado es incorrecto."
            )

        if "total_cost" not in payload:
            errors.append(
                "Falta total_cost en el payload."
            )

        if not isinstance(
            payload.get(
                "analyses"
            ),
            list,
        ):
            errors.append(
                "analyses debía ser una lista."
            )

        return ScenarioResult(
            name="Serialización",
            passed=not errors,
            errors=errors,
            metadata={
                "serialized_characters": len(
                    serialized
                ),
                "analyses_total": (
                    payload.get(
                        "analyses_total"
                    )
                ),
                "total_cost": (
                    payload.get(
                        "total_cost"
                    )
                ),
            },
        )

    def _scenario_effective_date(
        self,
    ) -> ScenarioResult:
        """
        Valida selección de tarifas por fecha.
        """

        early = self.analyzer.resolve_pricing(
            provider="anthropic",
            model="claude-sonnet-5",
            billing_tier="paid",
            billing_mode="standard",
            effective_date="2026-07-15",
        )

        late = self.analyzer.resolve_pricing(
            provider="anthropic",
            model="claude-sonnet-5",
            billing_tier="paid",
            billing_mode="standard",
            effective_date="2026-09-15",
        )

        errors: list[str] = []

        if (
            early.get(
                "rates",
                {},
            ).get(
                "input"
            )
            != 2.0
        ):
            errors.append(
                "La tarifa inicial de input debía ser 2.0."
            )

        if (
            early.get(
                "rates",
                {},
            ).get(
                "output"
            )
            != 10.0
        ):
            errors.append(
                "La tarifa inicial de output debía ser 10.0."
            )

        if (
            late.get(
                "rates",
                {},
            ).get(
                "input"
            )
            != 3.0
        ):
            errors.append(
                "La tarifa posterior de input debía ser 3.0."
            )

        if (
            late.get(
                "rates",
                {},
            ).get(
                "output"
            )
            != 15.0
        ):
            errors.append(
                "La tarifa posterior de output debía ser 15.0."
            )

        return ScenarioResult(
            name="Selección de tarifas por fecha",
            passed=not errors,
            errors=errors,
            metadata={
                "early_status": (
                    early.get(
                        "status"
                    ).value
                ),
                "early_input": (
                    early.get(
                        "rates",
                        {},
                    ).get(
                        "input"
                    )
                ),
                "early_output": (
                    early.get(
                        "rates",
                        {},
                    ).get(
                        "output"
                    )
                ),
                "late_status": (
                    late.get(
                        "status"
                    ).value
                ),
                "late_input": (
                    late.get(
                        "rates",
                        {},
                    ).get(
                        "input"
                    )
                ),
                "late_output": (
                    late.get(
                        "rates",
                        {},
                    ).get(
                        "output"
                    )
                ),
            },
        )

    # --------------------------------------------------
    # Utilidades
    # --------------------------------------------------

    def _assert_close(
        self,
        *,
        actual: float,
        expected: float,
        label: str,
        errors: list[str],
        tolerance: float = 0.00000001,
    ) -> None:
        """
        Compara flotantes con tolerancia.
        """

        if abs(
            actual
            - expected
        ) > tolerance:
            errors.append(
                (
                    f"{label}: esperado {expected}, "
                    f"actual {actual}."
                )
            )

    # --------------------------------------------------
    # Impresión
    # --------------------------------------------------

    def _print_scenario(
        self,
        result: ScenarioResult,
    ) -> None:
        """
        Imprime un escenario.
        """

        print()

        print(
            "-" * 70
        )

        print(
            f"Escenario: {result.name}"
        )

        print(
            "-" * 70
        )

        print(
            "Resultado: "
            + (
                "OK"
                if result.passed
                else "ERROR"
            )
        )

        if result.metadata:
            print(
                "Datos:"
            )

            for key, value in (
                result.metadata.items()
            ):
                if isinstance(
                    value,
                    (
                        list,
                        dict,
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
            print(
                "Errores:"
            )

            for error in result.errors:
                print(
                    f"- {error}"
                )

    def _print_summary(
        self,
    ) -> bool:
        """
        Imprime el resumen final.
        """

        passed = sum(
            1
            for result in self.results
            if result.passed
        )

        failed = (
            len(
                self.results
            )
            - passed
        )

        overall_valid = (
            failed == 0
        )

        print()

        print(
            "=" * 70
        )

        print(
            "RESUMEN COST ANALYTICS"
        )

        print(
            "=" * 70
        )

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

        print(
            f"- {TEST_ROOT}"
        )

        if overall_valid:
            print()

            print(
                "Cost Analytics Smoke Test "
                "completado correctamente."
            )

        return overall_valid


def main(
) -> int:
    """
    Punto de entrada.
    """

    test = CostAnalyticsSmokeTest()

    return (
        0
        if test.run()
        else 1
    )


if __name__ == "__main__":
    sys.exit(
        main()
    )