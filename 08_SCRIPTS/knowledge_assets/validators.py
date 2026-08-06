###############################################################################
# validators.py
#
# Knowledge Assets Library
#
# Infraestructura central de validación para activos de conocimiento,
# relaciones, colecciones, consultas, paquetes y estructuras de grafo.
#
# Este módulo proporciona:
#
#     • Resultados de validación acumulativos
#     • Problemas clasificados por severidad
#     • Contexto y rutas de validación
#     • Conversión de resultados a diccionarios y JSON
#     • Utilidades reutilizables para validadores especializados
#
# Los validadores concretos se incorporarán en las siguientes secciones
# del módulo.
###############################################################################

from __future__ import annotations

###############################################################################
# STANDARD LIBRARY
###############################################################################

from abc import ABC
from abc import abstractmethod

from collections.abc import Iterable as IterableABC

from dataclasses import dataclass
from dataclasses import field

from datetime import datetime

from enum import Enum

import json

from time import perf_counter

from typing import Any
from typing import Callable
from typing import Dict
from typing import Generic
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Mapping
from typing import MutableMapping
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple
from typing import Type
from typing import TypeAlias
from typing import TypeVar

###############################################################################
# LOCAL IMPORTS
###############################################################################

from .exceptions import ValidationError
from .models import KnowledgeAsset

###############################################################################
# TYPE ALIASES
###############################################################################

JSONDict: TypeAlias = Dict[
    str,
    Any,
]

ValidationPath: TypeAlias = Tuple[
    str,
    ...,
]

ValidationMetadata: TypeAlias = MutableMapping[
    str,
    Any,
]

ValidationIssueList: TypeAlias = List[
    "ValidationIssue",
]

ValidationResultList: TypeAlias = List[
    "ValidationResult",
]

ValidationSubject = TypeVar(
    "ValidationSubject"
)

ValidationSubjectType: TypeAlias = Type[
    Any
]

ValidationProfileName: TypeAlias = str

ValidationRuleName: TypeAlias = str

ValidationRuleTag: TypeAlias = str

ValidationRuleTags: TypeAlias = Set[
    ValidationRuleTag
]

ValidationState: TypeAlias = MutableMapping[
    str,
    Any,
]


###############################################################################
# MODULE DEFAULTS
###############################################################################

DEFAULT_VALIDATION_CODE = "validation.issue"

DEFAULT_VALIDATION_MESSAGE = "Se detectó un problema de validación."

DEFAULT_VALIDATOR_NAME = "validator"

###############################################################################
# HELPERS
###############################################################################


def _now() -> datetime:
    """
    Devuelve la fecha y hora UTC actual.
    """

    return datetime.utcnow()


###############################################################################


def _normalize_text(
    value: Any,
) -> str:
    """
    Convierte un valor a texto limpio.

    None se convierte en una cadena vacía.
    """

    if value is None:

        return ""

    return str(
        value
    ).strip()


###############################################################################


def _normalize_code(
    value: Any,
) -> str:
    """
    Normaliza un código de validación.
    """

    normalized = _normalize_text(
        value
    )

    if not normalized:

        return DEFAULT_VALIDATION_CODE

    return normalized.casefold().replace(
        " ",
        ".",
    )


###############################################################################


def _normalize_path_part(
    value: Any,
) -> str:
    """
    Normaliza una sección de una ruta de validación.
    """

    return _normalize_text(
        value
    )


###############################################################################


def _normalize_path(
    path: Optional[
        Iterable[
            Any
        ]
    ],
) -> ValidationPath:
    """
    Convierte una ruta arbitraria en una tupla de texto.
    """

    if path is None:

        return ()

    return tuple(

        normalized

        for value in path

        if (
            normalized := _normalize_path_part(
                value
            )
        )

    )


###############################################################################


def _path_to_string(
    path: ValidationPath,
    *,
    separator: str = ".",
) -> str:
    """
    Convierte una ruta estructurada a texto.
    """

    return separator.join(
        path
    )


###############################################################################


def _coerce_metadata(
    metadata: Optional[
        Mapping[
            str,
            Any,
        ]
    ],
) -> ValidationMetadata:
    """
    Crea una copia mutable de la metadata recibida.
    """

    if metadata is None:

        return {}

    return dict(
        metadata
    )


###############################################################################


def _safe_value(
    value: Any,
) -> Any:
    """
    Convierte valores comunes a representaciones serializables.

    Los valores desconocidos se convierten a texto para evitar errores
    durante la creación de reportes.
    """

    if value is None:

        return None

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

    if isinstance(
        value,
        datetime,
    ):

        return value.isoformat()

    if isinstance(
        value,
        Enum,
    ):

        return value.name

    if isinstance(
        value,
        Mapping,
    ):

        return {

            str(key): _safe_value(
                current
            )

            for key, current

            in value.items()

        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            frozenset,
        ),
    ):

        return [

            _safe_value(
                current
            )

            for current

            in value

        ]

    return repr(
        value
    )


###############################################################################
# VALIDATION SEVERITY
###############################################################################


class ValidationSeverity(
    str,
    Enum,
):
    """
    Nivel de severidad de un problema de validación.

    El orden lógico es:

        INFO < WARNING < ERROR < CRITICAL
    """

    INFO = "info"

    WARNING = "warning"

    ERROR = "error"

    CRITICAL = "critical"

    ###########################################################################

    @property
    def rank(
        self,
    ) -> int:
        """
        Valor ordinal utilizado para comparaciones.
        """

        ranks = {

            ValidationSeverity.INFO: 10,

            ValidationSeverity.WARNING: 20,

            ValidationSeverity.ERROR: 30,

            ValidationSeverity.CRITICAL: 40,

        }

        return ranks[
            self
        ]

    ###########################################################################

    @property
    def invalidates(
        self,
    ) -> bool:
        """
        Indica si la severidad invalida el objeto evaluado.
        """

        return self in {

            ValidationSeverity.ERROR,

            ValidationSeverity.CRITICAL,

        }

    ###########################################################################

    @classmethod
    def coerce(
        cls,
        value: Any,
    ) -> "ValidationSeverity":
        """
        Convierte texto u otra instancia compatible a ValidationSeverity.
        """

        if isinstance(
            value,
            cls,
        ):

            return value

        normalized = _normalize_text(
            value
        ).casefold()

        for severity in cls:

            if normalized in {

                severity.name.casefold(),

                severity.value.casefold(),

            }:

                return severity

        raise ValueError(
            f"Severidad de validación no reconocida: {value!r}."
        )

    ###########################################################################

    def __lt__(
        self,
        other: object,
    ) -> bool:

        if not isinstance(
            other,
            ValidationSeverity,
        ):

            return NotImplemented

        return self.rank < other.rank


###############################################################################
# VALIDATION ISSUE
###############################################################################


@dataclass(
    slots=True,
    frozen=True,
)
class ValidationIssue:
    """
    Representa un problema individual detectado durante una validación.

    Una incidencia contiene:

        • severidad
        • código estable
        • mensaje legible
        • ruta dentro del objeto
        • valor relacionado
        • regla o validador que la produjo
        • metadata adicional
    """

    ###########################################################################
    # IDENTIDAD
    ###########################################################################

    code: str = DEFAULT_VALIDATION_CODE

    message: str = DEFAULT_VALIDATION_MESSAGE

    severity: ValidationSeverity = ValidationSeverity.ERROR

    ###########################################################################
    # CONTEXTO
    ###########################################################################

    path: ValidationPath = ()

    field_name: Optional[
        str
    ] = None

    value: Any = None

    validator: Optional[
        str
    ] = None

    rule: Optional[
        str
    ] = None

    hint: Optional[
        str
    ] = None

    ###########################################################################
    # METADATA
    ###########################################################################

    metadata: Mapping[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    ###########################################################################
    # AUDITORÍA
    ###########################################################################

    created_at: datetime = field(
        default_factory=_now
    )

    ###########################################################################
    # NORMALIZACIÓN
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:

        object.__setattr__(
            self,
            "code",
            _normalize_code(
                self.code
            ),
        )

        message = _normalize_text(
            self.message
        )

        object.__setattr__(
            self,
            "message",
            message
            or DEFAULT_VALIDATION_MESSAGE,
        )

        object.__setattr__(
            self,
            "severity",
            ValidationSeverity.coerce(
                self.severity
            ),
        )

        object.__setattr__(
            self,
            "path",
            _normalize_path(
                self.path
            ),
        )

        if self.field_name is not None:

            normalized_field = _normalize_text(
                self.field_name
            )

            object.__setattr__(
                self,
                "field_name",
                normalized_field
                or None,
            )

        if self.validator is not None:

            normalized_validator = _normalize_text(
                self.validator
            )

            object.__setattr__(
                self,
                "validator",
                normalized_validator
                or None,
            )

        if self.rule is not None:

            normalized_rule = _normalize_text(
                self.rule
            )

            object.__setattr__(
                self,
                "rule",
                normalized_rule
                or None,
            )

        if self.hint is not None:

            normalized_hint = _normalize_text(
                self.hint
            )

            object.__setattr__(
                self,
                "hint",
                normalized_hint
                or None,
            )

        object.__setattr__(
            self,
            "metadata",
            dict(
                self.metadata
            ),
        )

    ###########################################################################
    # PROPIEDADES
    ###########################################################################

    @property
    def is_info(
        self,
    ) -> bool:

        return (
            self.severity
            is ValidationSeverity.INFO
        )

    ###########################################################################

    @property
    def is_warning(
        self,
    ) -> bool:

        return (
            self.severity
            is ValidationSeverity.WARNING
        )

    ###########################################################################

    @property
    def is_error(
        self,
    ) -> bool:

        return (
            self.severity
            is ValidationSeverity.ERROR
        )

    ###########################################################################

    @property
    def is_critical(
        self,
    ) -> bool:

        return (
            self.severity
            is ValidationSeverity.CRITICAL
        )

    ###########################################################################

    @property
    def invalidates(
        self,
    ) -> bool:

        return self.severity.invalidates

    ###########################################################################

    @property
    def path_string(
        self,
    ) -> str:

        return _path_to_string(
            self.path
        )

    ###########################################################################
    # OPERACIONES
    ###########################################################################

    def with_prefix(
        self,
        *parts: str,
    ) -> "ValidationIssue":
        """
        Devuelve una nueva incidencia con una ruta prefijada.
        """

        prefix = _normalize_path(
            parts
        )

        return ValidationIssue(

            code=self.code,

            message=self.message,

            severity=self.severity,

            path=prefix + self.path,

            field_name=self.field_name,

            value=self.value,

            validator=self.validator,

            rule=self.rule,

            hint=self.hint,

            metadata=self.metadata,

            created_at=self.created_at,

        )

    ###########################################################################
    # SERIALIZACIÓN
    ###########################################################################

    def to_dict(
        self,
        *,
        include_value: bool = True,
    ) -> JSONDict:

        data: JSONDict = {

            "code": self.code,

            "message": self.message,

            "severity": self.severity.value,

            "path": list(
                self.path
            ),

            "path_string": self.path_string,

            "field_name": self.field_name,

            "validator": self.validator,

            "rule": self.rule,

            "hint": self.hint,

            "metadata": _safe_value(
                self.metadata
            ),

            "created_at":
            self.created_at.isoformat(),

        }

        if include_value:

            data["value"] = _safe_value(
                self.value
            )

        return data

    ###########################################################################

    def to_json(
        self,
        *,
        indent: int = 2,
        include_value: bool = True,
    ) -> str:

        return json.dumps(

            self.to_dict(
                include_value=include_value
            ),

            indent=indent,

            ensure_ascii=False,

        )

    ###########################################################################

    def __str__(
        self,
    ) -> str:

        location = (
            f" [{self.path_string}]"
            if self.path
            else ""
        )

        return (

            f"{self.severity.value.upper()} "

            f"{self.code}{location}: "

            f"{self.message}"

        )


###############################################################################
# VALIDATION RESULT
###############################################################################


@dataclass(slots=True)
class ValidationResult:
    """
    Resultado acumulativo de una operación de validación.

    Permite registrar múltiples incidencias sin detener la ejecución en
    el primer error.
    """

    ###########################################################################
    # IDENTIDAD
    ###########################################################################

    validator: str = DEFAULT_VALIDATOR_NAME

    subject_type: Optional[
        str
    ] = None

    subject_identifier: Optional[
        str
    ] = None

    ###########################################################################
    # RESULTADOS
    ###########################################################################

    issues: ValidationIssueList = field(
        default_factory=list
    )

    rules_executed: List[
        str
    ] = field(
        default_factory=list
    )

    rules_skipped: List[
        str
    ] = field(
        default_factory=list
    )

    ###########################################################################
    # METADATA
    ###########################################################################

    metadata: ValidationMetadata = field(
        default_factory=dict
    )

    ###########################################################################
    # AUDITORÍA
    ###########################################################################

    started_at: datetime = field(
        default_factory=_now
    )

    completed_at: Optional[
        datetime
    ] = None

    duration_ms: Optional[
        float
    ] = None

    ###########################################################################
    # ESTADO INTERNO
    ###########################################################################

    _performance_start: float = field(
        default_factory=perf_counter,
        repr=False,
    )

    ###########################################################################
    # NORMALIZACIÓN
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:

        self.validator = (
            _normalize_text(
                self.validator
            )
            or DEFAULT_VALIDATOR_NAME
        )

        if self.subject_type is not None:

            self.subject_type = (
                _normalize_text(
                    self.subject_type
                )
                or None
            )

        if self.subject_identifier is not None:

            self.subject_identifier = (
                _normalize_text(
                    self.subject_identifier
                )
                or None
            )

        self.metadata = dict(
            self.metadata
        )

    ###########################################################################
    # PROPIEDADES
    ###########################################################################

    @property
    def valid(
        self,
    ) -> bool:

        return not any(

            issue.invalidates

            for issue

            in self.issues

        )

    ###########################################################################

    @property
    def invalid(
        self,
    ) -> bool:

        return not self.valid

    ###########################################################################

    @property
    def completed(
        self,
    ) -> bool:

        return self.completed_at is not None

    ###########################################################################

    @property
    def issue_count(
        self,
    ) -> int:

        return len(
            self.issues
        )

    ###########################################################################

    @property
    def info_count(
        self,
    ) -> int:

        return len(
            self.infos
        )

    ###########################################################################

    @property
    def warning_count(
        self,
    ) -> int:

        return len(
            self.warnings
        )

    ###########################################################################

    @property
    def error_count(
        self,
    ) -> int:

        return len(
            self.errors
        )

    ###########################################################################

    @property
    def critical_count(
        self,
    ) -> int:

        return len(
            self.critical_errors
        )

    ###########################################################################

    @property
    def infos(
        self,
    ) -> ValidationIssueList:

        return self.by_severity(
            ValidationSeverity.INFO
        )

    ###########################################################################

    @property
    def warnings(
        self,
    ) -> ValidationIssueList:

        return self.by_severity(
            ValidationSeverity.WARNING
        )

    ###########################################################################

    @property
    def errors(
        self,
    ) -> ValidationIssueList:

        return [

            issue

            for issue

            in self.issues

            if issue.severity in {

                ValidationSeverity.ERROR,

                ValidationSeverity.CRITICAL,

            }

        ]

    ###########################################################################

    @property
    def critical_errors(
        self,
    ) -> ValidationIssueList:

        return self.by_severity(
            ValidationSeverity.CRITICAL
        )

    ###########################################################################

    @property
    def highest_severity(
        self,
    ) -> Optional[
        ValidationSeverity
    ]:

        if not self.issues:

            return None

        return max(

            (
                issue.severity
                for issue
                in self.issues
            ),

            key=lambda severity:
            severity.rank,

        )

    ###########################################################################
    # REGISTRO DE INCIDENCIAS
    ###########################################################################

    def add_issue(
        self,
        issue: ValidationIssue,
    ) -> ValidationIssue:

        if not isinstance(
            issue,
            ValidationIssue,
        ):

            raise TypeError(
                "ValidationIssue esperado."
            )

        self.issues.append(
            issue
        )

        return issue

    ###########################################################################

    def add(
        self,
        message: str,
        *,
        code: str = DEFAULT_VALIDATION_CODE,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
        path: Optional[
            Iterable[
                Any
            ]
        ] = None,
        field_name: Optional[str] = None,
        value: Any = None,
        validator: Optional[str] = None,
        rule: Optional[str] = None,
        hint: Optional[str] = None,
        metadata: Optional[
            Mapping[
                str,
                Any,
            ]
        ] = None,
    ) -> ValidationIssue:
        """
        Crea y registra una incidencia.
        """

        issue = ValidationIssue(

            code=code,

            message=message,

            severity=severity,

            path=_normalize_path(
                path
            ),

            field_name=field_name,

            value=value,

            validator=validator
            or self.validator,

            rule=rule,

            hint=hint,

            metadata=_coerce_metadata(
                metadata
            ),

        )

        return self.add_issue(
            issue
        )

    ###########################################################################

    def add_info(
        self,
        message: str,
        **kwargs: Any,
    ) -> ValidationIssue:

        return self.add(

            message,

            severity=ValidationSeverity.INFO,

            **kwargs,

        )

    ###########################################################################

    def add_warning(
        self,
        message: str,
        **kwargs: Any,
    ) -> ValidationIssue:

        return self.add(

            message,

            severity=ValidationSeverity.WARNING,

            **kwargs,

        )

    ###########################################################################

    def add_error(
        self,
        message: str,
        **kwargs: Any,
    ) -> ValidationIssue:

        return self.add(

            message,

            severity=ValidationSeverity.ERROR,

            **kwargs,

        )

    ###########################################################################

    def add_critical(
        self,
        message: str,
        **kwargs: Any,
    ) -> ValidationIssue:

        return self.add(

            message,

            severity=ValidationSeverity.CRITICAL,

            **kwargs,

        )

    ###########################################################################
    # REGLAS
    ###########################################################################

    def mark_rule_executed(
        self,
        rule_name: str,
    ) -> None:

        normalized = _normalize_text(
            rule_name
        )

        if (
            normalized

            and normalized
            not in self.rules_executed
        ):

            self.rules_executed.append(
                normalized
            )

    ###########################################################################

    def mark_rule_skipped(
        self,
        rule_name: str,
    ) -> None:

        normalized = _normalize_text(
            rule_name
        )

        if (
            normalized

            and normalized
            not in self.rules_skipped
        ):

            self.rules_skipped.append(
                normalized
            )

    ###########################################################################
    # CONSULTAS
    ###########################################################################

    def by_severity(
        self,
        severity: ValidationSeverity,
    ) -> ValidationIssueList:

        severity = ValidationSeverity.coerce(
            severity
        )

        return [

            issue

            for issue

            in self.issues

            if issue.severity
            is severity

        ]

    ###########################################################################

    def by_code(
        self,
        code: str,
    ) -> ValidationIssueList:

        normalized = _normalize_code(
            code
        )

        return [

            issue

            for issue

            in self.issues

            if issue.code
            == normalized

        ]

    ###########################################################################

    def by_path(
        self,
        path: Iterable[
            Any
        ],
        *,
        include_descendants: bool = True,
    ) -> ValidationIssueList:

        normalized = _normalize_path(
            path
        )

        if include_descendants:

            length = len(
                normalized
            )

            return [

                issue

                for issue

                in self.issues

                if issue.path[
                    :length
                ]
                == normalized

            ]

        return [

            issue

            for issue

            in self.issues

            if issue.path
            == normalized

        ]

    ###########################################################################

    def has_code(
        self,
        code: str,
    ) -> bool:

        return bool(
            self.by_code(
                code
            )
        )

    ###########################################################################

    def contains_severity(
        self,
        severity: ValidationSeverity,
    ) -> bool:

        return bool(
            self.by_severity(
                severity
            )
        )

    ###########################################################################
    # COMPOSICIÓN
    ###########################################################################

    def extend(
        self,
        issues: Iterable[
            ValidationIssue
        ],
        *,
        path_prefix: Optional[
            Iterable[
                Any
            ]
        ] = None,
    ) -> None:

        prefix = _normalize_path(
            path_prefix
        )

        for issue in issues:

            if prefix:

                issue = issue.with_prefix(
                    *prefix
                )

            self.add_issue(
                issue
            )

    ###########################################################################

    def merge(
        self,
        other: "ValidationResult",
        *,
        path_prefix: Optional[
            Iterable[
                Any
            ]
        ] = None,
    ) -> "ValidationResult":

        if not isinstance(
            other,
            ValidationResult,
        ):

            raise TypeError(
                "ValidationResult esperado."
            )

        self.extend(

            other.issues,

            path_prefix=path_prefix,

        )

        for rule_name in other.rules_executed:

            self.mark_rule_executed(
                rule_name
            )

        for rule_name in other.rules_skipped:

            self.mark_rule_skipped(
                rule_name
            )

        self.metadata.update(
            other.metadata
        )

        return self

    ###########################################################################
    # FINALIZACIÓN
    ###########################################################################

    def finish(
        self,
    ) -> "ValidationResult":
        """
        Finaliza el resultado y calcula su duración.
        """

        if self.completed:

            return self

        self.completed_at = _now()

        self.duration_ms = round(

            (
                perf_counter()
                -
                self._performance_start
            )
            *
            1000,

            3,

        )

        return self

    ###########################################################################

    def clear(
        self,
    ) -> None:

        self.issues.clear()

        self.rules_executed.clear()

        self.rules_skipped.clear()

        self.completed_at = None

        self.duration_ms = None

        self.started_at = _now()

        self._performance_start = perf_counter()

    ###########################################################################
    # EXCEPCIONES
    ###########################################################################

    def raise_for_errors(
        self,
        *,
        message: Optional[str] = None,
    ) -> None:
        """
        Lanza ValidationError cuando existen errores invalidantes.
        """

        if self.valid:

            return

        detail = message or self.summary()

        raise ValidationError(
            detail
        )

    ###########################################################################
    # REPRESENTACIÓN
    ###########################################################################

    def summary(
        self,
    ) -> str:

        status = (
            "válido"
            if self.valid
            else "inválido"
        )

        return (

            f"Resultado de validación {status}: "

            f"{self.error_count} error(es), "

            f"{self.warning_count} advertencia(s), "

            f"{self.info_count} mensaje(s) informativo(s)."

        )

    ###########################################################################

    def to_dict(
        self,
        *,
        include_values: bool = True,
    ) -> JSONDict:

        return {

            "valid":
            self.valid,

            "invalid":
            self.invalid,

            "validator":
            self.validator,

            "subject_type":
            self.subject_type,

            "subject_identifier":
            self.subject_identifier,

            "issue_count":
            self.issue_count,

            "info_count":
            self.info_count,

            "warning_count":
            self.warning_count,

            "error_count":
            self.error_count,

            "critical_count":
            self.critical_count,

            "highest_severity":
            (
                self.highest_severity.value
                if self.highest_severity
                else None
            ),

            "issues": [

                issue.to_dict(
                    include_value=include_values
                )

                for issue

                in self.issues

            ],

            "rules_executed":
            list(
                self.rules_executed
            ),

            "rules_skipped":
            list(
                self.rules_skipped
            ),

            "metadata":
            _safe_value(
                self.metadata
            ),

            "started_at":
            self.started_at.isoformat(),

            "completed_at":
            (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),

            "duration_ms":
            self.duration_ms,

        }

    ###########################################################################

    def to_json(
        self,
        *,
        indent: int = 2,
        include_values: bool = True,
    ) -> str:

        return json.dumps(

            self.to_dict(
                include_values=include_values
            ),

            indent=indent,

            ensure_ascii=False,

        )

    ###########################################################################
    # MÉTODOS ESPECIALES
    ###########################################################################

    def __iter__(
        self,
    ) -> Iterator[
        ValidationIssue
    ]:

        return iter(
            self.issues
        )

    ###########################################################################

    def __len__(
        self,
    ) -> int:

        return len(
            self.issues
        )

    ###########################################################################

    def __bool__(
        self,
    ) -> bool:
        """
        Un resultado se evalúa como True cuando es válido.
        """

        return self.valid

    ###########################################################################

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"validator={self.validator!r}, "

            f"valid={self.valid!r}, "

            f"issues={self.issue_count})"

        )
 
        
    ###############################################################################
    # RULE OUTPUT ALIAS
    ###############################################################################


RuleOutput: TypeAlias = (
    None
    | bool
    | str
    | ValidationIssue
    | ValidationResult
    | Iterable[
        ValidationIssue
    ]
)


    ###############################################################################
    # VALIDATION HOOK ALIASES
    ###############################################################################


BeforeValidationHook: TypeAlias = Callable[
    [
        "ValidationContext[Any]",
    ],
    None,
]

AfterValidationHook: TypeAlias = Callable[
    [
        "ValidationContext[Any]",
        ValidationResult,
    ],
    None,
]

ValidationErrorHook: TypeAlias = Callable[
    [
        "ValidationContext[Any]",
        Exception,
    ],
    None,
]


    ###############################################################################
    # VALIDATION CONTEXT
    ###############################################################################


@dataclass(
    slots=True,
)
class ValidationContext(
    Generic[
        ValidationSubject,
    ],
):
    """
    Runtime context shared across validation rules.

    The context stores the object being validated together with
    execution metadata, accumulated state and optional external
    services required during validation.

    Every rule executed by the validation engine receives the same
    ValidationContext instance.
    """

    subject: ValidationSubject

    profile: ValidationProfileName = "default"

    path: ValidationPath = field(
        default_factory=tuple,
    )

    state: ValidationState = field(
        default_factory=dict,
    )

    metadata: ValidationMetadata = field(
        default_factory=dict,
    )

    services: MutableMapping[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    parent: Optional[
        "ValidationContext[Any]"
    ] = None

    created_at: datetime = field(
        default_factory=_now,
    )

    def child(
        self,
        subject: Any,
        *path: str,
    ) -> "ValidationContext[Any]":
        """
        Creates a child validation context.

        The child shares the execution state and services while
        extending the validation path.
        """

        return ValidationContext(

            subject=subject,

            profile=self.profile,

            path=(
                *self.path,
                *path,
            ),

            state=self.state,

            metadata=self.metadata,

            services=self.services,

            parent=self,
        )

    @property
    def root(
        self,
    ) -> "ValidationContext[Any]":

        context: ValidationContext[Any] = self

        while context.parent is not None:

            context = context.parent

        return context

    @property
    def is_root(
        self,
    ) -> bool:

        return self.parent is None

    def push(
        self,
        *path: str,
    ) -> None:

        self.path = (

            *self.path,

            *path,

        )

    def pop(
        self,
        count: int = 1,
    ) -> None:

        if count <= 0:

            return

        self.path = self.path[
            :-count
        ]

    def reset_path(
        self,
    ) -> None:

        self.path = tuple()

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self.state.get(
            key,
            default,
        )

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:

        self.state[
            key
        ] = value

    def contains(
        self,
        key: str,
    ) -> bool:

        return key in self.state

    def remove(
        self,
        key: str,
    ) -> None:

        self.state.pop(
            key,
            None,
        )

    def clear_state(
        self,
    ) -> None:

        self.state.clear()

    def service(
        self,
        name: str,
    ) -> Any:

        return self.services.get(
            name,
        )

    def register_service(
        self,
        name: str,
        service: Any,
    ) -> None:

        self.services[
            name
        ] = service

    def unregister_service(
        self,
        name: str,
    ) -> None:

        self.services.pop(
            name,
            None,
        )

    def copy(
        self,
    ) -> "ValidationContext[ValidationSubject]":

        return ValidationContext(

            subject=self.subject,

            profile=self.profile,

            path=self.path,

            state=dict(
                self.state,
            ),

            metadata=dict(
                self.metadata,
            ),

            services=dict(
                self.services,
            ),

            parent=self.parent,
        )

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "profile": self.profile,

            "path": list(
                self.path,
            ),

            "state": dict(
                self.state,
            ),

            "metadata": dict(
                self.metadata,
            ),

            "services": list(
                self.services.keys(),
            ),

            "is_root": self.is_root,

            "created_at": (
                self.created_at.isoformat()
            ),

        }

    def __len__(
        self,
    ) -> int:

        return len(
            self.path,
        )

    def __bool__(
        self,
    ) -> bool:

        return True

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"profile={self.profile!r}, "

            f"path={self.path!r}, "

            f"subject={type(self.subject).__name__})"

        )
        
        
    ###############################################################################
    # VALIDATION RULE
    ###############################################################################


class ValidationRule(
    ABC,
    Generic[
        ValidationSubject,
    ],
):
    """
    Base class for every validation rule.

    A rule evaluates one aspect of a subject and may produce
    zero or more validation issues.

    Rules are intentionally stateless and reusable.
    """

    __slots__ = (

        "_name",

        "_description",

        "_severity",

        "_enabled",

        "_tags",

    )

    def __init__(
        self,
        name: ValidationRuleName,
        *,
        description: str = "",
        severity: ValidationSeverity = (
            ValidationSeverity.ERROR
        ),
        enabled: bool = True,
        tags: Optional[
            Iterable[
                ValidationRuleTag
            ]
        ] = None,
    ) -> None:

        self._name = _normalize_code(
            name,
        )

        self._description = description.strip()

        self._severity = (
            ValidationSeverity.coerce(
                severity,
            )
        )

        self._enabled = bool(
            enabled,
        )

        self._tags = frozenset(

            _normalize_code(
                tag,
            )

            for tag in (
                tags or ()
            )

            if str(
                tag,
            ).strip()

        )

    @property
    def name(
        self,
    ) -> ValidationRuleName:

        return self._name

    @property
    def description(
        self,
    ) -> str:

        return self._description

    @property
    def severity(
        self,
    ) -> ValidationSeverity:

        return self._severity

    @property
    def enabled(
        self,
    ) -> bool:

        return self._enabled

    @property
    def tags(
        self,
    ) -> ValidationRuleTags:

        return self._tags

    def enable(
        self,
    ) -> None:

        self._enabled = True

    def disable(
        self,
    ) -> None:

        self._enabled = False

    def has_tag(
        self,
        tag: str,
    ) -> bool:

        return _normalize_code(
            tag,
        ) in self._tags

    @abstractmethod
    def validate(
        self,
        context: ValidationContext[
            ValidationSubject
        ],
    ) -> RuleOutput:
        """
        Executes the validation rule.
        """
        raise NotImplementedError

    def __call__(
        self,
        context: ValidationContext[
            ValidationSubject
        ],
    ) -> RuleOutput:

        if not self.enabled:

            return None

        return self.validate(
            context,
        )

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"name={self.name!r}, "

            f"severity={self.severity.name!r}, "

            f"enabled={self.enabled!r})"

        )
        
        
    ###############################################################################
    # FUNCTIONAL VALIDATION RULE
    ###############################################################################


class FunctionalValidationRule(
    ValidationRule[
        ValidationSubject
    ],
    Generic[
        ValidationSubject,
    ],
):
    """
    Validation rule backed by a callable.

    This implementation allows simple validation rules to be
    created without defining a dedicated ValidationRule subclass.

    The callable receives the active ValidationContext and may
    return any value supported by RuleOutput.
    """

    __slots__ = (
        "_function",
    )

    def __init__(
        self,
        name: ValidationRuleName,
        function: Callable[
            [
                ValidationContext[
                    ValidationSubject
                ]
            ],
            RuleOutput,
        ],
        *,
        description: str = "",
        severity: ValidationSeverity = (
            ValidationSeverity.ERROR
        ),
        enabled: bool = True,
        tags: Optional[
            Iterable[
                ValidationRuleTag
            ]
        ] = None,
    ) -> None:

        if not callable(
            function,
        ):

            raise TypeError(
                "function must be callable"
            )

        super().__init__(

            name=name,

            description=description,

            severity=severity,

            enabled=enabled,

            tags=tags,

        )

        self._function = function

    @property
    def function(
        self,
    ) -> Callable[
        [
            ValidationContext[
                ValidationSubject
            ]
        ],
        RuleOutput,
    ]:

        return self._function

    @property
    def function_name(
        self,
    ) -> str:

        return getattr(

            self.function,

            "__name__",

            type(
                self.function
            ).__name__,

        )

    def validate(
        self,
        context: ValidationContext[
            ValidationSubject
        ],
    ) -> RuleOutput:
        """
        Executes the configured validation callable.
        """

        return self.function(
            context,
        )

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"name={self.name!r}, "

            f"function={self.function_name!r}, "

            f"severity={self.severity.name!r}, "

            f"enabled={self.enabled!r})"

        )
    ###############################################################################
    # VALIDATION PROFILE
    ###############################################################################


class ValidationProfile:
    """
    Named collection of validation rules.

    A profile represents a validation strategy such as:

        default
        strict
        fast
        import
        api
        graph

    The validation engine executes the rules contained in the
    selected profile.
    """

    __slots__ = (

        "_name",

        "_description",

        "_rules",

    )

    def __init__(
        self,
        name: ValidationProfileName,
        *,
        description: str = "",
    ) -> None:

        self._name = _normalize_code(
            name,
        )

        self._description = description.strip()

        self._rules: List[
            ValidationRule[Any]
        ] = []

    @property
    def name(
        self,
    ) -> ValidationProfileName:

        return self._name

    @property
    def description(
        self,
    ) -> str:

        return self._description

    @property
    def rules(
        self,
    ) -> Tuple[
        ValidationRule[Any],
        ...,
    ]:

        return tuple(
            self._rules,
        )

    def add(
        self,
        rule: ValidationRule[Any],
    ) -> "ValidationProfile":

        self._rules.append(
            rule,
        )

        return self

    def extend(
        self,
        rules: Iterable[
            ValidationRule[Any]
        ],
    ) -> "ValidationProfile":

        for rule in rules:

            self.add(
                rule,
            )

        return self

    def remove(
        self,
        name: ValidationRuleName,
    ) -> bool:

        normalized = _normalize_code(
            name,
        )

        for index, rule in enumerate(
            self._rules,
        ):

            if rule.name == normalized:

                del self._rules[
                    index
                ]

                return True

        return False

    def clear(
        self,
    ) -> None:

        self._rules.clear()

    def get(
        self,
        name: ValidationRuleName,
    ) -> Optional[
        ValidationRule[Any]
    ]:

        normalized = _normalize_code(
            name,
        )

        for rule in self._rules:

            if rule.name == normalized:

                return rule

        return None

    def contains(
        self,
        name: ValidationRuleName,
    ) -> bool:

        return (

            self.get(
                name,
            )

            is not None

        )

    def enabled_rules(
        self,
    ) -> Iterator[
        ValidationRule[Any]
    ]:

        for rule in self._rules:

            if rule.enabled:

                yield rule

    def rules_with_tag(
        self,
        tag: ValidationRuleTag,
    ) -> Iterator[
        ValidationRule[Any]
    ]:

        normalized = _normalize_code(
            tag,
        )

        for rule in self._rules:

            if rule.has_tag(
                normalized,
            ):

                yield rule

    def __iter__(
        self,
    ) -> Iterator[
        ValidationRule[Any]
    ]:

        return iter(
            self._rules,
        )

    def __len__(
        self,
    ) -> int:

        return len(
            self._rules,
        )

    def __contains__(
        self,
        name: object,
    ) -> bool:

        if not isinstance(
            name,
            str,
        ):

            return False

        return self.contains(
            name,
        )

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"name={self.name!r}, "

            f"rules={len(self)!r})"

        )
    ###############################################################################
    # RULE PIPELINE
    ###############################################################################


class RulePipeline:
    """
    Coordinates validation profiles and executes their rules.

    The pipeline selects a validation profile, applies optional
    rule filters, executes each enabled rule and normalizes every
    supported RuleOutput into a single ValidationResult.

    Rule execution errors may either be converted into validation
    issues or propagated to the caller.
    """

    __slots__ = (

        "_profiles",

        "_default_profile",

        "_stop_on_first_error",

        "_catch_exceptions",

    )

    def __init__(
        self,
        *,
        default_profile: ValidationProfileName = "default",
        stop_on_first_error: bool = False,
        catch_exceptions: bool = True,
    ) -> None:

        self._profiles: Dict[
            ValidationProfileName,
            ValidationProfile,
        ] = {}

        self._default_profile = _normalize_code(
            default_profile,
        )

        self._stop_on_first_error = bool(
            stop_on_first_error,
        )

        self._catch_exceptions = bool(
            catch_exceptions,
        )

    @property
    def default_profile(
        self,
    ) -> ValidationProfileName:

        return self._default_profile

    @property
    def stop_on_first_error(
        self,
    ) -> bool:

        return self._stop_on_first_error

    @property
    def catch_exceptions(
        self,
    ) -> bool:

        return self._catch_exceptions

    @property
    def profiles(
        self,
    ) -> Tuple[
        ValidationProfile,
        ...,
    ]:

        return tuple(
            self._profiles.values(),
        )

    def set_default_profile(
        self,
        name: ValidationProfileName,
    ) -> None:

        normalized = _normalize_code(
            name,
        )

        if normalized not in self._profiles:

            raise KeyError(
                (
                    "Unknown validation profile: "
                    f"{normalized!r}"
                )
            )

        self._default_profile = normalized

    def register(
        self,
        profile: ValidationProfile,
        *,
        replace: bool = False,
    ) -> "RulePipeline":

        if not isinstance(
            profile,
            ValidationProfile,
        ):

            raise TypeError(
                (
                    "profile must be an instance "
                    "of ValidationProfile"
                )
            )

        if (
            profile.name in self._profiles
            and not replace
        ):

            raise ValueError(
                (
                    "Validation profile already "
                    f"registered: {profile.name!r}"
                )
            )

        self._profiles[
            profile.name
        ] = profile

        return self

    def unregister(
        self,
        name: ValidationProfileName,
    ) -> Optional[
        ValidationProfile
    ]:

        normalized = _normalize_code(
            name,
        )

        return self._profiles.pop(
            normalized,
            None,
        )

    def get(
        self,
        name: Optional[
            ValidationProfileName
        ] = None,
    ) -> Optional[
        ValidationProfile
    ]:

        normalized = _normalize_code(
            name or self.default_profile,
        )

        return self._profiles.get(
            normalized,
        )

    def require(
        self,
        name: Optional[
            ValidationProfileName
        ] = None,
    ) -> ValidationProfile:

        normalized = _normalize_code(
            name or self.default_profile,
        )

        profile = self.get(
            normalized,
        )

        if profile is None:

            raise KeyError(
                (
                    "Unknown validation profile: "
                    f"{normalized!r}"
                )
            )

        return profile

    def contains(
        self,
        name: ValidationProfileName,
    ) -> bool:

        return (

            _normalize_code(
                name,
            )

            in self._profiles

        )

    def clear(
        self,
    ) -> None:

        self._profiles.clear()

    def execute(
        self,
        context: ValidationContext[
            ValidationSubject
        ],
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        include_tags: Optional[
            Iterable[
                ValidationRuleTag
            ]
        ] = None,
        exclude_tags: Optional[
            Iterable[
                ValidationRuleTag
            ]
        ] = None,
        minimum_severity: Optional[
            ValidationSeverity
        ] = None,
        stop_on_first_error: Optional[
            bool
        ] = None,
        catch_exceptions: Optional[
            bool
        ] = None,
        validator: str = "rule_pipeline",
    ) -> ValidationResult:
        """
        Executes the selected profile against a validation context.

        All supported rule outputs are normalized into one
        ValidationResult instance.
        """

        selected_profile = self.require(
            profile or context.profile,
        )

        context.profile = selected_profile.name

        result = ValidationResult(
            validator=validator,
        )

        included_tags = frozenset(

            _normalize_code(
                tag,
            )

            for tag in (
                include_tags or ()
            )

            if str(
                tag,
            ).strip()

        )

        excluded_tags = frozenset(

            _normalize_code(
                tag,
            )

            for tag in (
                exclude_tags or ()
            )

            if str(
                tag,
            ).strip()

        )

        severity_threshold = (

            ValidationSeverity.coerce(
                minimum_severity,
            )

            if minimum_severity is not None

            else None

        )

        should_stop = (

            self.stop_on_first_error

            if stop_on_first_error is None

            else bool(
                stop_on_first_error,
            )

        )

        should_catch = (

            self.catch_exceptions

            if catch_exceptions is None

            else bool(
                catch_exceptions,
            )

        )

        for rule in selected_profile:

            if not self._should_execute_rule(

                rule=rule,

                include_tags=included_tags,

                exclude_tags=excluded_tags,

                minimum_severity=severity_threshold,

            ):

                continue

            try:

                output = rule(
                    context,
                )

            except Exception as error:

                if not should_catch:

                    raise

                output = ValidationIssue(

                    code=(
                        "validation.rule.execution_error"
                    ),

                    message=(

                        "Validation rule "
                        f"{rule.name!r} failed: "
                        f"{type(error).__name__}: "
                        f"{error}"

                    ),

                    severity=(
                        ValidationSeverity.CRITICAL
                    ),

                    path=context.path,

                    validator=validator,

                    rule=rule.name,

                    hint=(
                        "Review the rule implementation "
                        "or disable exception catching "
                        "to propagate the original error."
                    ),

                    metadata={

                        "exception_type": (
                            type(
                                error
                            ).__name__
                        ),

                        "profile": (
                            selected_profile.name
                        ),

                    },

                )

            self._consume_output(

                output=output,

                result=result,

                context=context,

                rule=rule,

                validator=validator,

            )

            if (
                should_stop
                and result.invalid
            ):

                break

        result.finish()

        return result

    @staticmethod
    def _should_execute_rule(
        *,
        rule: ValidationRule[Any],
        include_tags: Set[
            ValidationRuleTag
        ],
        exclude_tags: Set[
            ValidationRuleTag
        ],
        minimum_severity: Optional[
            ValidationSeverity
        ],
    ) -> bool:

        if not rule.enabled:

            return False

        rule_tags = set(
            rule.tags,
        )

        if (
            include_tags
            and rule_tags.isdisjoint(
                include_tags,
            )
        ):

            return False

        if (
            exclude_tags
            and not rule_tags.isdisjoint(
                exclude_tags,
            )
        ):

            return False

        if (
            minimum_severity is not None
            and rule.severity.rank
            < minimum_severity.rank
        ):

            return False

        return True

    @classmethod
    def _consume_output(
        cls,
        *,
        output: RuleOutput,
        result: ValidationResult,
        context: ValidationContext[Any],
        rule: ValidationRule[Any],
        validator: str,
    ) -> None:

        if output is None:

            return

        if isinstance(
            output,
            bool,
        ):

            if output:

                return

            result.extend(
                (
                    cls._default_issue(

                        context=context,

                        rule=rule,

                        validator=validator,

                    ),
                )
            )

            return

        if isinstance(
            output,
            str,
        ):

            normalized_message = (
                output.strip()
            )

            if not normalized_message:

                return

            result.extend(
                (
                    cls._default_issue(

                        context=context,

                        rule=rule,

                        validator=validator,

                        message=normalized_message,

                    ),
                )
            )

            return

        if isinstance(
            output,
            ValidationIssue,
        ):

            result.extend(
                (
                    output,
                )
            )

            return

        if isinstance(
            output,
            ValidationResult,
        ):

            result.merge(
                output,
            )

            return

        if isinstance(
            output,
            IterableABC,
        ):

            issues: List[
                ValidationIssue
            ] = []

            for item in output:

                if not isinstance(
                    item,
                    ValidationIssue,
                ):

                    raise TypeError(
                        (
                            "Rule output iterable must "
                            "contain only ValidationIssue "
                            "instances"
                        )
                    )

                issues.append(
                    item,
                )

            result.extend(
                issues,
            )

            return

        raise TypeError(
            (
                "Unsupported validation rule output: "
                f"{type(output).__name__}"
            )
        )

    @staticmethod
    def _default_issue(
        *,
        context: ValidationContext[Any],
        rule: ValidationRule[Any],
        validator: str,
        message: Optional[
            str
        ] = None,
    ) -> ValidationIssue:

        return ValidationIssue(

            code=(
                f"validation.rule.{rule.name}"
            ),

            message=(

                message

                or rule.description

                or (
                    "Validation rule "
                    f"{rule.name!r} failed."
                )

            ),

            severity=rule.severity,

            path=context.path,

            validator=validator,

            rule=rule.name,

            metadata={

                "profile": context.profile,

                "tags": sorted(
                    rule.tags,
                ),

            },

        )

    def __iter__(
        self,
    ) -> Iterator[
        ValidationProfile
    ]:

        return iter(
            self._profiles.values(),
        )

    def __len__(
        self,
    ) -> int:

        return len(
            self._profiles,
        )

    def __contains__(
        self,
        name: object,
    ) -> bool:

        if not isinstance(
            name,
            str,
        ):

            return False

        return self.contains(
            name,
        )

    def __call__(
        self,
        context: ValidationContext[
            ValidationSubject
        ],
        **kwargs: Any,
    ) -> ValidationResult:

        return self.execute(
            context,
            **kwargs,
        )

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"default_profile="
            f"{self.default_profile!r}, "

            f"profiles={len(self)!r}, "

            f"stop_on_first_error="
            f"{self.stop_on_first_error!r}, "

            f"catch_exceptions="
            f"{self.catch_exceptions!r})"

        )
        
    ###############################################################################
# VALIDATION STATISTICS
###############################################################################


@dataclass(
    slots=True,
)
class ValidationStatistics:
    """
    Aggregated runtime statistics for a ValidationEngine.

    Statistics are updated after every validation execution and
    can be reset without modifying the engine configuration.
    """

    validation_count: int = 0

    valid_count: int = 0

    invalid_count: int = 0

    issue_count: int = 0

    exception_count: int = 0

    total_duration: float = 0.0

    last_duration: float = 0.0

    last_profile: str = ""

    last_validator: str = ""

    last_error: str = ""

    @property
    def average_duration(
        self,
    ) -> float:

        if self.validation_count == 0:

            return 0.0

        return (

            self.total_duration

            / self.validation_count

        )

    @property
    def success_rate(
        self,
    ) -> float:

        if self.validation_count == 0:

            return 0.0

        return (

            self.valid_count

            / self.validation_count

        )

    @property
    def failure_rate(
        self,
    ) -> float:

        if self.validation_count == 0:

            return 0.0

        return (

            self.invalid_count

            / self.validation_count

        )

    def record_result(
        self,
        result: ValidationResult,
        *,
        duration: float,
        profile: ValidationProfileName,
    ) -> None:

        self.validation_count += 1

        self.issue_count += (
            result.issue_count
        )

        self.total_duration += max(
            0.0,
            duration,
        )

        self.last_duration = max(
            0.0,
            duration,
        )

        self.last_profile = (
            _normalize_code(
                profile,
            )
        )

        self.last_validator = (
            result.validator
        )

        self.last_error = ""

        if result.valid:

            self.valid_count += 1

        else:

            self.invalid_count += 1

    def record_exception(
        self,
        error: Exception,
        *,
        duration: float,
        profile: ValidationProfileName,
    ) -> None:

        self.exception_count += 1

        self.total_duration += max(
            0.0,
            duration,
        )

        self.last_duration = max(
            0.0,
            duration,
        )

        self.last_profile = (
            _normalize_code(
                profile,
            )
        )

        self.last_error = (

            f"{type(error).__name__}: "
            f"{error}"

        )

    def reset(
        self,
    ) -> None:

        self.validation_count = 0

        self.valid_count = 0

        self.invalid_count = 0

        self.issue_count = 0

        self.exception_count = 0

        self.total_duration = 0.0

        self.last_duration = 0.0

        self.last_profile = ""

        self.last_validator = ""

        self.last_error = ""

    def copy(
        self,
    ) -> "ValidationStatistics":

        return ValidationStatistics(

            validation_count=(
                self.validation_count
            ),

            valid_count=(
                self.valid_count
            ),

            invalid_count=(
                self.invalid_count
            ),

            issue_count=(
                self.issue_count
            ),

            exception_count=(
                self.exception_count
            ),

            total_duration=(
                self.total_duration
            ),

            last_duration=(
                self.last_duration
            ),

            last_profile=(
                self.last_profile
            ),

            last_validator=(
                self.last_validator
            ),

            last_error=(
                self.last_error
            ),

        )

    def to_dict(
        self,
    ) -> JSONDict:

        return {

            "validation_count": (
                self.validation_count
            ),

            "valid_count": (
                self.valid_count
            ),

            "invalid_count": (
                self.invalid_count
            ),

            "issue_count": (
                self.issue_count
            ),

            "exception_count": (
                self.exception_count
            ),

            "total_duration": (
                self.total_duration
            ),

            "average_duration": (
                self.average_duration
            ),

            "last_duration": (
                self.last_duration
            ),

            "success_rate": (
                self.success_rate
            ),

            "failure_rate": (
                self.failure_rate
            ),

            "last_profile": (
                self.last_profile
            ),

            "last_validator": (
                self.last_validator
            ),

            "last_error": (
                self.last_error
            ),

        }

    def __bool__(
        self,
    ) -> bool:

        return self.validation_count > 0

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"validations="
            f"{self.validation_count!r}, "

            f"valid={self.valid_count!r}, "

            f"invalid={self.invalid_count!r}, "

            f"exceptions="
            f"{self.exception_count!r})"

        )
    
    
    ###############################################################################
    # VALIDATION ENGINE
    ###############################################################################


class ValidationEngine:
    """
    High-level entry point of the validation framework.

    The engine owns the validation pipeline, manages validation
    profiles and provides a simplified public API for executing
    validations.

    Most users should interact only with ValidationEngine.
    """

    __slots__ = (

        "_pipeline",

        "_default_profile",

        "_metadata",

        "_statistics",

        "_before_validation_hooks",

        "_after_validation_hooks",

        "_validation_error_hooks",

    )

    def __init__(
        self,
        *,
        default_profile: ValidationProfileName = "default",
        stop_on_first_error: bool = False,
        catch_exceptions: bool = True,
    ) -> None:

        self._pipeline = RulePipeline(

            default_profile=default_profile,

            stop_on_first_error=(
                stop_on_first_error
            ),

            catch_exceptions=(
                catch_exceptions
            ),

        )

        self._default_profile = (
            _normalize_code(
                default_profile,
            )
        )

        self._metadata: ValidationMetadata = {}
        
        self._statistics = (
            ValidationStatistics()
        )

        self._before_validation_hooks: List[
            BeforeValidationHook
        ] = []

        self._after_validation_hooks: List[
            AfterValidationHook
        ] = []

        self._validation_error_hooks: List[
            ValidationErrorHook
        ] = []

    @property
    def pipeline(
        self,
    ) -> RulePipeline:

        return self._pipeline

    @property
    def default_profile(
        self,
    ) -> ValidationProfileName:

        return self._default_profile

    @property
    def metadata(
        self,
    ) -> ValidationMetadata:

        return self._metadata

    @property
    def statistics(
        self,
    ) -> ValidationStatistics:

        return self._statistics

    @property
    def before_validation_hooks(
        self,
    ) -> Tuple[
        BeforeValidationHook,
        ...,
    ]:

        return tuple(
            self._before_validation_hooks,
        )

    @property
    def after_validation_hooks(
        self,
    ) -> Tuple[
        AfterValidationHook,
        ...,
    ]:

        return tuple(
            self._after_validation_hooks,
        )

    @property
    def validation_error_hooks(
        self,
    ) -> Tuple[
        ValidationErrorHook,
        ...,
    ]:

        return tuple(
            self._validation_error_hooks,
        )
    
    def register_profile(
        self,
        profile: ValidationProfile,
        *,
        replace: bool = False,
    ) -> "ValidationEngine":

        self.pipeline.register(

            profile,

            replace=replace,

        )

        return self

    def unregister_profile(
        self,
        name: ValidationProfileName,
    ) -> Optional[
        ValidationProfile
    ]:

        return self.pipeline.unregister(
            name,
        )

    def get_profile(
        self,
        name: Optional[
            ValidationProfileName
        ] = None,
    ) -> Optional[
        ValidationProfile
    ]:

        return self.pipeline.get(
            name,
        )

    def require_profile(
        self,
        name: Optional[
            ValidationProfileName
        ] = None,
    ) -> ValidationProfile:

        return self.pipeline.require(
            name,
        )

    def contains_profile(
        self,
        name: ValidationProfileName,
    ) -> bool:

        return self.pipeline.contains(
            name,
        )

    def profiles(
        self,
    ) -> Tuple[
        ValidationProfile,
        ...,
    ]:

        return self.pipeline.profiles

    def clear_profiles(
        self,
    ) -> None:

        self.pipeline.clear()

    def create_context(
        self,
        subject: ValidationSubject,
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        path: ValidationPath = (),
        metadata: Optional[
            ValidationMetadata
        ] = None,
        state: Optional[
            ValidationState
        ] = None,
        services: Optional[
            MutableMapping[
                str,
                Any,
            ]
        ] = None,
    ) -> ValidationContext[
        ValidationSubject
    ]:
        """
        Creates a ValidationContext for a subject.
        """

        return ValidationContext(

            subject=subject,

            profile=(
                profile
                or self.default_profile
            ),

            path=path,

            metadata=(
                metadata
                if metadata is not None
                else {}
            ),

            state=(
                state
                if state is not None
                else {}
            ),

            services=(
                services
                if services is not None
                else {}
            ),

        )

    def set_default_profile(
        self,
        profile: ValidationProfileName,
    ) -> None:

        normalized = _normalize_code(
            profile,
        )

        self.pipeline.set_default_profile(
            normalized,
        )

        self._default_profile = (
            normalized
        )

    def configure(
        self,
        *,
        metadata: Optional[
            ValidationMetadata
        ] = None,
    ) -> "ValidationEngine":

        if metadata:

            self.metadata.update(
                metadata,
            )

        return self

    def __len__(
        self,
    ) -> int:

        return len(
            self.pipeline,
        )

    def __contains__(
        self,
        name: object,
    ) -> bool:

        if not isinstance(
            name,
            str,
        ):

            return False

        return self.contains_profile(
            name,
        )
        
    ###########################################################################
    # VALIDATION
    ###########################################################################

    def validate(
        self,
        subject: ValidationSubject,
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        path: ValidationPath = (),
        metadata: Optional[
            ValidationMetadata
        ] = None,
        state: Optional[
            ValidationState
        ] = None,
        services: Optional[
            MutableMapping[
                str,
                Any,
            ]
        ] = None,
        **kwargs: Any,
    ) -> ValidationResult:
        """
        Validates a subject.

        This is the primary public API.
        """

        context = self.create_context(

            subject=subject,

            profile=profile,

            path=path,

            metadata=metadata,

            state=state,

            services=services,

        )

        return self.validate_context(

            context,

            **kwargs,

        )

    def validate_context(
        self,
        context: ValidationContext[
            ValidationSubject
        ],
        **kwargs: Any,
    ) -> ValidationResult:
        """
        Executes validation using an existing context.

        Registered hooks are invoked before and after execution.
        Runtime metrics are recorded automatically.
        """

        if not isinstance(
            context,
            ValidationContext,
        ):

            raise TypeError(
                (
                    "context must be an instance "
                    "of ValidationContext"
                )
            )

        started_at = perf_counter()

        try:

            self._run_before_validation_hooks(
                context,
            )

            result = self.pipeline.execute(

                context,

                **kwargs,

            )

            self._run_after_validation_hooks(

                context,

                result,

            )

        except Exception as error:

            duration = (

                perf_counter()

                - started_at

            )

            self.statistics.record_exception(

                error,

                duration=duration,

                profile=context.profile,

            )

            self._run_validation_error_hooks(

                context,

                error,

            )

            raise

        duration = (

            perf_counter()

            - started_at

        )

        self.statistics.record_result(

            result,

            duration=duration,

            profile=context.profile,

        )

        return result

    def validate_many(
        self,
        subjects: Iterable[
            ValidationSubject
        ],
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        stop_on_first_invalid: bool = False,
        **kwargs: Any,
    ) -> List[
        ValidationResult
    ]:
        """
        Validates multiple subjects.
        """

        results: List[
            ValidationResult
        ] = []

        for subject in subjects:

            result = self.validate(

                subject,

                profile=profile,

                **kwargs,

            )

            results.append(
                result,
            )

            if (
                stop_on_first_invalid
                and result.invalid
            ):

                break

        return results

    def validate_iterable(
        self,
        subjects: Iterable[
            ValidationSubject
        ],
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        **kwargs: Any,
    ) -> Iterator[
        ValidationResult
    ]:
        """
        Lazily validates an iterable.
        """

        for subject in subjects:

            yield self.validate(

                subject,

                profile=profile,

                **kwargs,

            )

    def is_valid(
        self,
        subject: ValidationSubject,
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Returns True when the subject is valid.
        """

        return self.validate(

            subject,

            profile=profile,

            **kwargs,

        ).valid

    def first_issue(
        self,
        subject: ValidationSubject,
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        **kwargs: Any,
    ) -> Optional[
        ValidationIssue
    ]:
        """
        Returns the first validation issue.
        """

        result = self.validate(

            subject,

            profile=profile,

            **kwargs,

        )

        if result.issues:

            return result.issues[0]

        return None

    def raise_for_errors(
        self,
        subject: ValidationSubject,
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        **kwargs: Any,
    ) -> None:
        """
        Validates a subject and raises when errors exist.
        """

        self.validate(

            subject,

            profile=profile,

            **kwargs,

        ).raise_for_errors()


    ###########################################################################
    # HOOKS AND INSTRUMENTATION
    ###########################################################################

    def add_before_validation_hook(
        self,
        hook: BeforeValidationHook,
    ) -> "ValidationEngine":

        self._require_callable_hook(
            hook,
        )

        if hook not in (
            self._before_validation_hooks
        ):

            self._before_validation_hooks.append(
                hook,
            )

        return self

    def add_after_validation_hook(
        self,
        hook: AfterValidationHook,
    ) -> "ValidationEngine":

        self._require_callable_hook(
            hook,
        )

        if hook not in (
            self._after_validation_hooks
        ):

            self._after_validation_hooks.append(
                hook,
            )

        return self

    def add_validation_error_hook(
        self,
        hook: ValidationErrorHook,
    ) -> "ValidationEngine":

        self._require_callable_hook(
            hook,
        )

        if hook not in (
            self._validation_error_hooks
        ):

            self._validation_error_hooks.append(
                hook,
            )

        return self

    def remove_before_validation_hook(
        self,
        hook: BeforeValidationHook,
    ) -> bool:

        return self._remove_hook(

            self._before_validation_hooks,

            hook,

        )

    def remove_after_validation_hook(
        self,
        hook: AfterValidationHook,
    ) -> bool:

        return self._remove_hook(

            self._after_validation_hooks,

            hook,

        )

    def remove_validation_error_hook(
        self,
        hook: ValidationErrorHook,
    ) -> bool:

        return self._remove_hook(

            self._validation_error_hooks,

            hook,

        )

    def clear_hooks(
        self,
    ) -> None:

        self._before_validation_hooks.clear()

        self._after_validation_hooks.clear()

        self._validation_error_hooks.clear()

    def reset_statistics(
        self,
    ) -> None:

        self.statistics.reset()

    def statistics_snapshot(
        self,
    ) -> ValidationStatistics:

        return self.statistics.copy()

    def snapshot(
        self,
    ) -> JSONDict:

        return {

            "default_profile": (
                self.default_profile
            ),

            "profiles": [

                profile.name

                for profile in (
                    self.profiles()
                )

            ],

            "metadata": dict(
                self.metadata,
            ),

            "hooks": {

                "before_validation": len(
                    self._before_validation_hooks
                ),

                "after_validation": len(
                    self._after_validation_hooks
                ),

                "validation_error": len(
                    self._validation_error_hooks
                ),

            },

            "statistics": (
                self.statistics.to_dict()
            ),

        }

    def _run_before_validation_hooks(
        self,
        context: ValidationContext[Any],
    ) -> None:

        for hook in tuple(
            self._before_validation_hooks,
        ):

            hook(
                context,
            )

    def _run_after_validation_hooks(
        self,
        context: ValidationContext[Any],
        result: ValidationResult,
    ) -> None:

        for hook in tuple(
            self._after_validation_hooks,
        ):

            hook(

                context,

                result,

            )

    def _run_validation_error_hooks(
        self,
        context: ValidationContext[Any],
        error: Exception,
    ) -> None:

        for hook in tuple(
            self._validation_error_hooks,
        ):

            try:

                hook(

                    context,

                    error,

                )

            except Exception:

                continue

    @staticmethod
    def _require_callable_hook(
        hook: Callable[
            ...,
            Any,
        ],
    ) -> None:

        if not callable(
            hook,
        ):

            raise TypeError(
                "validation hook must be callable"
            )

    @staticmethod
    def _remove_hook(
        hooks: List[
            Callable[
                ...,
                Any,
            ]
        ],
        hook: Callable[
            ...,
            Any,
        ],
    ) -> bool:

        try:

            hooks.remove(
                hook,
            )

        except ValueError:

            return False

        return True


    def __repr__(
        self,
    ) -> str:

        hook_count = (

            len(
                self._before_validation_hooks
            )

            + len(
                self._after_validation_hooks
            )

            + len(
                self._validation_error_hooks
            )

        )

        return (

            f"{type(self).__name__}("

            f"default_profile="
            f"{self.default_profile!r}, "

            f"profiles={len(self)!r}, "

            f"validations="
            f"{self.statistics.validation_count!r}, "

            f"hooks={hook_count!r})"

        )
     
        
###############################################################################
# ASSET VALIDATOR
###############################################################################


class AssetValidator(
    ValidationEngine,
):
    """
    Validador especializado para KnowledgeAsset.

    AssetValidator extiende ValidationEngine y proporciona perfiles
    de validación específicos para los activos de conocimiento.

    Perfiles disponibles:

        • default
        • strict
        • fast
        • import
        • api

    En esta primera entrega los perfiles se registran como estructuras
    vacías. Las reglas concretas se incorporarán progresivamente en las
    siguientes entregas.

    AssetValidator conserva toda la infraestructura de ValidationEngine:

        • estadísticas
        • hooks
        • contextos
        • perfiles
        • pipelines
        • filtrado por tags
        • control de excepciones
        • resultados estructurados
    """

    __slots__ = ()

    ###########################################################################
    # IDENTIDAD
    ###########################################################################

    VALIDATOR_NAME = "asset_validator"

    SUBJECT_TYPE = KnowledgeAsset

    ###########################################################################
    # PERFILES
    ###########################################################################

    PROFILE_DEFAULT = "default"

    PROFILE_STRICT = "strict"

    PROFILE_FAST = "fast"

    PROFILE_IMPORT = "import"

    PROFILE_API = "api"

    SUPPORTED_PROFILES: Tuple[
        ValidationProfileName,
        ...,
    ] = (
        PROFILE_DEFAULT,
        PROFILE_STRICT,
        PROFILE_FAST,
        PROFILE_IMPORT,
        PROFILE_API,
    )

    ###########################################################################
    # CONSTRUCTOR
    ###########################################################################

    def __init__(
        self,
        *,
        default_profile: ValidationProfileName = PROFILE_DEFAULT,
        stop_on_first_error: bool = False,
        catch_exceptions: bool = True,
    ) -> None:
        """
        Inicializa el validador y registra sus perfiles de dominio.
        """

        normalized_profile = _normalize_code(
            default_profile,
        )

        if normalized_profile not in self.SUPPORTED_PROFILES:

            raise ValueError(
                (
                    "Perfil no soportado por AssetValidator: "
                    f"{default_profile!r}. "
                    "Perfiles disponibles: "
                    f"{', '.join(self.SUPPORTED_PROFILES)}."
                )
            )

        super().__init__(
            default_profile=normalized_profile,
            stop_on_first_error=stop_on_first_error,
            catch_exceptions=catch_exceptions,
        )

        self.metadata.update(
            {
                "validator": self.VALIDATOR_NAME,
                "subject_type": (
                    self.SUBJECT_TYPE.__name__
                ),
                "supported_profiles": list(
                    self.SUPPORTED_PROFILES,
                ),
            }
        )

        self._register_asset_profiles()

    ###########################################################################
    # REGISTRO DE PERFILES
    ###########################################################################

    def _register_asset_profiles(
        self,
    ) -> None:
        """
        Construye y registra todos los perfiles de AssetValidator.

        En la Entrega 8A los perfiles se crean sin reglas. Las reglas
        concretas se añadirán en las siguientes entregas.
        """

        for profile in self._build_asset_profiles():

            self.register_profile(
                profile,
            )

    ###########################################################################

    def _build_asset_profiles(
        self,
    ) -> Tuple[
        ValidationProfile,
        ...,
    ]:
        """
        Construye las estrategias de validación disponibles.
        """

        return (
            ValidationProfile(
                self.PROFILE_DEFAULT,
                description=(
                    "Validación general de un KnowledgeAsset."
                ),
            ),
            ValidationProfile(
                self.PROFILE_STRICT,
                description=(
                    "Validación exhaustiva y estricta de un "
                    "KnowledgeAsset."
                ),
            ),
            ValidationProfile(
                self.PROFILE_FAST,
                description=(
                    "Validación rápida de campos esenciales."
                ),
            ),
            ValidationProfile(
                self.PROFILE_IMPORT,
                description=(
                    "Validación de activos procedentes de procesos "
                    "de importación."
                ),
            ),
            ValidationProfile(
                self.PROFILE_API,
                description=(
                    "Validación de activos recibidos o expuestos "
                    "mediante una API."
                ),
            ),
        )

    ###########################################################################
    # API ESPECIALIZADA
    ###########################################################################

    def validate(
        self,
        subject: KnowledgeAsset,
        *,
        profile: Optional[
            ValidationProfileName
        ] = None,
        path: ValidationPath = (),
        metadata: Optional[
            ValidationMetadata
        ] = None,
        state: Optional[
            ValidationState
        ] = None,
        services: Optional[
            MutableMapping[
                str,
                Any,
            ]
        ] = None,
        **kwargs: Any,
    ) -> ValidationResult:
        """
        Valida un KnowledgeAsset utilizando el perfil seleccionado.

        La comprobación estricta del tipo y las reglas específicas se
        incorporarán en la Entrega 8B.
        """

        kwargs.setdefault(
            "validator",
            self.VALIDATOR_NAME,
        )

        return super().validate(
            subject,
            profile=profile,
            path=path,
            metadata=metadata,
            state=state,
            services=services,
            **kwargs,
        )

    ###########################################################################
    # CONSULTAS
    ###########################################################################

    @classmethod
    def supports_profile(
        cls,
        profile: ValidationProfileName,
    ) -> bool:
        """
        Indica si AssetValidator reconoce un perfil.
        """

        return (
            _normalize_code(
                profile,
            )
            in cls.SUPPORTED_PROFILES
        )

    ###########################################################################

    @property
    def subject_type(
        self,
    ) -> Type[
        KnowledgeAsset
    ]:
        """
        Tipo de objeto administrado por este validador.
        """

        return self.SUBJECT_TYPE

    ###########################################################################

    def __repr__(
        self,
    ) -> str:

        return (
            f"{type(self).__name__}("
            f"default_profile={self.default_profile!r}, "
            f"profiles={len(self.profiles())!r}, "
            f"validations="
            f"{self.statistics.validation_count!r})"
        )