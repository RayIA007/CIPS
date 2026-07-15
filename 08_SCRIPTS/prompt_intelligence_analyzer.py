"""
=========================================================
Proyecto : CIPS
Release  : 0.9
Build    : 069
Archivo  : prompt_intelligence_analyzer.py
Estado   : RELEASE
=========================================================

Analiza prompts, respuestas y telemetría para producir
métricas de eficiencia y recomendaciones operativas.

Responsabilidades:
- analizar un prompt individual;
- analizar eventos de TelemetryEvent;
- calcular longitud, densidad y redundancia estimada;
- calcular relación prompt/respuesta;
- calcular rendimiento de salida;
- calcular tokens por segundo;
- clasificar eficiencia;
- generar PromptAnalysis;
- generar PromptIntelligenceReport.

Este componente NO:
- llama modelos de Inteligencia Artificial;
- modifica prompts;
- escribe archivos;
- ejecuta el Pipeline;
- sustituye TelemetryEngine;
- sustituye PromptEngine.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import math
import re
from pathlib import Path
from statistics import mean
from typing import Any, Iterable
from uuid import uuid4

from prompt_intelligence_models import (
    PromptAnalysis,
    PromptEfficiencyStatus,
    PromptIntelligenceReport,
    PromptMetric,
)
from telemetry_models import TelemetryEvent


class PromptIntelligenceAnalyzer:
    """
    Analizador de eficiencia de prompts.
    """

    COMPONENT_NAME = "prompt_intelligence_analyzer"
    VERSION = "0.9"

    def __init__(
        self,
        acceptable_prompt_tokens: int = 6000,
        inefficient_prompt_tokens: int = 10000,
        critical_prompt_tokens: int = 16000,
        acceptable_token_ratio: float = 5.0,
        inefficient_token_ratio: float = 8.0,
        critical_token_ratio: float = 12.0,
        acceptable_response_yield: float = 20.0,
        inefficient_response_yield: float = 10.0,
        critical_response_yield: float = 5.0,
        acceptable_redundancy_score: float = 20.0,
        inefficient_redundancy_score: float = 35.0,
        critical_redundancy_score: float = 50.0,
        acceptable_density_score: float = 35.0,
        inefficient_density_score: float = 20.0,
        critical_density_score: float = 10.0,
    ) -> None:
        self.acceptable_prompt_tokens = self._positive_int(
            acceptable_prompt_tokens,
            6000,
        )
        self.inefficient_prompt_tokens = self._positive_int(
            inefficient_prompt_tokens,
            10000,
        )
        self.critical_prompt_tokens = self._positive_int(
            critical_prompt_tokens,
            16000,
        )

        self.acceptable_token_ratio = self._non_negative_float(
            acceptable_token_ratio,
            5.0,
        )
        self.inefficient_token_ratio = self._non_negative_float(
            inefficient_token_ratio,
            8.0,
        )
        self.critical_token_ratio = self._non_negative_float(
            critical_token_ratio,
            12.0,
        )

        self.acceptable_response_yield = self._percent(
            acceptable_response_yield,
            20.0,
        )
        self.inefficient_response_yield = self._percent(
            inefficient_response_yield,
            10.0,
        )
        self.critical_response_yield = self._percent(
            critical_response_yield,
            5.0,
        )

        self.acceptable_redundancy_score = self._percent(
            acceptable_redundancy_score,
            20.0,
        )
        self.inefficient_redundancy_score = self._percent(
            inefficient_redundancy_score,
            35.0,
        )
        self.critical_redundancy_score = self._percent(
            critical_redundancy_score,
            50.0,
        )

        self.acceptable_density_score = self._percent(
            acceptable_density_score,
            35.0,
        )
        self.inefficient_density_score = self._percent(
            inefficient_density_score,
            20.0,
        )
        self.critical_density_score = self._percent(
            critical_density_score,
            10.0,
        )

    # --------------------------------------------------
    # API pública
    # --------------------------------------------------

    def analyze_prompt(
        self,
        prompt_content: str,
        response_content: str = "",
        *,
        project_id: str = "",
        stage: str = "",
        provider: str = "",
        model: str = "",
        prompt_path: str = "",
        prompt_tokens: int = 0,
        response_tokens: int = 0,
        thinking_tokens: int = 0,
        total_tokens: int = 0,
        duration_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> PromptAnalysis:
        """
        Analiza un prompt y su respuesta.
        """

        prompt_content = str(
            prompt_content or ""
        )
        response_content = str(
            response_content or ""
        )

        prompt_words = self._count_words(
            prompt_content
        )
        response_words = self._count_words(
            response_content
        )

        prompt_lines = self._count_lines(
            prompt_content
        )
        response_lines = self._count_lines(
            response_content
        )

        prompt_characters = len(
            prompt_content
        )
        response_characters = len(
            response_content
        )

        prompt_tokens = self._non_negative_int(
            prompt_tokens
        )
        response_tokens = self._non_negative_int(
            response_tokens
        )
        thinking_tokens = self._non_negative_int(
            thinking_tokens
        )
        total_tokens = self._non_negative_int(
            total_tokens
        )

        if (
            total_tokens == 0
            and (
                prompt_tokens
                or response_tokens
                or thinking_tokens
            )
        ):
            total_tokens = (
                prompt_tokens
                + response_tokens
                + thinking_tokens
            )

        character_ratio = self._safe_ratio(
            prompt_characters,
            response_characters,
        )

        token_ratio = self._safe_ratio(
            prompt_tokens,
            response_tokens,
        )

        response_yield = self._response_yield(
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            prompt_characters=prompt_characters,
            response_characters=response_characters,
        )

        tokens_per_second = self._safe_ratio(
            total_tokens,
            duration_seconds,
        )

        redundancy_score = self._estimate_redundancy(
            prompt_content
        )

        density_score = self._estimate_density(
            prompt_content
        )

        analysis = PromptAnalysis(
            analysis_id=self._new_analysis_id(),
            project_id=project_id,
            stage=stage,
            status=PromptEfficiencyStatus.UNKNOWN,
            provider=provider,
            model=model,
            prompt_path=prompt_path,
            prompt_characters=prompt_characters,
            prompt_words=prompt_words,
            prompt_lines=prompt_lines,
            prompt_tokens=prompt_tokens,
            response_characters=response_characters,
            response_words=response_words,
            response_lines=response_lines,
            response_tokens=response_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=total_tokens,
            duration_seconds=duration_seconds,
            prompt_response_character_ratio=character_ratio,
            prompt_response_token_ratio=token_ratio,
            response_yield_percent=response_yield,
            tokens_per_second=tokens_per_second,
            redundancy_score=redundancy_score,
            density_score=density_score,
            metadata=dict(
                metadata or {}
            ),
        )

        for metric in self._build_metrics(
            analysis
        ):
            analysis.add_metric(
                metric
            )

        analysis.metadata.update(
            {
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "thresholds": self.get_thresholds(),
            }
        )

        return analysis

    def analyze_event(
        self,
        event: TelemetryEvent,
        prompt_content: str = "",
        response_content: str = "",
    ) -> PromptAnalysis:
        """
        Analiza un TelemetryEvent.
        """

        if not isinstance(
            event,
            TelemetryEvent,
        ):
            raise TypeError(
                "event debe ser TelemetryEvent."
            )

        resolved_prompt = prompt_content
        resolved_response = response_content

        if (
            not resolved_prompt
            and event.metadata.get(
                "prompt_path"
            )
        ):
            resolved_prompt = self._read_text_file(
                event.metadata.get(
                    "prompt_path"
                )
            )

        if (
            not resolved_response
            and event.metadata.get(
                "response_path"
            )
        ):
            resolved_response = self._read_text_file(
                event.metadata.get(
                    "response_path"
                )
            )

        return self.analyze_prompt(
            prompt_content=resolved_prompt,
            response_content=resolved_response,
            project_id=event.project_id,
            stage=event.stage,
            provider=event.provider,
            model=event.model,
            prompt_path=str(
                event.metadata.get(
                    "prompt_path",
                    "",
                )
            ),
            prompt_tokens=event.prompt_tokens,
            response_tokens=event.response_tokens,
            thinking_tokens=event.thinking_tokens,
            total_tokens=event.total_tokens,
            duration_seconds=event.duration_seconds,
            metadata={
                "event_id": event.event_id,
                "event_success": event.success,
                "status_code": event.status_code,
                "retry_count": event.retry_count,
                "retry_exhausted": (
                    event.retry_exhausted
                ),
            },
        )

    def analyze_events(
        self,
        events: Iterable[
            TelemetryEvent | dict[str, Any]
        ],
        project_id: str = "",
        scope: str = "project",
    ) -> PromptIntelligenceReport:
        """
        Analiza múltiples eventos y genera reporte.
        """

        normalized_events = self._normalize_events(
            events
        )

        resolved_project_id = str(
            project_id
            or self._infer_project_id(
                normalized_events
            )
            or ""
        ).strip()

        report = PromptIntelligenceReport(
            report_id=self._new_report_id(),
            generated_at=self._utc_now(),
            project_id=resolved_project_id,
            status=PromptEfficiencyStatus.UNKNOWN,
            scope=scope,
            metadata={
                "component": self.COMPONENT_NAME,
                "version": self.VERSION,
                "events_received": len(
                    normalized_events
                ),
            },
        )

        for event in normalized_events:
            analysis = self.analyze_event(
                event
            )
            report.add_analysis(
                analysis
            )

        report.recommendations = self._consolidate_recommendations(
            report
        )

        if not normalized_events:
            report.warnings.append(
                "No existen eventos para analizar."
            )

        return report

    def get_thresholds(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve umbrales públicos.
        """

        return {
            "acceptable_prompt_tokens": (
                self.acceptable_prompt_tokens
            ),
            "inefficient_prompt_tokens": (
                self.inefficient_prompt_tokens
            ),
            "critical_prompt_tokens": (
                self.critical_prompt_tokens
            ),
            "acceptable_token_ratio": (
                self.acceptable_token_ratio
            ),
            "inefficient_token_ratio": (
                self.inefficient_token_ratio
            ),
            "critical_token_ratio": (
                self.critical_token_ratio
            ),
            "acceptable_response_yield": (
                self.acceptable_response_yield
            ),
            "inefficient_response_yield": (
                self.inefficient_response_yield
            ),
            "critical_response_yield": (
                self.critical_response_yield
            ),
            "acceptable_redundancy_score": (
                self.acceptable_redundancy_score
            ),
            "inefficient_redundancy_score": (
                self.inefficient_redundancy_score
            ),
            "critical_redundancy_score": (
                self.critical_redundancy_score
            ),
            "acceptable_density_score": (
                self.acceptable_density_score
            ),
            "inefficient_density_score": (
                self.inefficient_density_score
            ),
            "critical_density_score": (
                self.critical_density_score
            ),
        }

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "reads_files": True,
            "writes_files": False,
            "provider_agnostic": True,
            "uses_telemetry": True,
            "metrics": [
                "prompt_length",
                "token_ratio",
                "response_yield",
                "redundancy",
                "density",
                "throughput",
            ],
            "next_component": (
                "prompt_intelligence_smoke_test"
            ),
        }

    # --------------------------------------------------
    # Métricas
    # --------------------------------------------------

    def _build_metrics(
        self,
        analysis: PromptAnalysis,
    ) -> list[PromptMetric]:
        """
        Construye las métricas del análisis.
        """

        metrics = [
            self._prompt_length_metric(
                analysis.prompt_tokens
            ),
            self._token_ratio_metric(
                analysis.prompt_response_token_ratio,
                analysis.response_tokens,
            ),
            self._response_yield_metric(
                analysis.response_yield_percent,
                analysis.response_tokens,
            ),
            self._redundancy_metric(
                analysis.redundancy_score
            ),
            self._density_metric(
                analysis.density_score
            ),
        ]

        if analysis.duration_seconds > 0:
            metrics.append(
                self._throughput_metric(
                    analysis.tokens_per_second
                )
            )

        return metrics

    def _prompt_length_metric(
        self,
        prompt_tokens: int,
    ) -> PromptMetric:
        if prompt_tokens <= 0:
            return PromptMetric(
                metric_id="prompt_length",
                name="Longitud del prompt",
                status=PromptEfficiencyStatus.UNKNOWN,
                value=prompt_tokens,
                unit="tokens",
                score=0,
                weight=1.5,
                message=(
                    "No existen tokens de prompt "
                    "para evaluar."
                ),
            )

        if prompt_tokens >= self.critical_prompt_tokens:
            status = PromptEfficiencyStatus.CRITICAL
            score = 20
            message = (
                "El prompt supera el umbral crítico."
            )
        elif prompt_tokens >= self.inefficient_prompt_tokens:
            status = PromptEfficiencyStatus.INEFFICIENT
            score = 45
            message = (
                "El prompt es excesivamente largo."
            )
        elif prompt_tokens >= self.acceptable_prompt_tokens:
            status = PromptEfficiencyStatus.ACCEPTABLE
            score = 70
            message = (
                "El prompt es largo pero aceptable."
            )
        else:
            status = PromptEfficiencyStatus.EFFICIENT
            score = 95
            message = (
                "La longitud del prompt es eficiente."
            )

        return PromptMetric(
            metric_id="prompt_length",
            name="Longitud del prompt",
            status=status,
            value=prompt_tokens,
            unit="tokens",
            warning_threshold=(
                self.acceptable_prompt_tokens
            ),
            critical_threshold=(
                self.critical_prompt_tokens
            ),
            score=score,
            weight=1.5,
            message=message,
            recommendation=(
                "Reduce contexto redundante y separa "
                "instrucciones no esenciales."
                if status
                in {
                    PromptEfficiencyStatus.INEFFICIENT,
                    PromptEfficiencyStatus.CRITICAL,
                }
                else ""
            ),
        )

    def _token_ratio_metric(
        self,
        ratio: float,
        response_tokens: int,
    ) -> PromptMetric:
        if response_tokens <= 0:
            return PromptMetric(
                metric_id="token_ratio",
                name="Relación prompt/respuesta",
                status=PromptEfficiencyStatus.UNKNOWN,
                value=ratio,
                unit="ratio",
                score=0,
                weight=2.0,
                message=(
                    "No existen tokens de respuesta "
                    "para calcular la relación."
                ),
            )

        if ratio >= self.critical_token_ratio:
            status = PromptEfficiencyStatus.CRITICAL
            score = 15
        elif ratio >= self.inefficient_token_ratio:
            status = PromptEfficiencyStatus.INEFFICIENT
            score = 40
        elif ratio >= self.acceptable_token_ratio:
            status = PromptEfficiencyStatus.ACCEPTABLE
            score = 70
        else:
            status = PromptEfficiencyStatus.EFFICIENT
            score = 95

        return PromptMetric(
            metric_id="token_ratio",
            name="Relación prompt/respuesta",
            status=status,
            value=round(
                ratio,
                4,
            ),
            unit="ratio",
            warning_threshold=(
                self.acceptable_token_ratio
            ),
            critical_threshold=(
                self.critical_token_ratio
            ),
            score=score,
            weight=2.0,
            message=(
                "La relación compara tokens de entrada "
                "contra tokens de salida."
            ),
            recommendation=(
                "Reduce el contexto o solicita una salida "
                "más concreta y estructurada."
                if status
                in {
                    PromptEfficiencyStatus.INEFFICIENT,
                    PromptEfficiencyStatus.CRITICAL,
                }
                else ""
            ),
        )

    def _response_yield_metric(
        self,
        yield_percent: float,
        response_tokens: int,
    ) -> PromptMetric:
        if response_tokens <= 0:
            return PromptMetric(
                metric_id="response_yield",
                name="Rendimiento de salida",
                status=PromptEfficiencyStatus.UNKNOWN,
                value=yield_percent,
                unit="%",
                score=0,
                weight=2.0,
                message=(
                    "No existe salida para evaluar."
                ),
            )

        if yield_percent <= self.critical_response_yield:
            status = PromptEfficiencyStatus.CRITICAL
            score = 15
        elif yield_percent <= self.inefficient_response_yield:
            status = PromptEfficiencyStatus.INEFFICIENT
            score = 40
        elif yield_percent <= self.acceptable_response_yield:
            status = PromptEfficiencyStatus.ACCEPTABLE
            score = 70
        else:
            status = PromptEfficiencyStatus.EFFICIENT
            score = 95

        return PromptMetric(
            metric_id="response_yield",
            name="Rendimiento de salida",
            status=status,
            value=round(
                yield_percent,
                4,
            ),
            unit="%",
            warning_threshold=(
                self.acceptable_response_yield
            ),
            critical_threshold=(
                self.critical_response_yield
            ),
            score=score,
            weight=2.0,
            message=(
                "Porcentaje de salida respecto "
                "a la entrada."
            ),
            recommendation=(
                "Reduce instrucciones redundantes o ajusta "
                "el alcance solicitado."
                if status
                in {
                    PromptEfficiencyStatus.INEFFICIENT,
                    PromptEfficiencyStatus.CRITICAL,
                }
                else ""
            ),
        )

    def _redundancy_metric(
        self,
        score_value: float,
    ) -> PromptMetric:
        if score_value >= self.critical_redundancy_score:
            status = PromptEfficiencyStatus.CRITICAL
            score = 20
        elif score_value >= self.inefficient_redundancy_score:
            status = PromptEfficiencyStatus.INEFFICIENT
            score = 45
        elif score_value >= self.acceptable_redundancy_score:
            status = PromptEfficiencyStatus.ACCEPTABLE
            score = 70
        else:
            status = PromptEfficiencyStatus.EFFICIENT
            score = 95

        return PromptMetric(
            metric_id="redundancy",
            name="Redundancia estimada",
            status=status,
            value=round(
                score_value,
                4,
            ),
            unit="%",
            warning_threshold=(
                self.acceptable_redundancy_score
            ),
            critical_threshold=(
                self.critical_redundancy_score
            ),
            score=score,
            weight=1.5,
            message=(
                "Estimación heurística de repetición "
                "de vocabulario y líneas."
            ),
            recommendation=(
                "Elimina instrucciones, encabezados o "
                "fragmentos repetidos."
                if status
                in {
                    PromptEfficiencyStatus.INEFFICIENT,
                    PromptEfficiencyStatus.CRITICAL,
                }
                else ""
            ),
        )

    def _density_metric(
        self,
        score_value: float,
    ) -> PromptMetric:
        if score_value <= self.critical_density_score:
            status = PromptEfficiencyStatus.CRITICAL
            score = 20
        elif score_value <= self.inefficient_density_score:
            status = PromptEfficiencyStatus.INEFFICIENT
            score = 45
        elif score_value <= self.acceptable_density_score:
            status = PromptEfficiencyStatus.ACCEPTABLE
            score = 70
        else:
            status = PromptEfficiencyStatus.EFFICIENT
            score = 95

        return PromptMetric(
            metric_id="instruction_density",
            name="Densidad informativa",
            status=status,
            value=round(
                score_value,
                4,
            ),
            unit="%",
            warning_threshold=(
                self.acceptable_density_score
            ),
            critical_threshold=(
                self.critical_density_score
            ),
            score=score,
            weight=1.5,
            message=(
                "Proporción estimada de contenido útil "
                "frente a estructura y repetición."
            ),
            recommendation=(
                "Concentra instrucciones, restricciones "
                "y datos relevantes en menos bloques."
                if status
                in {
                    PromptEfficiencyStatus.INEFFICIENT,
                    PromptEfficiencyStatus.CRITICAL,
                }
                else ""
            ),
        )

    def _throughput_metric(
        self,
        tokens_per_second: float,
    ) -> PromptMetric:
        if tokens_per_second <= 0:
            status = PromptEfficiencyStatus.UNKNOWN
            score = 0
        elif tokens_per_second < 20:
            status = PromptEfficiencyStatus.INEFFICIENT
            score = 45
        elif tokens_per_second < 40:
            status = PromptEfficiencyStatus.ACCEPTABLE
            score = 70
        else:
            status = PromptEfficiencyStatus.EFFICIENT
            score = 90

        return PromptMetric(
            metric_id="throughput",
            name="Procesamiento de tokens",
            status=status,
            value=round(
                tokens_per_second,
                4,
            ),
            unit="tokens/second",
            score=score,
            weight=0.5,
            message=(
                "Velocidad aproximada del flujo "
                "completo de tokens."
            ),
            recommendation=(
                "Revisa latencia del proveedor y tamaño "
                "total del contexto."
                if status
                == PromptEfficiencyStatus.INEFFICIENT
                else ""
            ),
        )

    # --------------------------------------------------
    # Heurísticas
    # --------------------------------------------------

    def _estimate_redundancy(
        self,
        text: str,
    ) -> float:
        words = [
            word.lower()
            for word in re.findall(
                r"\b[\wáéíóúüñ]+\b",
                text,
                flags=re.IGNORECASE,
            )
            if len(word) > 3
        ]

        if not words:
            return 0.0

        counts = Counter(
            words
        )

        repeated_occurrences = sum(
            count - 1
            for count in counts.values()
            if count > 1
        )

        word_redundancy = self._rate(
            repeated_occurrences,
            len(words),
        )

        lines = [
            self._normalize_line(
                line
            )
            for line in text.splitlines()
            if self._normalize_line(
                line
            )
        ]

        if lines:
            line_counts = Counter(
                lines
            )
            repeated_lines = sum(
                count - 1
                for count in line_counts.values()
                if count > 1
            )
            line_redundancy = self._rate(
                repeated_lines,
                len(lines),
            )
        else:
            line_redundancy = 0.0

        return round(
            (
                word_redundancy * 0.7
                + line_redundancy * 0.3
            ),
            4,
        )

    def _estimate_density(
        self,
        text: str,
    ) -> float:
        words = re.findall(
            r"\b[\wáéíóúüñ]+\b",
            text,
            flags=re.IGNORECASE,
        )

        if not words:
            return 0.0

        meaningful_words = [
            word
            for word in words
            if (
                len(word) > 3
                and word.lower()
                not in self._stopwords()
            )
        ]

        lexical_density = self._rate(
            len(
                meaningful_words
            ),
            len(
                words
            ),
        )

        structure_penalty = min(
            (
                text.count("#")
                + text.count("- ")
                + text.count("* ")
            )
            / max(
                len(
                    text.splitlines()
                ),
                1,
            )
            * 10,
            25.0,
        )

        density = (
            lexical_density
            - structure_penalty
        )

        return round(
            min(
                max(
                    density,
                    0.0,
                ),
                100.0,
            ),
            4,
        )

    # --------------------------------------------------
    # Reporte y utilidades
    # --------------------------------------------------

    def _consolidate_recommendations(
        self,
        report: PromptIntelligenceReport,
    ) -> list[str]:
        recommendations: list[str] = []

        for analysis in report.analyses:
            for recommendation in analysis.recommendations:
                recommendations.append(
                    (
                        f"{analysis.stage}: "
                        f"{recommendation}"
                    )
                    if analysis.stage
                    else recommendation
                )

        if report.status == PromptEfficiencyStatus.EFFICIENT:
            recommendations.append(
                "Mantener la estructura actual de prompts."
            )
        elif report.status == PromptEfficiencyStatus.ACCEPTABLE:
            recommendations.append(
                "Aplicar mejoras menores antes de aumentar "
                "el volumen de producción."
            )
        elif report.status == PromptEfficiencyStatus.INEFFICIENT:
            recommendations.append(
                "Optimizar los prompts problemáticos antes "
                "de nuevas ejecuciones."
            )
        elif report.status == PromptEfficiencyStatus.CRITICAL:
            recommendations.append(
                "Detener ejecuciones no esenciales y reducir "
                "longitud, redundancia y alcance."
            )

        return self._unique_strings(
            recommendations
        )

    def _normalize_events(
        self,
        events: Iterable[
            TelemetryEvent | dict[str, Any]
        ],
    ) -> list[TelemetryEvent]:
        normalized: list[TelemetryEvent] = []

        for event in events or []:
            if isinstance(
                event,
                TelemetryEvent,
            ):
                normalized.append(
                    event
                )
            elif isinstance(
                event,
                dict,
            ):
                data = {
                    key: value
                    for key, value in event.items()
                    if key
                    in TelemetryEvent.__dataclass_fields__
                }
                normalized.append(
                    TelemetryEvent(
                        **data
                    )
                )

        return normalized

    def _infer_project_id(
        self,
        events: list[TelemetryEvent],
    ) -> str:
        project_ids = {
            event.project_id
            for event in events
            if event.project_id
        }

        if len(project_ids) == 1:
            return next(
                iter(
                    project_ids
                )
            )

        return ""

    def _read_text_file(
        self,
        path_value: Any,
    ) -> str:
        if not path_value:
            return ""

        try:
            path = Path(
                str(
                    path_value
                )
            )
        except Exception:
            return ""

        if not path.exists():
            return ""

        try:
            return path.read_text(
                encoding="utf-8"
            )
        except Exception:
            return ""

    def _count_words(
        self,
        text: str,
    ) -> int:
        return len(
            re.findall(
                r"\b[\wáéíóúüñ]+\b",
                text,
                flags=re.IGNORECASE,
            )
        )

    def _count_lines(
        self,
        text: str,
    ) -> int:
        if not text:
            return 0

        return len(
            text.splitlines()
        )

    def _response_yield(
        self,
        prompt_tokens: int,
        response_tokens: int,
        prompt_characters: int,
        response_characters: int,
    ) -> float:
        if prompt_tokens > 0:
            return self._rate(
                response_tokens,
                prompt_tokens,
            )

        if prompt_characters > 0:
            return self._rate(
                response_characters,
                prompt_characters,
            )

        return 0.0

    def _safe_ratio(
        self,
        numerator: float,
        denominator: float,
    ) -> float:
        if denominator <= 0:
            return 0.0

        return round(
            numerator
            / denominator,
            6,
        )

    def _rate(
        self,
        numerator: float,
        denominator: float,
    ) -> float:
        if denominator <= 0:
            return 0.0

        return round(
            (
                numerator
                / denominator
            )
            * 100,
            6,
        )

    def _normalize_line(
        self,
        value: str,
    ) -> str:
        return re.sub(
            r"\s+",
            " ",
            str(
                value or ""
            ).strip().lower(),
        )

    def _stopwords(
        self,
    ) -> set[str]:
        return {
            "para",
            "como",
            "este",
            "esta",
            "estos",
            "estas",
            "desde",
            "hasta",
            "entre",
            "sobre",
            "cada",
            "todo",
            "toda",
            "todos",
            "todas",
            "pero",
            "porque",
            "cuando",
            "donde",
            "quien",
            "cual",
            "también",
            "solo",
            "debe",
            "deben",
            "puede",
            "pueden",
            "with",
            "from",
            "that",
            "this",
            "have",
            "will",
            "your",
            "into",
            "about",
            "should",
        }

    def _positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        try:
            number = int(
                value
            )
        except (TypeError, ValueError):
            return default

        return number if number > 0 else default

    def _non_negative_int(
        self,
        value: Any,
    ) -> int:
        try:
            number = int(
                value
            )
        except (TypeError, ValueError):
            return 0

        return max(
            number,
            0,
        )

    def _non_negative_float(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return default

        return max(
            number,
            0.0,
        )

    def _percent(
        self,
        value: Any,
        default: float,
    ) -> float:
        try:
            number = float(
                value
            )
        except (TypeError, ValueError):
            return default

        return min(
            max(
                number,
                0.0,
            ),
            100.0,
        )

    def _unique_strings(
        self,
        values: list[str],
    ) -> list[str]:
        unique: list[str] = []

        for value in values:
            item = str(
                value or ""
            ).strip()

            if (
                item
                and item not in unique
            ):
                unique.append(
                    item
                )

        return unique

    def _new_analysis_id(
        self,
    ) -> str:
        return (
            "PROMPT-"
            + uuid4().hex.upper()
        )

    def _new_report_id(
        self,
    ) -> str:
        return (
            "PROMPT-REPORT-"
            + uuid4().hex.upper()
        )

    def _utc_now(
        self,
    ) -> str:
        return (
            datetime.now(
                timezone.utc
            )
            .isoformat(
                timespec="milliseconds"
            )
            .replace(
                "+00:00",
                "Z",
            )
        )