"""
CIPS Prompt Intelligence Smoke Test
Release 0.9
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from prompt_intelligence_analyzer import PromptIntelligenceAnalyzer
from prompt_intelligence_models import (
    PromptAnalysis,
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
)
from telemetry_models import TelemetryEvent


TEST_ROOT = (
    Path(__file__).resolve().parents[1]
    / "04_PROYECTOS"
    / "PROMPT_INTELLIGENCE_SMOKE_TEST"
)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptIntelligenceSmokeTest:
    TEST_NAME = "CIPS Prompt Intelligence Smoke Test"

    def __init__(self) -> None:
        self.analyzer = PromptIntelligenceAnalyzer()
        self.results: list[ScenarioResult] = []
        self.analyses: list[PromptAnalysis] = []

    def run(self) -> bool:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
        TEST_ROOT.mkdir(parents=True, exist_ok=True)

        print(self.TEST_NAME)
        print("=" * 70)
        print("Esta prueba no llama a Gemini ni requiere credenciales.")
        print(f"Ruta temporal: {TEST_ROOT}")

        scenarios: list[Callable[[], ScenarioResult]] = [
            self._efficient,
            self._acceptable,
            self._inefficient,
            self._critical,
            self._telemetry_event,
            self._file_paths,
            self._report,
            self._serialization,
        ]

        for scenario in scenarios:
            result = scenario()
            self.results.append(result)
            self._print_result(result)

        return self._print_summary()

    def _efficient(self) -> ScenarioResult:
        analysis = self.analyzer.analyze_prompt(
            prompt_content=(
                "Analiza las pausas activas y entrega "
                "tres conclusiones claras."
            ),
            response_content=(
                "Reducen fatiga, apoyan la concentración "
                "y favorecen la movilidad."
            ),
            project_id="PROMPT_TEST",
            stage="investigacion",
            provider="gemini",
            model="gemini-3.5-flash",
            prompt_tokens=100,
            response_tokens=40,
            thinking_tokens=10,
            total_tokens=150,
            duration_seconds=3,
        )
        self.analyses.append(analysis)

        errors = []
        if analysis.status != PromptEfficiencyStatus.EFFICIENT:
            errors.append("El estado esperado era EFFICIENT.")
        if analysis.efficiency_score < 80:
            errors.append("El score debía ser al menos 80.")

        return ScenarioResult(
            "Prompt eficiente",
            not errors,
            errors,
            {
                "status": analysis.status.value,
                "efficiency_score": analysis.efficiency_score,
            },
        )

    def _acceptable(self) -> ScenarioResult:
        analysis = self.analyzer.analyze_prompt(
            prompt_content=(
                "Contexto académico. Explica pausas activas "
                "con beneficios, recomendaciones y cierre."
            ),
            response_content=(
                "Las pausas activas reducen fatiga y pueden "
                "mejorar la atención."
            ),
            project_id="PROMPT_TEST",
            stage="verificacion",
            prompt_tokens=6500,
            response_tokens=1100,
            total_tokens=7600,
            duration_seconds=40,
        )
        self.analyses.append(analysis)

        errors = []
        if analysis.status not in {
            PromptEfficiencyStatus.ACCEPTABLE,
            PromptEfficiencyStatus.INEFFICIENT,
        }:
            errors.append(
                "El escenario debía ser ACCEPTABLE o INEFFICIENT."
            )

        return ScenarioResult(
            "Prompt aceptable",
            not errors,
            errors,
            {
                "status": analysis.status.value,
                "prompt_tokens": analysis.prompt_tokens,
            },
        )

    def _inefficient(self) -> ScenarioResult:
        repeated = "Explica el tema claramente y con detalle. "

        analysis = self.analyzer.analyze_prompt(
            prompt_content=repeated * 120,
            response_content="Respuesta resumida.",
            project_id="PROMPT_TEST",
            stage="guion",
            prompt_tokens=9000,
            response_tokens=900,
            thinking_tokens=200,
            total_tokens=10100,
            duration_seconds=75,
        )
        self.analyses.append(analysis)

        errors = []
        if analysis.status not in {
            PromptEfficiencyStatus.INEFFICIENT,
            PromptEfficiencyStatus.CRITICAL,
        }:
            errors.append("El escenario debía ser problemático.")
        if analysis.redundancy_score <= 20:
            errors.append("La redundancia debía superar 20.")
        if not analysis.recommendations:
            errors.append("Debían existir recomendaciones.")

        return ScenarioResult(
            "Prompt ineficiente",
            not errors,
            errors,
            {
                "status": analysis.status.value,
                "redundancy_score": analysis.redundancy_score,
                "recommendations": len(analysis.recommendations),
            },
        )

    def _critical(self) -> ScenarioResult:
        repeated = "Repite esta instrucción y genera una salida breve. "

        analysis = self.analyzer.analyze_prompt(
            prompt_content=repeated * 300,
            response_content="Respuesta muy corta.",
            project_id="PROMPT_TEST",
            stage="storyboard",
            prompt_tokens=18000,
            response_tokens=500,
            thinking_tokens=200,
            total_tokens=18700,
            duration_seconds=180,
        )
        self.analyses.append(analysis)

        errors = []
        if analysis.status != PromptEfficiencyStatus.CRITICAL:
            errors.append("El estado esperado era CRITICAL.")
        if not analysis.problem_metrics():
            errors.append("Debían existir métricas problemáticas.")

        return ScenarioResult(
            "Prompt crítico",
            not errors,
            errors,
            {
                "status": analysis.status.value,
                "problem_metrics": len(analysis.problem_metrics()),
            },
        )

    def _telemetry_event(self) -> ScenarioResult:
        event = TelemetryEvent(
            event_id="EVENT-001",
            timestamp="2026-07-15T18:00:00Z",
            project_id="PROMPT_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="seo",
            success=True,
            provider="gemini",
            model="gemini-3.5-flash",
            duration_seconds=30,
            prompt_tokens=3000,
            response_tokens=800,
            thinking_tokens=200,
            total_tokens=4000,
        )

        analysis = self.analyzer.analyze_event(
            event,
            prompt_content="Genera una estrategia SEO clara.",
            response_content="Estrategia SEO optimizada.",
        )
        self.analyses.append(analysis)

        errors = []
        if analysis.project_id != "PROMPT_TEST":
            errors.append("project_id no se propagó.")
        if analysis.stage != "seo":
            errors.append("stage no se propagó.")
        if analysis.metadata.get("event_id") != "EVENT-001":
            errors.append("event_id no quedó en metadata.")

        return ScenarioResult(
            "Análisis desde TelemetryEvent",
            not errors,
            errors,
            {
                "stage": analysis.stage,
                "provider": analysis.provider,
                "status": analysis.status.value,
            },
        )

    def _file_paths(self) -> ScenarioResult:
        prompt_path = TEST_ROOT / "PROMPT_PUBLICACION.md"
        response_path = TEST_ROOT / "06_PUBLICACION.md"

        prompt_path.write_text(
            "# Prompt\n\nRedacta una publicación breve.",
            encoding="utf-8",
        )
        response_path.write_text(
            "# Publicación\n\nRealiza pausas activas.",
            encoding="utf-8",
        )

        event = TelemetryEvent(
            event_id="EVENT-FILE",
            timestamp="2026-07-15T18:10:00Z",
            project_id="PROMPT_TEST",
            component="pipeline_engine",
            operation="execute_stage",
            stage="publicacion",
            success=True,
            prompt_tokens=500,
            response_tokens=180,
            total_tokens=680,
            duration_seconds=5,
            metadata={
                "prompt_path": str(prompt_path),
                "response_path": str(response_path),
            },
        )

        analysis = self.analyzer.analyze_event(event)
        self.analyses.append(analysis)

        errors = []
        if analysis.prompt_characters <= 0:
            errors.append("No se leyó prompt_path.")
        if analysis.response_characters <= 0:
            errors.append("No se leyó response_path.")
        if analysis.prompt_path != str(prompt_path):
            errors.append("prompt_path no se conservó.")

        return ScenarioResult(
            "Lectura de archivos",
            not errors,
            errors,
            {
                "prompt_characters": analysis.prompt_characters,
                "response_characters": analysis.response_characters,
            },
        )

    def _report(self) -> ScenarioResult:
        report = PromptIntelligenceReport(
            report_id="REPORT-TEST",
            generated_at="2026-07-15T18:20:00Z",
            project_id="PROMPT_TEST",
            status="UNKNOWN",
            analyses=list(self.analyses),
        )

        errors = []
        if report.analyses_total != len(self.analyses):
            errors.append("analyses_total es incorrecto.")
        if report.total_prompt_tokens <= 0:
            errors.append("total_prompt_tokens debía ser mayor a 0.")
        if report.status not in {
            PromptEfficiencyStatus.INEFFICIENT,
            PromptEfficiencyStatus.CRITICAL,
        }:
            errors.append("El reporte debía reflejar el peor estado.")

        return ScenarioResult(
            "Consolidación del reporte",
            not errors,
            errors,
            {
                "status": report.status.value,
                "analyses_total": report.analyses_total,
                "total_prompt_tokens": report.total_prompt_tokens,
            },
        )

    def _serialization(self) -> ScenarioResult:
        report = PromptIntelligenceReport(
            report_id="REPORT-SERIALIZATION",
            generated_at="2026-07-15T18:30:00Z",
            project_id="PROMPT_TEST",
            status="UNKNOWN",
            analyses=list(self.analyses),
        )

        payload = report.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False)
        problems = report.problematic_analyses()

        errors = []
        if not serialized:
            errors.append("La serialización quedó vacía.")
        if payload.get("analyses_total") != len(self.analyses):
            errors.append("analyses_total serializado es incorrecto.")
        if not problems:
            errors.append("Debían existir análisis problemáticos.")

        recommendations = sum(
            (analysis.recommendations for analysis in problems),
            [],
        )
        if not recommendations:
            errors.append("Debían existir recomendaciones.")

        return ScenarioResult(
            "Serialización y recomendaciones",
            not errors,
            errors,
            {
                "serialized_characters": len(serialized),
                "problematic_analyses": len(problems),
                "recommendations": len(recommendations),
            },
        )

    def _print_result(self, result: ScenarioResult) -> None:
        print()
        print("-" * 70)
        print(f"Escenario: {result.name}")
        print("-" * 70)
        print(f"Resultado: {'OK' if result.passed else 'ERROR'}")

        if result.metadata:
            print("Datos:")
            for key, value in result.metadata.items():
                print(f"  {key}: {value}")

        if result.errors:
            print("Errores:")
            for error in result.errors:
                print(f"- {error}")

    def _print_summary(self) -> bool:
        passed = sum(result.passed for result in self.results)
        failed = len(self.results) - passed
        valid = failed == 0

        print()
        print("=" * 70)
        print("RESUMEN PROMPT INTELLIGENCE")
        print("=" * 70)
        print(f"Escenarios ejecutados: {len(self.results)}")
        print(f"Escenarios aprobados: {passed}")
        print(f"Escenarios fallidos: {failed}")
        print(f"Resultado integral válido: {valid}")
        print()
        print("Artefactos conservados para inspección:")
        print(f"- {TEST_ROOT}")

        if valid:
            print()
            print(
                "Prompt Intelligence Smoke Test "
                "completado correctamente."
            )

        return valid


def main() -> int:
    return 0 if PromptIntelligenceSmokeTest().run() else 1


if __name__ == "__main__":
    sys.exit(main())