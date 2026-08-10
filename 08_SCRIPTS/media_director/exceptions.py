from __future__ import annotations


class MediaDirectorError(RuntimeError):
    """Error base del dominio MediaDirector."""


class MediaRequestValidationError(ValueError, MediaDirectorError):
    """La solicitud multimedia no satisface el contrato de la estrategia."""


class MediaResultValidationError(ValueError, MediaDirectorError):
    """El resultado multimedia no satisface el contrato de la estrategia."""


__all__ = [
    "MediaDirectorError",
    "MediaRequestValidationError",
    "MediaResultValidationError",
]
