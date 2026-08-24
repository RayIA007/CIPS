"""Explicit failures for the universal render adapter boundary."""

from __future__ import annotations


class RenderAdapterError(RuntimeError):
    """Base error for render-boundary failures."""


class RenderAdapterContractError(RenderAdapterError):
    """An adapter or compiled plan violates the universal contract."""


class RenderCompilationError(RenderAdapterError):
    """A target adapter could not compile an inspectable render payload."""


class RenderCapabilityError(RenderAdapterError):
    """The selected target cannot represent required manifest features."""

    def __init__(self, target_id: str, unsupported: tuple[str, ...]) -> None:
        normalized = tuple(sorted(set(unsupported)))
        if not normalized:
            raise ValueError("unsupported debe contener al menos una capability.")
        self.target_id = target_id
        self.unsupported = normalized
        super().__init__(
            f"El target '{target_id}' no soporta: " + ", ".join(normalized) + "."
        )


__all__ = [
    "RenderAdapterContractError",
    "RenderAdapterError",
    "RenderCapabilityError",
    "RenderCompilationError",
]
