"""
=========================================================
Proyecto : CIPS
Release  : 0.8
Build    : 060
Archivo  : telemetry_models.py
Estado   : RELEASE
=========================================================

Define los contratos de datos del Telemetry Framework.

Responsabilidades:
- representar intentos individuales de ejecución;
- representar eventos de telemetría por componente o Stage;
- acumular métricas por proyecto;
- mantener estructuras serializables;
- ofrecer métodos seguros de agregación;
- desacoplar observabilidad del Runtime principal.

Este módulo NO:
- escribe archivos;
- ejecuta componentes;
- modifica proyectos;
- llama modelos de Inteligencia Artificial;
- calcula costos reales por proveedor;
- sustituye a runtime_models.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TelemetryAttempt:
    """
    Representa un intento individual dentro de una operación.

    Se utiliza principalmente para registrar intentos del
    RetryEngine, aunque también puede representar cualquier
    operación repetida dentro del Runtime.
    """

    attempt_number: int
    success: bool

    duration_seconds: float = 0.0
    delay_seconds: float = 0.0

    retryable: bool = False
    status_code: int | None = None
    exception_type: str = ""
    matched_rule: str = ""
    message: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.attempt_number = self._positive_int(
            self.attempt_number,
            default=1,
        )
        self.success = bool(self.success)
        self.duration_seconds = self._non_negative_float(
            self.duration_seconds
        )
        self.delay_seconds = self._non_negative_float(
            self.delay_seconds
        )
        self.retryable = bool(self.retryable)
        self.status_code = self._status_code(self.status_code)
        self.exception_type = str(
            self.exception_type or ""
        ).strip()
        self.matched_rule = str(
            self.matched_rule or ""
        ).strip()
        self.message = str(self.message or "").strip()
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _positive_int(value: Any, default: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return number if number > 0 else default

    @staticmethod
    def _non_negative_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(number, 0.0), 3)

    @staticmethod
    def _status_code(value: Any) -> int | None:
        if value is None:
            return None
        try:
            code = int(value)
        except (TypeError, ValueError):
            return None
        return code if 100 <= code <= 599 else None


@dataclass
class TelemetryEvent:
    """
    Representa un evento de telemetría de CIPS.

    Un evento puede corresponder a una ejecución de Stage,
    llamada LLM, validación, finalización, exportación o fallo.
    """

    event_id: str
    timestamp: str
    project_id: str
    component: str
    operation: str

    stage: str = ""
    event_type: str = "execution"
    success: bool = False
    message: str = ""

    provider: str = ""
    model: str = ""
    thinking_level: str = ""

    duration_seconds: float = 0.0
    prompt_characters: int = 0
    response_characters: int = 0

    prompt_tokens: int = 0
    response_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    retry_enabled: bool = False
    retry_attempts: int = 0
    retry_count: int = 0
    retry_exhausted: bool = False
    succeeded_after_retry: bool = False

    status_code: int | None = None
    exception_type: str = ""

    validation_score: float | None = None
    validation_passing_score: float | None = None
    validation_approved: bool | None = None

    estimated_cost: float = 0.0
    currency: str = "USD"

    attempts: list[TelemetryAttempt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_id = str(self.event_id or "").strip()
        self.timestamp = str(self.timestamp or "").strip()
        self.project_id = str(self.project_id or "").strip()
        self.component = str(self.component or "").strip()
        self.operation = str(self.operation or "").strip()
        self.stage = str(self.stage or "").strip().lower()
        self.event_type = str(
            self.event_type or "execution"
        ).strip().lower()
        self.success = bool(self.success)
        self.message = str(self.message or "").strip()
        self.provider = str(self.provider or "").strip()
        self.model = str(self.model or "").strip()
        self.thinking_level = str(
            self.thinking_level or ""
        ).strip().lower()

        self.duration_seconds = self._non_negative_float(
            self.duration_seconds
        )
        self.prompt_characters = self._non_negative_int(
            self.prompt_characters
        )
        self.response_characters = self._non_negative_int(
            self.response_characters
        )
        self.prompt_tokens = self._non_negative_int(
            self.prompt_tokens
        )
        self.response_tokens = self._non_negative_int(
            self.response_tokens
        )
        self.thinking_tokens = self._non_negative_int(
            self.thinking_tokens
        )
        self.total_tokens = self._non_negative_int(
            self.total_tokens
        )

        if self.total_tokens == 0 and (
            self.prompt_tokens
            or self.response_tokens
            or self.thinking_tokens
        ):
            self.total_tokens = (
                self.prompt_tokens
                + self.response_tokens
                + self.thinking_tokens
            )

        self.retry_enabled = bool(self.retry_enabled)
        self.retry_attempts = self._non_negative_int(
            self.retry_attempts
        )
        self.retry_count = self._non_negative_int(
            self.retry_count
        )
        self.retry_exhausted = bool(self.retry_exhausted)
        self.succeeded_after_retry = bool(
            self.succeeded_after_retry
        )
        self.status_code = TelemetryAttempt._status_code(
            self.status_code
        )
        self.exception_type = str(
            self.exception_type or ""
        ).strip()

        self.validation_score = self._optional_float(
            self.validation_score
        )
        self.validation_passing_score = self._optional_float(
            self.validation_passing_score
        )
        if self.validation_approved is not None:
            self.validation_approved = bool(
                self.validation_approved
            )

        self.estimated_cost = self._non_negative_float(
            self.estimated_cost
        )
        self.currency = str(
            self.currency or "USD"
        ).strip().upper()

        normalized_attempts: list[TelemetryAttempt] = []
        for attempt in self.attempts:
            if isinstance(attempt, TelemetryAttempt):
                normalized_attempts.append(attempt)
            elif isinstance(attempt, dict):
                normalized_attempts.append(
                    TelemetryAttempt(
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
                        status_code=attempt.get("status_code"),
                        exception_type=attempt.get(
                            "exception_type",
                            "",
                        ),
                        matched_rule=attempt.get(
                            "matched_rule",
                            "",
                        ),
                        message=attempt.get("message", ""),
                        metadata=attempt.get("metadata", {}),
                    )
                )
        self.attempts = normalized_attempts
        self.warnings = [str(item) for item in self.warnings]
        self.errors = [str(item) for item in self.errors]
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attempts"] = [
            attempt.to_dict()
            for attempt in self.attempts
        ]
        return data

    def has_retry_activity(self) -> bool:
        return bool(
            self.retry_enabled
            or self.retry_attempts > 1
            or self.retry_count > 0
            or self.attempts
        )

    def has_validation_data(self) -> bool:
        return any(
            value is not None
            for value in (
                self.validation_score,
                self.validation_passing_score,
                self.validation_approved,
            )
        )

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0
        return max(number, 0)

    @staticmethod
    def _non_negative_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(number, 0.0), 6)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


@dataclass
class TelemetrySummary:
    """
    Resumen acumulado de eventos de telemetría.
    """

    scope: str
    scope_id: str

    events_total: int = 0
    successful_events: int = 0
    failed_events: int = 0
    success_rate: float = 0.0

    duration_seconds: float = 0.0
    average_duration_seconds: float = 0.0

    prompt_tokens: int = 0
    response_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0

    retry_attempts: int = 0
    retry_count: int = 0
    exhausted_events: int = 0
    recovered_events: int = 0

    estimated_cost: float = 0.0
    currency: str = "USD"

    providers: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    status_codes: dict[str, int] = field(default_factory=dict)
    exception_types: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def register_event(self, event: TelemetryEvent) -> None:
        if not isinstance(event, TelemetryEvent):
            raise TypeError("event debe ser TelemetryEvent.")

        self.events_total += 1
        if event.success:
            self.successful_events += 1
        else:
            self.failed_events += 1

        self.duration_seconds += event.duration_seconds
        self.prompt_tokens += event.prompt_tokens
        self.response_tokens += event.response_tokens
        self.thinking_tokens += event.thinking_tokens
        self.total_tokens += event.total_tokens
        self.retry_attempts += event.retry_attempts
        self.retry_count += event.retry_count

        if event.retry_exhausted:
            self.exhausted_events += 1
        if event.succeeded_after_retry:
            self.recovered_events += 1

        self.estimated_cost += event.estimated_cost

        self._append_unique(self.providers, event.provider)
        self._append_unique(self.models, event.model)
        self._append_unique(self.stages, event.stage)

        if event.status_code is not None:
            key = str(event.status_code)
            self.status_codes[key] = (
                self.status_codes.get(key, 0) + 1
            )

        if event.exception_type:
            self.exception_types[event.exception_type] = (
                self.exception_types.get(
                    event.exception_type,
                    0,
                )
                + 1
            )

        self._recalculate()

    def merge(self, other: "TelemetrySummary") -> None:
        if not isinstance(other, TelemetrySummary):
            raise TypeError("other debe ser TelemetrySummary.")

        self.events_total += other.events_total
        self.successful_events += other.successful_events
        self.failed_events += other.failed_events
        self.duration_seconds += other.duration_seconds
        self.prompt_tokens += other.prompt_tokens
        self.response_tokens += other.response_tokens
        self.thinking_tokens += other.thinking_tokens
        self.total_tokens += other.total_tokens
        self.retry_attempts += other.retry_attempts
        self.retry_count += other.retry_count
        self.exhausted_events += other.exhausted_events
        self.recovered_events += other.recovered_events
        self.estimated_cost += other.estimated_cost

        for provider in other.providers:
            self._append_unique(self.providers, provider)
        for model in other.models:
            self._append_unique(self.models, model)
        for stage in other.stages:
            self._append_unique(self.stages, stage)

        for code, count in other.status_codes.items():
            self.status_codes[str(code)] = (
                self.status_codes.get(str(code), 0)
                + int(count)
            )

        for exception_type, count in (
            other.exception_types.items()
        ):
            self.exception_types[exception_type] = (
                self.exception_types.get(
                    exception_type,
                    0,
                )
                + int(count)
            )

        self._recalculate()

    def to_dict(self) -> dict[str, Any]:
        self._recalculate()
        return asdict(self)

    def _recalculate(self) -> None:
        if self.events_total > 0:
            self.success_rate = round(
                (
                    self.successful_events
                    / self.events_total
                )
                * 100,
                2,
            )
            self.average_duration_seconds = round(
                self.duration_seconds
                / self.events_total,
                6,
            )
        else:
            self.success_rate = 0.0
            self.average_duration_seconds = 0.0

        self.duration_seconds = round(
            self.duration_seconds,
            6,
        )
        self.estimated_cost = round(
            self.estimated_cost,
            8,
        )

    @staticmethod
    def _append_unique(
        values: list[str],
        value: Any,
    ) -> None:
        normalized = str(value or "").strip()
        if normalized and normalized not in values:
            values.append(normalized)


def get_telemetry_models_info() -> dict[str, Any]:
    """
    Devuelve información pública del módulo.
    """

    return {
        "component": "telemetry_models",
        "version": "0.8",
        "models": [
            "TelemetryAttempt",
            "TelemetryEvent",
            "TelemetrySummary",
        ],
        "serializable": True,
        "runtime_models_modified": False,
        "next_component": "telemetry_engine",
    }