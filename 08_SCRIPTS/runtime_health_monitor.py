"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 066
Archivo  : runtime_health_monitor.py
Estado   : RELEASE
=========================================================

Orquesta el Runtime Health Monitor de CIPS.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from health_analyzer import HealthAnalyzer
from health_models import (
    ComponentHealth,
    HealthIndicator,
    HealthStatus,
    RuntimeHealthReport,
)
from runtime_models import EngineResult
from telemetry_engine import TelemetryEngine


class RuntimeHealthMonitor:
    """Coordina lectura, análisis y persistencia de salud."""

    COMPONENT_NAME = "runtime_health_monitor"
    VERSION = "0.8"

    HEALTH_JSON_FILENAME = "RUNTIME_HEALTH.json"
    HEALTH_MARKDOWN_FILENAME = "RUNTIME_HEALTH.md"

    def __init__(
        self,
        telemetry_engine: TelemetryEngine | None = None,
        health_analyzer: HealthAnalyzer | None = None,
    ) -> None:
        self.telemetry_engine = telemetry_engine or TelemetryEngine()
        self.health_analyzer = health_analyzer or HealthAnalyzer()

    def execute(
        self,
        project_path: Path | str,
        project_id: str | None = None,
        scope: str = "project",
        output_directory: Path | str | None = None,
        persist: bool = True,
    ) -> EngineResult:
        """Genera el informe de salud desde la telemetría existente."""

        try:
            resolved_project_path = Path(project_path).expanduser().resolve()
            telemetry_directory = self._resolve_output_directory(
                project_path=resolved_project_path,
                output_directory=output_directory,
            )

            read_result = self.telemetry_engine.read_events(
                project_path=resolved_project_path,
                output_directory=telemetry_directory,
                project_id=project_id,
            )

            if not read_result.success:
                return EngineResult.fail(
                    message="No fue posible leer la telemetría del proyecto.",
                    errors=list(read_result.errors),
                    warnings=list(read_result.warnings),
                    metadata={
                        **self._base_metadata(
                            resolved_project_path,
                            telemetry_directory,
                        ),
                        **dict(read_result.metadata),
                    },
                )

            events = list(read_result.data)
            resolved_project_id = str(
                project_id
                or self._infer_project_id(events)
                or resolved_project_path.name
            ).strip()

            report = self.health_analyzer.analyze(
                events=events,
                project_id=resolved_project_id,
                scope=scope,
            )

            report.metadata.update(
                {
                    "project_path": str(resolved_project_path),
                    "telemetry_directory": str(telemetry_directory),
                    "events_file": str(
                        telemetry_directory
                        / self.telemetry_engine.EVENTS_FILENAME
                    ),
                    "monitor_component": self.COMPONENT_NAME,
                    "monitor_version": self.VERSION,
                }
            )

            json_path = telemetry_directory / self.HEALTH_JSON_FILENAME
            markdown_path = (
                telemetry_directory / self.HEALTH_MARKDOWN_FILENAME
            )

            if persist:
                telemetry_directory.mkdir(parents=True, exist_ok=True)
                self._write_json_atomic(json_path, report.to_dict())
                self._write_text_atomic(
                    markdown_path,
                    self._render_markdown(report),
                )

            warnings = list(read_result.warnings)
            if report.status == HealthStatus.UNKNOWN:
                warnings.append(
                    "La salud del Runtime es UNKNOWN por falta de "
                    "telemetría suficiente."
                )

            return EngineResult.ok(
                data=report,
                message="Informe de salud del Runtime generado correctamente.",
                warnings=warnings,
                metadata={
                    **self._base_metadata(
                        resolved_project_path,
                        telemetry_directory,
                    ),
                    "project_id": report.project_id,
                    "status": report.status.value,
                    "events_total": report.events_total,
                    "successful_events": report.successful_events,
                    "failed_events": report.failed_events,
                    "success_rate": report.success_rate,
                    "retry_count": report.retry_count,
                    "exhausted_events": report.exhausted_events,
                    "components_count": len(report.components),
                    "indicators_count": len(report.indicators),
                    "recommendations_count": len(report.recommendations),
                    "persisted": bool(persist),
                    "json_path": str(json_path) if persist else "",
                    "markdown_path": str(markdown_path) if persist else "",
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en RuntimeHealthMonitor.",
                errors=[str(error)],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "exception_type": error.__class__.__name__,
                },
            )

    def load_report(
        self,
        project_path: Path | str,
        output_directory: Path | str | None = None,
    ) -> EngineResult:
        """Carga RUNTIME_HEALTH.json desde disco."""

        try:
            resolved_project_path = Path(project_path).expanduser().resolve()
            telemetry_directory = self._resolve_output_directory(
                project_path=resolved_project_path,
                output_directory=output_directory,
            )
            json_path = telemetry_directory / self.HEALTH_JSON_FILENAME

            if not json_path.exists():
                return EngineResult.fail(
                    message="No existe un informe de salud persistido.",
                    errors=[str(json_path)],
                    metadata={
                        **self._base_metadata(
                            resolved_project_path,
                            telemetry_directory,
                        ),
                        "json_path": str(json_path),
                    },
                )

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            report = self._report_from_dict(payload)

            return EngineResult.ok(
                data=report,
                message="Informe de salud cargado correctamente.",
                metadata={
                    **self._base_metadata(
                        resolved_project_path,
                        telemetry_directory,
                    ),
                    "json_path": str(json_path),
                    "status": report.status.value,
                    "events_total": report.events_total,
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message="No fue posible cargar el informe de salud.",
                errors=[str(error)],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "exception_type": error.__class__.__name__,
                },
            )

    def get_component_info(self) -> dict[str, Any]:
        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "reads_telemetry": True,
            "writes_files": True,
            "json_output": self.HEALTH_JSON_FILENAME,
            "markdown_output": self.HEALTH_MARKDOWN_FILENAME,
            "provider_agnostic": True,
            "uses_health_analyzer": True,
            "uses_telemetry_engine": True,
            "next_component": "runtime_health_smoke_test",
        }

    def _write_json_atomic(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        temporary_path.write_text(serialized + "\n", encoding="utf-8")
        temporary_path.replace(path)

    def _write_text_atomic(self, path: Path, content: str) -> None:
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        temporary_path.write_text(
            content.rstrip() + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)

    def _render_markdown(self, report: RuntimeHealthReport) -> str:
        lines: list[str] = [
            "# CIPS Runtime Health Report",
            "",
            f"- **Report ID:** `{report.report_id}`",
            f"- **Generated at:** `{report.generated_at}`",
            f"- **Project:** `{report.project_id}`",
            f"- **Scope:** `{report.scope}`",
            f"- **Status:** **{report.status.value}**",
            "",
            "## Summary",
            "",
            f"- Events: **{report.events_total}**",
            f"- Successful: **{report.successful_events}**",
            f"- Failed: **{report.failed_events}**",
            f"- Success rate: **{report.success_rate}%**",
            f"- Failure rate: **{report.failure_rate}%**",
            f"- Average duration: **{report.average_duration_seconds} s**",
            f"- Total duration: **{report.total_duration_seconds} s**",
            f"- Total tokens: **{report.total_tokens}**",
            f"- Retry count: **{report.retry_count}**",
            f"- Exhausted events: **{report.exhausted_events}**",
            f"- Recovered events: **{report.recovered_events}**",
            "",
            "## Global indicators",
            "",
        ]

        if report.indicators:
            for indicator in report.indicators:
                lines.extend(self._render_indicator(indicator))
        else:
            lines.append("_No global indicators available._")

        lines.extend(["", "## Components", ""])

        if report.components:
            for component in sorted(
                report.components,
                key=self._component_sort_key,
            ):
                lines.extend(self._render_component(component))
        else:
            lines.append("_No component health data available._")

        lines.extend(["", "## Recommendations", ""])

        if report.recommendations:
            lines.extend(
                f"- {recommendation}"
                for recommendation in report.recommendations
            )
        else:
            lines.append("_No recommendations._")

        if report.warnings:
            lines.extend(["", "## Warnings", ""])
            lines.extend(f"- {warning}" for warning in report.warnings)

        if report.errors:
            lines.extend(["", "## Errors", ""])
            lines.extend(f"- {error}" for error in report.errors)

        return "\n".join(lines)

    def _render_indicator(
        self,
        indicator: HealthIndicator,
    ) -> list[str]:
        lines = [
            f"### {indicator.name} — {indicator.status.value}",
            "",
            f"- ID: `{indicator.indicator_id}`",
            f"- Value: `{indicator.value}`",
        ]

        if indicator.unit:
            lines.append(f"- Unit: `{indicator.unit}`")
        if indicator.message:
            lines.append(f"- Message: {indicator.message}")
        if indicator.recommendation:
            lines.append(
                f"- Recommendation: {indicator.recommendation}"
            )

        lines.append("")
        return lines

    def _render_component(
        self,
        component: ComponentHealth,
    ) -> list[str]:
        lines = [
            f"### {component.component} — {component.status.value}",
            "",
            f"- Category: `{component.category}`",
            f"- Events: **{component.events_total}**",
            f"- Success rate: **{component.success_rate}%**",
            f"- Failure rate: **{component.failure_rate}%**",
            (
                "- Average duration: "
                f"**{component.average_duration_seconds} s**"
            ),
            (
                "- Maximum duration: "
                f"**{component.maximum_duration_seconds} s**"
            ),
            f"- Retry count: **{component.retry_count}**",
            f"- Exhausted events: **{component.exhausted_events}**",
            "",
        ]

        problem_indicators = component.problem_indicators()
        if problem_indicators:
            lines.extend(["**Problem indicators:**", ""])
            lines.extend(
                f"- {indicator.name}: {indicator.status.value}"
                for indicator in problem_indicators
            )
            lines.append("")

        return lines

    def _report_from_dict(
        self,
        payload: dict[str, Any],
    ) -> RuntimeHealthReport:
        if not isinstance(payload, dict):
            raise TypeError("El informe debe ser un objeto JSON.")

        components = [
            ComponentHealth(**component)
            for component in payload.get("components", [])
            if isinstance(component, dict)
        ]
        indicators = [
            HealthIndicator(**indicator)
            for indicator in payload.get("indicators", [])
            if isinstance(indicator, dict)
        ]

        allowed_fields = set(RuntimeHealthReport.__dataclass_fields__)
        data = {
            key: value
            for key, value in payload.items()
            if key in allowed_fields
        }
        data["components"] = components
        data["indicators"] = indicators
        return RuntimeHealthReport(**data)

    def _resolve_output_directory(
        self,
        project_path: Path,
        output_directory: Path | str | None,
    ) -> Path:
        if output_directory is not None:
            path = Path(output_directory).expanduser()
            if not path.is_absolute():
                path = project_path / path
            return path.resolve()

        return project_path / self.telemetry_engine.DEFAULT_DIRECTORY

    def _infer_project_id(self, events: list[Any]) -> str:
        project_ids = {
            str(getattr(event, "project_id", "") or "").strip()
            for event in events
        }
        project_ids.discard("")

        if len(project_ids) == 1:
            return next(iter(project_ids))
        return ""

    def _component_sort_key(
        self,
        component: ComponentHealth,
    ) -> tuple[int, float, str]:
        priority = {
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNKNOWN: 2,
            HealthStatus.HEALTHY: 3,
        }
        return (
            priority.get(component.status, 4),
            -component.failure_rate,
            component.component,
        )

    def _base_metadata(
        self,
        project_path: Path,
        telemetry_directory: Path,
    ) -> dict[str, Any]:
        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "project_path": str(project_path),
            "telemetry_directory": str(telemetry_directory),
            "health_json_filename": self.HEALTH_JSON_FILENAME,
            "health_markdown_filename": self.HEALTH_MARKDOWN_FILENAME,
        }

    def _utc_now(self) -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )