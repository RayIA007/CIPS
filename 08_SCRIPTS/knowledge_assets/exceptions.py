###############################################################################
# exceptions.py
#
# Knowledge Assets Library
#
# Jerarquía central de excepciones para la infraestructura de activos
# de conocimiento.
###############################################################################

from __future__ import annotations

###############################################################################
# STANDARD LIBRARY
###############################################################################

from typing import Any
from typing import Optional


###############################################################################
# BASE EXCEPTION
###############################################################################


class KnowledgeAssetsError(Exception):
    """
    Base exception for the Knowledge Assets Library.

    Every library-specific exception should inherit from this class so
    callers can capture infrastructure errors through a single common type.
    """

    __slots__ = (
        "message",
        "code",
        "details",
    )

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Any = None,
    ) -> None:

        normalized_message = str(
            message
        ).strip()

        self.message = (
            normalized_message
            or type(self).__name__
        )

        self.code = (
            str(code).strip()
            if code is not None
            else None
        )

        self.details = details

        super().__init__(
            self.message
        )

    def __str__(
        self,
    ) -> str:

        if self.code:

            return (
                f"[{self.code}] "
                f"{self.message}"
            )

        return self.message

    def __repr__(
        self,
    ) -> str:

        return (

            f"{type(self).__name__}("

            f"message={self.message!r}, "

            f"code={self.code!r}, "

            f"details={self.details!r})"

        )


###############################################################################
# CONFIGURATION EXCEPTIONS
###############################################################################


class ConfigurationError(
    KnowledgeAssetsError
):
    """
    Raised when the library receives an invalid configuration.
    """


###############################################################################


class RegistrationError(
    KnowledgeAssetsError
):
    """
    Raised when an object cannot be registered.
    """


###############################################################################


class DuplicateRegistrationError(
    RegistrationError
):
    """
    Raised when an object is registered more than once.
    """


###############################################################################


class RegistryLookupError(
    RegistrationError
):
    """
    Raised when a requested registry entry cannot be found.
    """


###############################################################################
# VALIDATION EXCEPTIONS
###############################################################################


class ValidationError(
    KnowledgeAssetsError
):
    """
    Raised when one or more validation errors invalidate a subject.

    The optional result attribute may contain the ValidationResult that
    caused the exception. It intentionally uses Any to avoid a circular
    dependency with validators.py.
    """

    __slots__ = (
        "result",
    )

    def __init__(
        self,
        message: str = "Validation failed.",
        *,
        result: Any = None,
        code: Optional[str] = "validation.failed",
        details: Any = None,
    ) -> None:

        self.result = result

        if details is None and result is not None:

            details = result

        super().__init__(

            message,

            code=code,

            details=details,

        )


###############################################################################
# IDENTIFIER EXCEPTIONS
###############################################################################


class IdentifierError(
    KnowledgeAssetsError
):
    """
    Raised when an identifier is missing, malformed or incompatible.
    """


###############################################################################
# SERIALIZATION EXCEPTIONS
###############################################################################


class SerializationError(
    KnowledgeAssetsError
):
    """
    Raised when an object cannot be serialized.
    """


###############################################################################


class DeserializationError(
    SerializationError
):
    """
    Raised when serialized data cannot be converted into an object.
    """


###############################################################################
# RELATIONSHIP EXCEPTIONS
###############################################################################


class RelationshipError(
    KnowledgeAssetsError
):
    """
    Raised when a knowledge relationship is invalid.
    """


###############################################################################
# GRAPH EXCEPTIONS
###############################################################################


class GraphError(
    KnowledgeAssetsError
):
    """
    Raised when a knowledge graph operation fails.
    """


###############################################################################
# PUBLIC API
###############################################################################


__all__ = [

    "KnowledgeAssetsError",

    "ConfigurationError",

    "RegistrationError",

    "DuplicateRegistrationError",

    "RegistryLookupError",

    "ValidationError",

    "IdentifierError",

    "SerializationError",

    "DeserializationError",

    "RelationshipError",

    "GraphError",

]