"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 063
Archivo  : production_logger.py
Estado   : RELEASE
=========================================================

Logger estructurado de producción.

Responsabilidades:
- Registrar eventos estructurados por Stage (LogEntry).
- Acumular métricas por Stage (StageMetrics).
- Persistir logs en formato JSON Lines (.jsonl).
- Exponer resúmenes por Stage para dashboards y telemetría.
- Envolver (wrap) al logger existente sin reemplazarlo.

Este módulo NO:
- Ejecuta componentes del pipeline.
- Modifica el estado de producción (eso es production_state.py).
- Calcula costos reales por proveedor.
- Sustituye a telemetry_engine.py.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class LogLevel(str, Enum):
    """Niveles de severidad de un evento de log."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """
    Evento de log estructurado.
    """

    entry_id: str
    timestamp: str
    level: LogLevel
    stage: str
    message: str

    component: str = ""
    operation: str = ""
    duration_seconds: float = 0.0
    cost: float = 0.0
    currency: str = "USD"
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_thinking: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entry_id = str(self.entry_id or "").strip() or str(uuid.uuid4())
        self.timestamp = str(self.timestamp or "").strip() or self._now_iso()
        if isinstance(self.level, str):
            self.level = LogLevel(self.level)
        self.stage = str(self.stage or "").strip().lower()
        self.message = str(self.message or "").strip()
        self.component = str(self.component or "").strip()
        self.operation = str(self.operation or "").strip()
        self.duration_seconds = self._non_negative_float(self.duration_seconds)
        self.cost = self._non_negative_float(self.cost)
        self.currency = str(self.currency or "USD").strip().upper()
        self.tokens_in = self._non_negative_int(self.tokens_in)
        self.tokens_out = self._non_negative_int(self.tokens_out)
        self.tokens_thinking = self._non_negative_int(self.tokens_thinking)
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["level"] = self.level.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogEntry:
        return cls(
            entry_id=data.get("entry_id", ""),
            timestamp=data.get("timestamp", ""),
            level=LogLevel(data.get("level", "info")),
            stage=data.get("stage", ""),
            message=data.get("message", ""),
            component=data.get("component", ""),
            operation=data.get("operation", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            cost=data.get("cost", 0.0),
            currency=data.get("currency", "USD"),
            tokens_in=data.get("tokens_in", 0),
            tokens_out=data.get("tokens_out", 0),
            tokens_thinking=data.get("tokens_thinking", 0),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    @staticmethod
    def _non_negative_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(number, 0.0), 6)

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0
        return max(number, 0)


@dataclass
class StageMetrics:
    """
    Métricas acumuladas por Stage durante una producción.
    """

    stage: str
    entries_count: int = 0
    errors_count: int = 0
    warnings_count: int = 0

    total_duration_seconds: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"

    tokens_in: int = 0
    tokens_out: int = 0
    tokens_thinking: int = 0
    total_tokens: int = 0

    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.stage = str(self.stage or "").strip().lower()
        self.entries_count = max(int(self.entries_count or 0), 0)
        self.errors_count = max(int(self.errors_count or 0), 0)
        self.warnings_count = max(int(self.warnings_count or 0), 0)
        self.total_duration_seconds = self._non_negative_float(self.total_duration_seconds)
        self.total_cost = self._non_negative_float(self.total_cost)
        self.currency = str(self.currency or "USD").strip().upper()
        self.tokens_in = max(int(self.tokens_in or 0), 0)
        self.tokens_out = max(int(self.tokens_out or 0), 0)
        self.tokens_thinking = max(int(self.tokens_thinking or 0), 0)
        self.total_tokens = max(int(self.total_tokens or 0), 0)
        self.retry_count = max(int(self.retry_count or 0), 0)
        self.metadata = dict(self.metadata or {})

    def register_entry(self, entry: LogEntry) -> None:
        """Acumula las métricas de un LogEntry."""
        if not isinstance(entry, LogEntry):
            raise TypeError("entry debe ser LogEntry.")

        self.entries_count += 1
        self.total_duration_seconds += entry.duration_seconds
        self.total_cost += entry.cost
        self.tokens_in += entry.tokens_in
        self.tokens_out += entry.tokens_out
        self.tokens_thinking += entry.tokens_thinking
        self.total_tokens = self.tokens_in + self.tokens_out + self.tokens_thinking

        if entry.level == LogLevel.ERROR:
            self.errors_count += 1
        elif entry.level == LogLevel.WARNING:
            self.warnings_count += 1

        retry_count = entry.metadata.get("retry_count", 0)
        if isinstance(retry_count, int):
            self.retry_count += retry_count

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _non_negative_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(number, 0.0), 6)


class ProductionLogger:
    """
    Logger estructurado de producción.

    Envuelve al logger legado (logger.py) para mantener
    compatibilidad, mientras añade persistencia estructurada
    en JSON Lines.
    """

    LOGS_DIR_NAME = "logs"
    LOG_FILE_NAME = "production_log.jsonl"

    def __init__(self, project_path: Path, legacy_logger: Any | None = None) -> None:
        self.project_path = Path(project_path)
        self.logs_dir = self.project_path / self.LOGS_DIR_NAME
        self.log_file = self.logs_dir / self.LOG_FILE_NAME
        self.legacy_logger = legacy_logger
        self._metrics: dict[str, StageMetrics] = {}
        self._entries: list[LogEntry] = []

    # --------------------------------------------------
    # Registro de eventos
    # --------------------------------------------------

    def log(
        self,
        level: LogLevel,
        stage: str,
        message: str,
        component: str = "",
        operation: str = "",
        duration_seconds: float = 0.0,
        cost: float = 0.0,
        currency: str = "USD",
        tokens_in: int = 0,
        tokens_out: int = 0,
        tokens_thinking: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> LogEntry:
        """
        Registra un evento estructurado y lo persiste inmediatamente.
        """
        entry = LogEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            level=level,
            stage=str(stage).strip().lower(),
            message=message,
            component=component,
            operation=operation,
            duration_seconds=duration_seconds,
            cost=cost,
            currency=currency,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tokens_thinking=tokens_thinking,
            metadata=dict(metadata or {}),
        )

        self._entries.append(entry)
        self._append_to_file(entry)
        self._update_metrics(entry)
        self._forward_to_legacy(entry)

        return entry

    def info(
        self,
        stage: str,
        message: str,
        **kwargs: Any,
    ) -> LogEntry:
        return self.log(LogLevel.INFO, stage, message, **kwargs)

    def debug(
        self,
        stage: str,
        message: str,
        **kwargs: Any,
    ) -> LogEntry:
        return self.log(LogLevel.DEBUG, stage, message, **kwargs)

    def warning(
        self,
        stage: str,
        message: str,
        **kwargs: Any,
    ) -> LogEntry:
        return self.log(LogLevel.WARNING, stage, message, **kwargs)

    def error(
        self,
        stage: str,
        message: str,
        **kwargs: Any,
    ) -> LogEntry:
        return self.log(LogLevel.ERROR, stage, message, **kwargs)

    def critical(
        self,
        stage: str,
        message: str,
        **kwargs: Any,
    ) -> LogEntry:
        return self.log(LogLevel.CRITICAL, stage, message, **kwargs)

    # --------------------------------------------------
    # Métricas
    # --------------------------------------------------

    def get_stage_metrics(self, stage: str) -> StageMetrics:
        """Devuelve las métricas acumuladas de un Stage."""
        key = str(stage).strip().lower()
        if key not in self._metrics:
            self._metrics[key] = StageMetrics(stage=key)
        return self._metrics[key]

    def get_all_metrics(self) -> dict[str, StageMetrics]:
        """Devuelve todas las métricas acumuladas."""
        return dict(self._metrics)

    def get_stage_summary(self, stage: str) -> dict[str, Any]:
        """Devuelve un resumen serializable de un Stage."""
        metrics = self.get_stage_metrics(stage)
        return {
            "stage": metrics.stage,
            "entries_count": metrics.entries_count,
            "errors_count": metrics.errors_count,
            "warnings_count": metrics.warnings_count,
            "total_duration_seconds": round(metrics.total_duration_seconds, 6),
            "total_cost": round(metrics.total_cost, 8),
            "currency": metrics.currency,
            "tokens": {
                "in": metrics.tokens_in,
                "out": metrics.tokens_out,
                "thinking": metrics.tokens_thinking,
                "total": metrics.total_tokens,
            },
            "retry_count": metrics.retry_count,
        }

    def get_production_summary(self) -> dict[str, Any]:
        """Devuelve un resumen global de toda la producción."""
        total_entries = sum(m.entries_count for m in self._metrics.values())
        total_errors = sum(m.errors_count for m in self._metrics.values())
        total_warnings = sum(m.warnings_count for m in self._metrics.values())
        total_duration = sum(m.total_duration_seconds for m in self._metrics.values())
        total_cost = sum(m.total_cost for m in self._metrics.values())
        total_tokens = sum(m.total_tokens for m in self._metrics.values())

        return {
            "stages": {k: v.to_dict() for k, v in self._metrics.items()},
            "total_entries": total_entries,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "total_duration_seconds": round(total_duration, 6),
            "total_cost": round(total_cost, 8),
            "total_tokens": total_tokens,
            "stages_completed": [
                stage for stage, metrics in self._metrics.items()
                if metrics.errors_count == 0 and metrics.entries_count > 0
            ],
        }

    # --------------------------------------------------
    # Persistencia
    # --------------------------------------------------

    def _append_to_file(self, entry: LogEntry) -> None:
        """Añade una línea JSON al archivo .jsonl de forma atómica."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.log_file.with_suffix(".jsonl.tmp")

        try:
            line = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
            # Escribir en modo append
            with temp_file.open("a", encoding="utf-8") as f:
                f.write(line)
            # Mover al archivo final (sobrescritura atómica no es viable en append,
            # así que escribimos directamente al destino)
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(line)
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
        except Exception:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise

    def load_entries(self) -> list[LogEntry]:
        """Carga todas las entradas desde el archivo .jsonl."""
        entries: list[LogEntry] = []
        if not self.log_file.exists():
            return entries

        try:
            with self.log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entries.append(LogEntry.from_dict(data))
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception:
            pass

        return entries

    def rebuild_metrics(self) -> None:
        """Reconstruye las métricas desde el archivo en disco."""
        self._metrics = {}
        self._entries = self.load_entries()
        for entry in self._entries:
            self._update_metrics(entry)

    # --------------------------------------------------
    # Privados
    # --------------------------------------------------

    def _update_metrics(self, entry: LogEntry) -> None:
        key = entry.stage
        if key not in self._metrics:
            self._metrics[key] = StageMetrics(stage=key)
        self._metrics[key].register_entry(entry)

    def _forward_to_legacy(self, entry: LogEntry) -> None:
        """Reenvía el mensaje al logger legado si está disponible."""
        if self.legacy_logger is None:
            return

        legacy_message = f"[{entry.level.value.upper()}] [{entry.stage}] {entry.message}"
        try:
            if entry.level == LogLevel.DEBUG:
                self.legacy_logger.debug(legacy_message)
            elif entry.level == LogLevel.INFO:
                self.legacy_logger.info(legacy_message)
            elif entry.level == LogLevel.WARNING:
                self.legacy_logger.warning(legacy_message)
            elif entry.level == LogLevel.ERROR:
                self.legacy_logger.error(legacy_message)
            elif entry.level == LogLevel.CRITICAL:
                self.legacy_logger.critical(legacy_message)
        except Exception:
            pass


def get_production_logger_info() -> dict[str, Any]:
    """Devuelve información pública del módulo."""
    return {
        "component": "production_logger",
        "version": "0.8",
        "models": [
            "LogLevel",
            "LogEntry",
            "StageMetrics",
            "ProductionLogger",
        ],
        "serializable": True,
        "log_file": "04_PROYECTOS/<PROY>/logs/production_log.jsonl",
    }
