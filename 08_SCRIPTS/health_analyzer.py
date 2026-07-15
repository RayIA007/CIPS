"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 065
Archivo  : health_analyzer.py
Estado   : RELEASE
=========================================================

Analiza eventos de telemetría y construye indicadores de
salud para el Runtime CIPS.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Iterable
from uuid import uuid4

from health_models import (
    ComponentHealth,
    HealthIndicator,
    HealthStatus,
    RuntimeHealthReport,
    worst_health_status,
)
from telemetry_models import TelemetryEvent


class HealthAnalyzer:
    """
    Analizador de salud basado en eventos de telemetría.
    """

    COMPONENT_NAME = "health_analyzer"
    VERSION = "0.8"

    def __init__(
        self,
        healthy_success_rate: float = 90.0,
        degraded_success_rate: float = 70.0,
        degraded_average_duration_seconds: float = 60.0,
        unhealthy_average_duration_seconds: float = 180.0,
        degraded_retry_rate: float = 25.0,
        unhealthy_retry_rate: float = 60.0,
        degraded_exhaustion_rate: float = 10.0,
        unhealthy_exhaustion_rate: float = 30.0,
        minimum_events_for_confidence: int = 2,
    ) -> None:
        self.healthy_success_rate = self._percent(
            healthy_success_rate,
            90.0,
        )
        self.degraded_success_rate = self._percent(
            degraded_success_rate,
            70.0,
        )
        self.degraded_average_duration_seconds = (
            self._non_negative_float(
                degraded_average_duration_seconds,
                60.0,
            )
        )
        self.unhealthy_average_duration_seconds = (
            self._non_negative_float(
                unhealthy_average_duration_seconds,
                180.0,
            )
        )
        self.degraded_retry_rate = self._percent(
            degraded_retry_rate,
            25.0,
        )
        self.unhealthy_retry_rate = self._percent(
            unhealthy_retry_rate,
            60.0,
        )
        self.degraded_exhaustion_rate = self._percent(
            degraded_exhaustion_rate,
            10.0,
        )
        self.unhealthy_exhaustion_rate = self._percent(
            unhealthy_exhaustion_rate,
            30.0,
        )
        self.minimum_events_for_confidence = self._positive_int(
            minimum_events_for_confidence,
            2,
        )

    def analyze(
        self,
        events: Iterable[TelemetryEvent | dict[str, Any]],
        project_id: str = "",
        scope: str = "project",
    ) -> RuntimeHealthReport:
        normalized_events = self._normalize_events(
            events
        )

        resolved_project_id = (
            str(
                project_id
                or self._infer_project_id(
                    normalized_events
                )
                or ""
            )
            .strip()
        )

        if not normalized_events:
            return RuntimeHealthReport(
                report_id=self._new_report_id(),
                generated_at=self._utc_now(),
                status=HealthStatus.UNKNOWN,
                project_id=resolved_project_id,
                scope=scope,
                indicators=[
                    HealthIndicator(
                        indicator_id="telemetry_availability",
                        name="Disponibilidad de telemetría",
                        status=HealthStatus.UNKNOWN,
                        value=0,
                        unit="events",
                        message=(
                            "No existen eventos suficientes "
                            "para evaluar la salud."
                        ),
                        recommendation=(
                            "Ejecuta al menos un Stage y confirma "
                            "que TelemetryEngine registre eventos."
                        ),
                        severity=20,
                    )
                ],
                recommendations=[
                    "Generar telemetría antes de evaluar "
                    "la salud del Runtime."
                ],
                metadata=self._base_metadata(),
            )

        successful_events = sum(
            1
            for event in normalized_events
            if event.success
        )
        failed_events = (
            len(normalized_events)
            - successful_events
        )
        total_duration = sum(
            event.duration_seconds
            for event in normalized_events
        )
        average_duration = mean(
            event.duration_seconds
            for event in normalized_events
        )

        report = RuntimeHealthReport(
            report_id=self._new_report_id(),
            generated_at=self._utc_now(),
            status=HealthStatus.UNKNOWN,
            project_id=resolved_project_id,
            scope=scope,
            events_total=len(normalized_events),
            successful_events=successful_events,
            failed_events=failed_events,
            total_duration_seconds=round(
                total_duration,
                6,
            ),
            average_duration_seconds=round(
                average_duration,
                6,
            ),
            total_tokens=sum(
                event.total_tokens
                for event in normalized_events
            ),
            retry_count=sum(
                event.retry_count
                for event in normalized_events
            ),
            exhausted_events=sum(
                1
                for event in normalized_events
                if event.retry_exhausted
            ),
            recovered_events=sum(
                1
                for event in normalized_events
                if event.succeeded_after_retry
            ),
            metadata=self._base_metadata(),
        )

        for indicator in self._build_global_indicators(
            report,
            normalized_events,
        ):
            report.add_indicator(
                indicator
            )

        for component in self._analyze_dimensions(
            normalized_events
        ):
            report.add_component(
                component
            )

        report.recommendations = self._build_recommendations(
            report
        )
        report.metadata["events_analyzed"] = len(
            normalized_events
        )
        report.metadata["thresholds"] = self.get_thresholds()

        return report

    def analyze_component(
        self,
        events: Iterable[TelemetryEvent | dict[str, Any]],
        component: str,
        category: str = "runtime",
    ) -> ComponentHealth:
        return self._build_component_health(
            component=str(
                component or "unknown"
            ).strip(),
            category=category,
            events=self._normalize_events(
                events
            ),
        )

    def get_thresholds(
        self,
    ) -> dict[str, Any]:
        return {
            "healthy_success_rate": self.healthy_success_rate,
            "degraded_success_rate": self.degraded_success_rate,
            "degraded_average_duration_seconds": (
                self.degraded_average_duration_seconds
            ),
            "unhealthy_average_duration_seconds": (
                self.unhealthy_average_duration_seconds
            ),
            "degraded_retry_rate": self.degraded_retry_rate,
            "unhealthy_retry_rate": self.unhealthy_retry_rate,
            "degraded_exhaustion_rate": (
                self.degraded_exhaustion_rate
            ),
            "unhealthy_exhaustion_rate": (
                self.unhealthy_exhaustion_rate
            ),
            "minimum_events_for_confidence": (
                self.minimum_events_for_confidence
            ),
        }

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "reads_files": False,
            "writes_files": False,
            "provider_agnostic": True,
            "dimensions": [
                "component",
                "provider",
                "model",
                "stage",
            ],
            "next_component": "runtime_health_monitor",
        }

    def _build_global_indicators(
        self,
        report: RuntimeHealthReport,
        events: list[TelemetryEvent],
    ) -> list[HealthIndicator]:
        retry_events = sum(
            1
            for event in events
            if (
                event.retry_count > 0
                or event.retry_attempts > 1
            )
        )
        exhaustion_rate = self._rate(
            report.exhausted_events,
            report.events_total,
        )
        indicators = [
            self._success_rate_indicator(
                report.events_total,
                report.success_rate,
            ),
            self._duration_indicator(
                report.average_duration_seconds
            ),
            self._retry_rate_indicator(
                self._rate(
                    retry_events,
                    report.events_total,
                )
            ),
            self._exhaustion_indicator(
                exhaustion_rate,
                report.exhausted_events,
            ),
        ]

        http_counts = self._count_status_codes(
            events
        )
        if http_counts:
            indicators.append(
                self._http_indicator(
                    http_counts
                )
            )

        if any(
            (
                event.status_code == 429
                or self._contains_marker(
                    event,
                    (
                        "resource_exhausted",
                        "quota exceeded",
                        "quota",
                    ),
                )
            )
            for event in events
        ):
            indicators.append(
                HealthIndicator(
                    indicator_id="quota_pressure",
                    name="Presión de cuota",
                    status=HealthStatus.UNHEALTHY,
                    value=True,
                    unit="boolean",
                    message=(
                        "Se detectaron errores de cuota "
                        "o rate limit."
                    ),
                    recommendation=(
                        "Detén pruebas no esenciales, espera "
                        "la renovación de cuota o configura "
                        "un proveedor alternativo."
                    ),
                    severity=90,
                    critical=True,
                )
            )

        if (
            report.events_total
            < self.minimum_events_for_confidence
        ):
            indicators.append(
                HealthIndicator(
                    indicator_id="sample_confidence",
                    name="Confianza de la muestra",
                    status=HealthStatus.UNKNOWN,
                    value=report.events_total,
                    unit="events",
                    threshold_warning=(
                        self.minimum_events_for_confidence
                    ),
                    message=(
                        "La muestra es pequeña para concluir "
                        "la salud con alta confianza."
                    ),
                    recommendation=(
                        "Acumula más eventos antes de tomar "
                        "decisiones permanentes."
                    ),
                    severity=10,
                )
            )

        return indicators

    def _analyze_dimensions(
        self,
        events: list[TelemetryEvent],
    ) -> list[ComponentHealth]:
        results: list[ComponentHealth] = []

        dimensions = (
            (
                "component",
                "runtime",
                lambda event: event.component,
            ),
            (
                "provider",
                "provider",
                lambda event: event.provider,
            ),
            (
                "model",
                "model",
                lambda event: event.model,
            ),
            (
                "stage",
                "stage",
                lambda event: event.stage,
            ),
        )

        for name, category, resolver in dimensions:
            grouped: dict[
                str,
                list[TelemetryEvent],
            ] = defaultdict(
                list
            )

            for event in events:
                key = str(
                    resolver(event) or ""
                ).strip()
                if key:
                    grouped[key].append(
                        event
                    )

            for key, grouped_events in sorted(
                grouped.items()
            ):
                label = (
                    key
                    if name == "component"
                    else f"{name}:{key}"
                )
                results.append(
                    self._build_component_health(
                        label,
                        category,
                        grouped_events,
                    )
                )

        return results

    def _build_component_health(
        self,
        component: str,
        category: str,
        events: list[TelemetryEvent],
    ) -> ComponentHealth:
        if not events:
            return ComponentHealth(
                component=component,
                category=category,
                status=HealthStatus.UNKNOWN,
            )

        successful_events = sum(
            1
            for event in events
            if event.success
        )
        failed_events = (
            len(events)
            - successful_events
        )
        retry_events = sum(
            1
            for event in events
            if (
                event.retry_count > 0
                or event.retry_attempts > 1
            )
        )

        health = ComponentHealth(
            component=component,
            category=category,
            status=HealthStatus.HEALTHY,
            events_total=len(events),
            successful_events=successful_events,
            failed_events=failed_events,
            average_duration_seconds=round(
                mean(
                    event.duration_seconds
                    for event in events
                ),
                6,
            ),
            maximum_duration_seconds=round(
                max(
                    event.duration_seconds
                    for event in events
                ),
                6,
            ),
            retry_attempts=sum(
                event.retry_attempts
                for event in events
            ),
            retry_count=sum(
                event.retry_count
                for event in events
            ),
            exhausted_events=sum(
                1
                for event in events
                if event.retry_exhausted
            ),
            recovered_events=sum(
                1
                for event in events
                if event.succeeded_after_retry
            ),
            total_tokens=sum(
                event.total_tokens
                for event in events
            ),
            estimated_cost=sum(
                event.estimated_cost
                for event in events
            ),
            currency=self._resolve_currency(
                events
            ),
            metadata={
                "status_codes": self._count_status_codes(
                    events
                ),
                "exception_types": (
                    self._count_exception_types(
                        events
                    )
                ),
            },
        )

        indicators = [
            self._success_rate_indicator(
                health.events_total,
                health.success_rate,
            ),
            self._duration_indicator(
                health.average_duration_seconds
            ),
            self._retry_rate_indicator(
                self._rate(
                    retry_events,
                    health.events_total,
                )
            ),
            self._exhaustion_indicator(
                self._rate(
                    health.exhausted_events,
                    health.events_total,
                ),
                health.exhausted_events,
            ),
        ]

        http_counts = self._count_status_codes(
            events
        )
        if http_counts:
            indicators.append(
                self._http_indicator(
                    http_counts
                )
            )

        for indicator in indicators:
            health.add_indicator(
                indicator
            )

        health.status = worst_health_status(
            [
                indicator.status
                for indicator in health.indicators
            ]
        )

        if (
            health.events_total
            < self.minimum_events_for_confidence
        ):
            health.warnings.append(
                "Muestra pequeña; el estado puede cambiar "
                "con nuevos eventos."
            )

        return health

    def _success_rate_indicator(
        self,
        events_total: int,
        success_rate: float,
    ) -> HealthIndicator:
        if events_total <= 0:
            status = HealthStatus.UNKNOWN
            severity = 0
            message = "No existen eventos."
        elif success_rate >= self.healthy_success_rate:
            status = HealthStatus.HEALTHY
            severity = 0
            message = "La tasa de éxito es saludable."
        elif success_rate >= self.degraded_success_rate:
            status = HealthStatus.DEGRADED
            severity = 45
            message = "La tasa de éxito está degradada."
        else:
            status = HealthStatus.UNHEALTHY
            severity = 85
            message = "La tasa de éxito es crítica."

        return HealthIndicator(
            indicator_id="success_rate",
            name="Tasa de éxito",
            status=status,
            value=round(
                success_rate,
                2,
            ),
            unit="%",
            threshold_warning=self.healthy_success_rate,
            threshold_critical=self.degraded_success_rate,
            message=message,
            recommendation=(
                "Revisa eventos fallidos, códigos HTTP "
                "y componentes degradados."
                if status
                in {
                    HealthStatus.DEGRADED,
                    HealthStatus.UNHEALTHY,
                }
                else ""
            ),
            severity=severity,
            critical=(
                status == HealthStatus.UNHEALTHY
            ),
        )

    def _duration_indicator(
        self,
        average_duration_seconds: float,
    ) -> HealthIndicator:
        if (
            average_duration_seconds
            >= self.unhealthy_average_duration_seconds
        ):
            status = HealthStatus.UNHEALTHY
            severity = 80
            message = "La duración promedio es crítica."
        elif (
            average_duration_seconds
            >= self.degraded_average_duration_seconds
        ):
            status = HealthStatus.DEGRADED
            severity = 40
            message = "La duración promedio es elevada."
        else:
            status = HealthStatus.HEALTHY
            severity = 0
            message = "La duración promedio es saludable."

        return HealthIndicator(
            indicator_id="average_duration",
            name="Duración promedio",
            status=status,
            value=round(
                average_duration_seconds,
                6,
            ),
            unit="seconds",
            threshold_warning=(
                self.degraded_average_duration_seconds
            ),
            threshold_critical=(
                self.unhealthy_average_duration_seconds
            ),
            message=message,
            recommendation=(
                "Revisa latencia del proveedor, tamaño del "
                "prompt y tiempos de Retry."
                if status
                in {
                    HealthStatus.DEGRADED,
                    HealthStatus.UNHEALTHY,
                }
                else ""
            ),
            severity=severity,
        )

    def _retry_rate_indicator(
        self,
        retry_rate: float,
    ) -> HealthIndicator:
        if retry_rate >= self.unhealthy_retry_rate:
            status = HealthStatus.UNHEALTHY
            severity = 80
            message = "La tasa de Retry es crítica."
        elif retry_rate >= self.degraded_retry_rate:
            status = HealthStatus.DEGRADED
            severity = 40
            message = "Los reintentos son frecuentes."
        else:
            status = HealthStatus.HEALTHY
            severity = 0
            message = "La actividad de Retry es saludable."

        return HealthIndicator(
            indicator_id="retry_rate",
            name="Tasa de eventos con Retry",
            status=status,
            value=round(
                retry_rate,
                2,
            ),
            unit="%",
            threshold_warning=self.degraded_retry_rate,
            threshold_critical=self.unhealthy_retry_rate,
            message=message,
            recommendation=(
                "Verifica disponibilidad del proveedor y "
                "considera fallback automático."
                if status
                in {
                    HealthStatus.DEGRADED,
                    HealthStatus.UNHEALTHY,
                }
                else ""
            ),
            severity=severity,
        )

    def _exhaustion_indicator(
        self,
        exhaustion_rate: float,
        exhausted_events: int,
    ) -> HealthIndicator:
        if (
            exhaustion_rate
            >= self.unhealthy_exhaustion_rate
        ):
            status = HealthStatus.UNHEALTHY
            severity = 95
            message = "El agotamiento de Retry es crítico."
        elif (
            exhaustion_rate
            >= self.degraded_exhaustion_rate
        ):
            status = HealthStatus.DEGRADED
            severity = 55
            message = "Se observan agotamientos de Retry."
        else:
            status = HealthStatus.HEALTHY
            severity = 0
            message = "El agotamiento de Retry es saludable."

        return HealthIndicator(
            indicator_id="retry_exhaustion_rate",
            name="Tasa de agotamiento de Retry",
            status=status,
            value=round(
                exhaustion_rate,
                2,
            ),
            unit="%",
            threshold_warning=(
                self.degraded_exhaustion_rate
            ),
            threshold_critical=(
                self.unhealthy_exhaustion_rate
            ),
            message=message,
            recommendation=(
                "Revisa cuotas, disponibilidad, backoff y "
                "proveedores alternativos."
                if exhausted_events > 0
                else ""
            ),
            severity=severity,
            critical=(
                status == HealthStatus.UNHEALTHY
            ),
        )

    def _http_indicator(
        self,
        http_counts: dict[str, int],
    ) -> HealthIndicator:
        observed = set(
            http_counts
        )
        critical_codes = {
            "401",
            "403",
            "429",
        }
        temporary_codes = {
            "408",
            "425",
            "500",
            "502",
            "503",
            "504",
        }

        if observed & critical_codes:
            status = HealthStatus.UNHEALTHY
            severity = 90
            message = (
                "Se detectaron errores HTTP críticos."
            )
        elif observed & temporary_codes:
            status = HealthStatus.DEGRADED
            severity = 50
            message = (
                "Se detectaron errores HTTP temporales."
            )
        else:
            status = HealthStatus.HEALTHY
            severity = 0
            message = (
                "No se detectaron códigos HTTP críticos."
            )

        return HealthIndicator(
            indicator_id="http_errors",
            name="Errores HTTP",
            status=status,
            value=dict(
                http_counts
            ),
            unit="events",
            message=message,
            recommendation=(
                "Revisa credenciales, cuota y salud "
                "del proveedor."
                if status != HealthStatus.HEALTHY
                else ""
            ),
            severity=severity,
            critical=(
                status == HealthStatus.UNHEALTHY
            ),
        )

    def _build_recommendations(
        self,
        report: RuntimeHealthReport,
    ) -> list[str]:
        recommendations: list[str] = []

        for indicator in report.indicators:
            if indicator.recommendation:
                recommendations.append(
                    indicator.recommendation
                )

        for component in report.components:
            for indicator in component.problem_indicators():
                if indicator.recommendation:
                    recommendations.append(
                        f"{component.component}: "
                        f"{indicator.recommendation}"
                    )

        if report.status == HealthStatus.HEALTHY:
            recommendations.append(
                "Mantener monitoreo continuo."
            )
        elif report.status == HealthStatus.DEGRADED:
            recommendations.append(
                "Revisar componentes degradados antes "
                "de aumentar el volumen."
            )
        elif report.status == HealthStatus.UNHEALTHY:
            recommendations.append(
                "Detener ejecuciones no esenciales y "
                "resolver indicadores críticos."
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

    def _count_status_codes(
        self,
        events: list[TelemetryEvent],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}

        for event in events:
            codes: list[int] = []
            if event.status_code is not None:
                codes.append(
                    event.status_code
                )
            codes.extend(
                attempt.status_code
                for attempt in event.attempts
                if attempt.status_code is not None
            )

            for code in codes:
                key = str(
                    code
                )
                counts[key] = counts.get(
                    key,
                    0,
                ) + 1

        return counts

    def _count_exception_types(
        self,
        events: list[TelemetryEvent],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}

        for event in events:
            exception_types: list[str] = []

            if event.exception_type:
                exception_types.append(
                    event.exception_type
                )

            exception_types.extend(
                attempt.exception_type
                for attempt in event.attempts
                if attempt.exception_type
            )

            for exception_type in exception_types:
                counts[exception_type] = counts.get(
                    exception_type,
                    0,
                ) + 1

        return counts

    def _contains_marker(
        self,
        event: TelemetryEvent,
        markers: tuple[str, ...],
    ) -> bool:
        text = " ".join(
            [
                event.message,
                *event.errors,
            ]
        ).lower()

        return any(
            marker in text
            for marker in markers
        )

    def _resolve_currency(
        self,
        events: list[TelemetryEvent],
    ) -> str:
        currencies = {
            str(
                event.currency or "USD"
            ).upper()
            for event in events
        }
        if len(currencies) == 1:
            return next(
                iter(
                    currencies
                )
            )
        return "USD"

    def _rate(
        self,
        numerator: int,
        denominator: int,
    ) -> float:
        if denominator <= 0:
            return 0.0

        return round(
            (
                numerator
                / denominator
            )
            * 100,
            2,
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

    def _non_negative_float(
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

        return max(
            number,
            0.0,
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

    def _new_report_id(
        self,
    ) -> str:
        return (
            "HEALTH-"
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

    def _base_metadata(
        self,
    ) -> dict[str, Any]:
        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
        }