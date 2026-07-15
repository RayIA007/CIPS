"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 061
Archivo  : telemetry_engine.py
Estado   : RELEASE
=========================================================

Registra, consulta y resume la telemetría de CIPS.

Responsabilidades:
- recibir TelemetryEvent;
- guardar eventos en formato JSON Lines;
- preservar un evento por línea;
- consultar eventos existentes;
- filtrar por proyecto, Stage, componente y resultado;
- reconstruir TelemetrySummary;
- guardar TELEMETRY_SUMMARY.json;
- tolerar líneas dañadas sin perder registros válidos;
- devolver EngineResult con metadata segura.

Este Engine NO:
- modifica contenido editorial;
- llama modelos de Inteligencia Artificial;
- controla el Pipeline;
- calcula precios reales de proveedores;
- sustituye MemoryEngine;
- elimina telemetría automáticamente.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from runtime_models import EngineResult
from telemetry_models import (
    TelemetryAttempt,
    TelemetryEvent,
    TelemetrySummary,
)


class TelemetryEngine:
    """
    Motor de persistencia y consulta de telemetría.

    Por defecto guarda los archivos dentro del proyecto:

        <proyecto>/03_TELEMETRIA/TELEMETRY.jsonl
        <proyecto>/03_TELEMETRIA/TELEMETRY_SUMMARY.json

    También admite una carpeta de salida explícita.
    """

    COMPONENT_NAME = "telemetry_engine"
    VERSION = "0.8"

    DEFAULT_DIRECTORY = "03_TELEMETRIA"
    EVENTS_FILENAME = "TELEMETRY.jsonl"
    SUMMARY_FILENAME = "TELEMETRY_SUMMARY.json"

    def execute(
        self,
        event: TelemetryEvent,
        project_path: Path | str | None = None,
        output_directory: Path | str | None = None,
        update_summary: bool = True,
    ) -> EngineResult:
        """
        Alias principal para registrar un evento.
        """

        return self.record_event(
            event=event,
            project_path=project_path,
            output_directory=output_directory,
            update_summary=update_summary,
        )

    def record_event(
        self,
        event: TelemetryEvent,
        project_path: Path | str | None = None,
        output_directory: Path | str | None = None,
        update_summary: bool = True,
    ) -> EngineResult:
        """
        Persiste un TelemetryEvent en JSON Lines.

        Si ``event_id`` o ``timestamp`` están vacíos, se generan
        automáticamente antes de escribir el evento.
        """

        try:
            validation = self._validate_event(
                event
            )

            if validation is not None:
                return validation

            telemetry_directory = (
                self._resolve_output_directory(
                    project_path=project_path,
                    output_directory=output_directory,
                )
            )

            telemetry_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._complete_event_identity(
                event
            )

            events_path = (
                telemetry_directory
                / self.EVENTS_FILENAME
            )

            self._append_json_line(
                events_path,
                event.to_dict(),
            )

            summary_result: EngineResult | None = None

            if update_summary:
                summary_result = self.rebuild_summary(
                    project_path=project_path,
                    output_directory=telemetry_directory,
                    scope="project",
                    scope_id=event.project_id,
                )

                if not summary_result.success:
                    return EngineResult.fail(
                        message=(
                            "El evento fue registrado, pero "
                            "no fue posible actualizar el resumen."
                        ),
                        errors=list(
                            summary_result.errors
                        ),
                        warnings=list(
                            summary_result.warnings
                        ),
                        metadata={
                            **self._base_metadata(
                                telemetry_directory
                            ),
                            "event_id": event.event_id,
                            "event_persisted": True,
                            "summary_updated": False,
                            "events_path": str(
                                events_path
                            ),
                        },
                    )

            metadata = {
                **self._base_metadata(
                    telemetry_directory
                ),
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "project_id": event.project_id,
                "component_recorded": event.component,
                "operation": event.operation,
                "stage": event.stage,
                "success": event.success,
                "events_path": str(
                    events_path
                ),
                "events_file_size_bytes": (
                    events_path.stat().st_size
                ),
                "summary_updated": bool(
                    update_summary
                ),
            }

            if (
                summary_result is not None
                and summary_result.success
            ):
                metadata[
                    "summary_path"
                ] = summary_result.metadata.get(
                    "summary_path",
                    "",
                )

                metadata[
                    "events_total"
                ] = summary_result.metadata.get(
                    "events_total",
                    0,
                )

            return EngineResult.ok(
                data=event,
                message=(
                    "Evento de telemetría registrado "
                    "correctamente."
                ),
                warnings=list(
                    event.warnings
                ),
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "Error inesperado en TelemetryEngine."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "exception_type": (
                        error.__class__.__name__
                    ),
                },
            )

    def record_from_dict(
        self,
        event_data: dict[str, Any],
        project_path: Path | str | None = None,
        output_directory: Path | str | None = None,
        update_summary: bool = True,
    ) -> EngineResult:
        """
        Construye y registra TelemetryEvent desde un diccionario.
        """

        try:
            event = self._event_from_dict(
                event_data
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "No fue posible construir "
                    "TelemetryEvent."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        return self.record_event(
            event=event,
            project_path=project_path,
            output_directory=output_directory,
            update_summary=update_summary,
        )

    def read_events(
        self,
        project_path: Path | str | None = None,
        output_directory: Path | str | None = None,
        project_id: str | None = None,
        stage: str | None = None,
        component: str | None = None,
        event_type: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> EngineResult:
        """
        Lee eventos válidos y aplica filtros opcionales.
        """

        try:
            telemetry_directory = (
                self._resolve_output_directory(
                    project_path=project_path,
                    output_directory=output_directory,
                )
            )

            events_path = (
                telemetry_directory
                / self.EVENTS_FILENAME
            )

            raw_events, warnings = (
                self._read_json_lines(
                    events_path
                )
            )

            filtered = [
                event_data
                for event_data in raw_events
                if self._matches_filters(
                    event_data=event_data,
                    project_id=project_id,
                    stage=stage,
                    component=component,
                    event_type=event_type,
                    success=success,
                )
            ]

            if newest_first:
                filtered.reverse()

            normalized_limit = self._normalize_limit(
                limit
            )

            if normalized_limit is not None:
                filtered = filtered[
                    :normalized_limit
                ]

            events = [
                self._event_from_dict(
                    event_data
                )
                for event_data in filtered
            ]

            return EngineResult.ok(
                data=events,
                message=(
                    "Eventos de telemetría consultados "
                    "correctamente."
                ),
                warnings=warnings,
                metadata={
                    **self._base_metadata(
                        telemetry_directory
                    ),
                    "events_path": str(
                        events_path
                    ),
                    "events_file_exists": (
                        events_path.exists()
                    ),
                    "events_read": len(
                        raw_events
                    ),
                    "events_returned": len(
                        events
                    ),
                    "filters": {
                        "project_id": (
                            project_id
                        ),
                        "stage": stage,
                        "component": component,
                        "event_type": event_type,
                        "success": success,
                        "limit": normalized_limit,
                        "newest_first": (
                            newest_first
                        ),
                    },
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "No fue posible consultar "
                    "la telemetría."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "exception_type": (
                        error.__class__.__name__
                    ),
                },
            )

    def build_summary(
        self,
        events: Iterable[TelemetryEvent],
        scope: str = "project",
        scope_id: str = "",
    ) -> TelemetrySummary:
        """
        Construye TelemetrySummary en memoria.
        """

        summary = TelemetrySummary(
            scope=str(
                scope or "project"
            ).strip().lower(),
            scope_id=str(
                scope_id or ""
            ).strip(),
        )

        for event in events:
            summary.register_event(
                event
            )

        summary.metadata.update(
            {
                "component": self.COMPONENT_NAME,
                "component_version": self.VERSION,
                "generated_at": self._utc_now(),
            }
        )

        return summary

    def rebuild_summary(
        self,
        project_path: Path | str | None = None,
        output_directory: Path | str | None = None,
        scope: str = "project",
        scope_id: str = "",
        project_id: str | None = None,
        stage: str | None = None,
        component: str | None = None,
        event_type: str | None = None,
        success: bool | None = None,
    ) -> EngineResult:
        """
        Reconstruye y guarda TELEMETRY_SUMMARY.json.
        """

        try:
            telemetry_directory = (
                self._resolve_output_directory(
                    project_path=project_path,
                    output_directory=output_directory,
                )
            )

            telemetry_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            read_result = self.read_events(
                project_path=project_path,
                output_directory=telemetry_directory,
                project_id=project_id,
                stage=stage,
                component=component,
                event_type=event_type,
                success=success,
            )

            if not read_result.success:
                return read_result

            events = read_result.data

            resolved_scope_id = str(
                scope_id
                or project_id
                or self._infer_scope_id(
                    events
                )
                or ""
            ).strip()

            summary = self.build_summary(
                events=events,
                scope=scope,
                scope_id=resolved_scope_id,
            )

            summary_path = (
                telemetry_directory
                / self.SUMMARY_FILENAME
            )

            self._write_json_atomic(
                summary_path,
                summary.to_dict(),
            )

            return EngineResult.ok(
                data=summary,
                message=(
                    "Resumen de telemetría "
                    "reconstruido correctamente."
                ),
                warnings=list(
                    read_result.warnings
                ),
                metadata={
                    **self._base_metadata(
                        telemetry_directory
                    ),
                    "summary_path": str(
                        summary_path
                    ),
                    "summary_size_bytes": (
                        summary_path.stat().st_size
                    ),
                    "scope": summary.scope,
                    "scope_id": summary.scope_id,
                    "events_total": (
                        summary.events_total
                    ),
                    "successful_events": (
                        summary.successful_events
                    ),
                    "failed_events": (
                        summary.failed_events
                    ),
                    "success_rate": (
                        summary.success_rate
                    ),
                    "total_tokens": (
                        summary.total_tokens
                    ),
                    "retry_count": (
                        summary.retry_count
                    ),
                    "exhausted_events": (
                        summary.exhausted_events
                    ),
                    "recovered_events": (
                        summary.recovered_events
                    ),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "No fue posible reconstruir "
                    "el resumen de telemetría."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "exception_type": (
                        error.__class__.__name__
                    ),
                },
            )

    def load_summary(
        self,
        project_path: Path | str | None = None,
        output_directory: Path | str | None = None,
    ) -> EngineResult:
        """
        Lee TELEMETRY_SUMMARY.json.
        """

        try:
            telemetry_directory = (
                self._resolve_output_directory(
                    project_path=project_path,
                    output_directory=output_directory,
                )
            )

            summary_path = (
                telemetry_directory
                / self.SUMMARY_FILENAME
            )

            if not summary_path.exists():
                return EngineResult.fail(
                    message=(
                        "No existe un resumen "
                        "de telemetría."
                    ),
                    errors=[
                        str(summary_path)
                    ],
                    metadata={
                        **self._base_metadata(
                            telemetry_directory
                        ),
                        "summary_path": str(
                            summary_path
                        ),
                    },
                )

            data = json.loads(
                summary_path.read_text(
                    encoding="utf-8"
                )
            )

            summary = TelemetrySummary(
                **data
            )

            return EngineResult.ok(
                data=summary,
                message=(
                    "Resumen de telemetría "
                    "cargado correctamente."
                ),
                metadata={
                    **self._base_metadata(
                        telemetry_directory
                    ),
                    "summary_path": str(
                        summary_path
                    ),
                    "events_total": (
                        summary.events_total
                    ),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message=(
                    "No fue posible cargar "
                    "el resumen de telemetría."
                ),
                errors=[
                    str(error)
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                    "exception_type": (
                        error.__class__.__name__
                    ),
                },
            )

    def count_events(
        self,
        project_path: Path | str | None = None,
        output_directory: Path | str | None = None,
    ) -> EngineResult:
        """
        Cuenta eventos válidos sin reconstruir el resumen.
        """

        read_result = self.read_events(
            project_path=project_path,
            output_directory=output_directory,
        )

        if not read_result.success:
            return read_result

        return EngineResult.ok(
            data=len(
                read_result.data
            ),
            message=(
                "Eventos de telemetría contados "
                "correctamente."
            ),
            warnings=list(
                read_result.warnings
            ),
            metadata=dict(
                read_result.metadata
            ),
        )

    def _validate_event(
        self,
        event: TelemetryEvent,
    ) -> EngineResult | None:
        """
        Valida los campos mínimos del evento.
        """

        if event is None:
            return EngineResult.fail(
                message=(
                    "No se recibió TelemetryEvent."
                ),
                errors=[
                    "event es None."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        if not isinstance(
            event,
            TelemetryEvent,
        ):
            return EngineResult.fail(
                message=(
                    "TelemetryEngine requiere "
                    "TelemetryEvent."
                ),
                errors=[
                    "Tipo recibido: "
                    f"{type(event).__name__}."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        missing_fields: list[str] = []

        if not event.project_id:
            missing_fields.append(
                "project_id"
            )

        if not event.component:
            missing_fields.append(
                "component"
            )

        if not event.operation:
            missing_fields.append(
                "operation"
            )

        if missing_fields:
            return EngineResult.fail(
                message=(
                    "TelemetryEvent no contiene "
                    "todos los campos requeridos."
                ),
                errors=[
                    "Campos faltantes: "
                    + ", ".join(
                        missing_fields
                    )
                    + "."
                ],
                metadata={
                    "component": self.COMPONENT_NAME,
                },
            )

        return None

    def _resolve_output_directory(
        self,
        project_path: Path | str | None,
        output_directory: Path | str | None,
    ) -> Path:
        """
        Resuelve la carpeta de telemetría.
        """

        if output_directory is not None:
            path = Path(
                output_directory
            ).expanduser()

            if not path.is_absolute():
                if project_path is None:
                    raise ValueError(
                        "Una carpeta relativa requiere "
                        "project_path."
                    )

                path = (
                    Path(
                        project_path
                    ).expanduser()
                    / path
                )

            return path.resolve()

        if project_path is None:
            raise ValueError(
                "Se requiere project_path u "
                "output_directory."
            )

        return (
            Path(
                project_path
            ).expanduser().resolve()
            / self.DEFAULT_DIRECTORY
        )

    def _complete_event_identity(
        self,
        event: TelemetryEvent,
    ) -> None:
        """
        Genera identificador y fecha cuando faltan.
        """

        if not event.event_id:
            event.event_id = (
                "TEL-"
                + uuid4().hex.upper()
            )

        if not event.timestamp:
            event.timestamp = self._utc_now()

    def _append_json_line(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        """
        Agrega una línea JSON completa y UTF-8.
        """

        serialized = json.dumps(
            self._make_serializable(
                payload
            ),
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
            sort_keys=False,
        )

        with path.open(
            mode="a",
            encoding="utf-8",
            newline="\n",
        ) as file:
            file.write(
                serialized
            )
            file.write(
                "\n"
            )
            file.flush()

    def _read_json_lines(
        self,
        path: Path,
    ) -> tuple[
        list[dict[str, Any]],
        list[str],
    ]:
        """
        Lee JSON Lines tolerando líneas vacías o dañadas.
        """

        if not path.exists():
            return [], []

        events: list[dict[str, Any]] = []
        warnings: list[str] = []

        with path.open(
            mode="r",
            encoding="utf-8",
        ) as file:
            for line_number, raw_line in enumerate(
                file,
                start=1,
            ):
                line = raw_line.strip()

                if not line:
                    continue

                try:
                    payload = json.loads(
                        line
                    )

                except json.JSONDecodeError as error:
                    warnings.append(
                        "Línea de telemetría inválida "
                        f"{line_number}: {error.msg}."
                    )
                    continue

                if not isinstance(
                    payload,
                    dict,
                ):
                    warnings.append(
                        "Línea de telemetría ignorada "
                        f"{line_number}: no es objeto JSON."
                    )
                    continue

                events.append(
                    payload
                )

        return events, warnings

    def _write_json_atomic(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> None:
        """
        Guarda JSON mediante archivo temporal.
        """

        temporary_path = path.with_suffix(
            f"{path.suffix}.tmp"
        )

        serialized = json.dumps(
            self._make_serializable(
                payload
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )

        temporary_path.write_text(
            serialized + "\n",
            encoding="utf-8",
        )

        temporary_path.replace(
            path
        )

    def _event_from_dict(
        self,
        event_data: dict[str, Any],
    ) -> TelemetryEvent:
        """
        Construye TelemetryEvent desde JSON o diccionario.
        """

        if not isinstance(
            event_data,
            dict,
        ):
            raise TypeError(
                "event_data debe ser dict."
            )

        allowed_fields = set(
            TelemetryEvent.__dataclass_fields__
        )

        filtered_data = {
            key: value
            for key, value in event_data.items()
            if key in allowed_fields
        }

        attempts = filtered_data.get(
            "attempts",
            [],
        )

        if not isinstance(
            attempts,
            list,
        ):
            attempts = []

        filtered_data[
            "attempts"
        ] = [
            attempt
            if isinstance(
                attempt,
                TelemetryAttempt,
            )
            else TelemetryAttempt(
                attempt_number=attempt.get(
                    "attempt_number",
                    1,
                ),
                success=attempt.get(
                    "success",
                    False,
                ),
                duration_seconds=attempt.get(
                    "duration_seconds",
                    0.0,
                ),
                delay_seconds=attempt.get(
                    "delay_seconds",
                    0.0,
                ),
                retryable=attempt.get(
                    "retryable",
                    False,
                ),
                status_code=attempt.get(
                    "status_code"
                ),
                exception_type=attempt.get(
                    "exception_type",
                    "",
                ),
                matched_rule=attempt.get(
                    "matched_rule",
                    "",
                ),
                message=attempt.get(
                    "message",
                    "",
                ),
                metadata=attempt.get(
                    "metadata",
                    {},
                ),
            )
            for attempt in attempts
            if isinstance(
                attempt,
                (
                    dict,
                    TelemetryAttempt,
                ),
            )
        ]

        required_defaults = {
            "event_id": "",
            "timestamp": "",
            "project_id": "",
            "component": "",
            "operation": "",
        }

        for key, value in required_defaults.items():
            filtered_data.setdefault(
                key,
                value,
            )

        return TelemetryEvent(
            **filtered_data
        )

    def _matches_filters(
        self,
        event_data: dict[str, Any],
        project_id: str | None,
        stage: str | None,
        component: str | None,
        event_type: str | None,
        success: bool | None,
    ) -> bool:
        """
        Aplica filtros exactos normalizados.
        """

        comparisons = (
            (
                project_id,
                event_data.get(
                    "project_id",
                    "",
                ),
            ),
            (
                stage,
                event_data.get(
                    "stage",
                    "",
                ),
            ),
            (
                component,
                event_data.get(
                    "component",
                    "",
                ),
            ),
            (
                event_type,
                event_data.get(
                    "event_type",
                    "",
                ),
            ),
        )

        for expected, actual in comparisons:
            if expected is None:
                continue

            if str(
                expected
            ).strip().lower() != str(
                actual
            ).strip().lower():
                return False

        if (
            success is not None
            and bool(
                event_data.get(
                    "success",
                    False,
                )
            )
            is not bool(success)
        ):
            return False

        return True

    def _normalize_limit(
        self,
        value: Any,
    ) -> int | None:
        """
        Normaliza límite de consulta.
        """

        if value in (
            None,
            "",
        ):
            return None

        try:
            limit = int(
                value
            )

        except (TypeError, ValueError):
            return None

        return (
            limit
            if limit > 0
            else None
        )

    def _infer_scope_id(
        self,
        events: list[TelemetryEvent],
    ) -> str:
        """
        Infiere project_id cuando todos los eventos coinciden.
        """

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

    def _make_serializable(
        self,
        value: Any,
    ) -> Any:
        """
        Convierte valores comunes a estructuras JSON.
        """

        if value is None:
            return None

        if isinstance(
            value,
            Path,
        ):
            return str(value)

        if isinstance(
            value,
            TelemetryEvent,
        ):
            return value.to_dict()

        if isinstance(
            value,
            TelemetryAttempt,
        ):
            return value.to_dict()

        if isinstance(
            value,
            TelemetrySummary,
        ):
            return value.to_dict()

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): self._make_serializable(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            return [
                self._make_serializable(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        return str(
            value
        )

    def _base_metadata(
        self,
        telemetry_directory: Path,
    ) -> dict[str, Any]:
        """
        Construye metadata común.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "telemetry_directory": str(
                telemetry_directory
            ),
            "events_filename": (
                self.EVENTS_FILENAME
            ),
            "summary_filename": (
                self.SUMMARY_FILENAME
            ),
            "storage_format": "jsonl",
        }

    def _utc_now(
        self,
    ) -> str:
        """
        Devuelve fecha UTC ISO-8601.
        """

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

    def get_component_info(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve información pública del componente.
        """

        return {
            "component": self.COMPONENT_NAME,
            "version": self.VERSION,
            "default_directory": (
                self.DEFAULT_DIRECTORY
            ),
            "events_file": self.EVENTS_FILENAME,
            "summary_file": (
                self.SUMMARY_FILENAME
            ),
            "storage_format": "jsonl",
            "writes_files": True,
            "supports_filters": True,
            "tolerates_invalid_lines": True,
            "updates_summary": True,
            "provider_agnostic": True,
            "next_step": (
                "pipeline_engine_integration"
            ),
        }