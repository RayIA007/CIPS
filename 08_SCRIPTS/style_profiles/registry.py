"""Deterministic registry and geometry resolver for CIPS style profiles."""

from __future__ import annotations

from collections.abc import Iterable

from .builtins import BUILTIN_STYLE_PROFILES
from .models import LayoutPolicy, StyleProfile, classify_output_layout


class StyleProfileRegistryError(ValueError):
    """Raised when profile registration or strict resolution fails."""


class StyleProfileRegistry:
    """Immutable-by-convention registry with explicit duplicate protection."""

    def __init__(self, profiles: Iterable[StyleProfile] = ()) -> None:
        registered: dict[str, StyleProfile] = {}
        for profile in profiles:
            if not isinstance(profile, StyleProfile):
                raise TypeError("profiles solo acepta StyleProfile.")
            if profile.profile_id in registered:
                raise StyleProfileRegistryError(
                    f"Perfil de estilo duplicado: {profile.profile_id}."
                )
            registered[profile.profile_id] = profile
        self._profiles = registered

    def get(self, profile_id: str) -> StyleProfile | None:
        """Return a registered profile, or None for legacy/custom IDs."""

        normalized = str(profile_id).strip()
        if not normalized:
            raise ValueError("profile_id no puede estar vacío.")
        return self._profiles.get(normalized)

    def require(self, profile_id: str) -> StyleProfile:
        profile = self.get(profile_id)
        if profile is None:
            raise StyleProfileRegistryError(
                f"Perfil de estilo no registrado: {str(profile_id).strip()}."
            )
        return profile

    def list_profiles(self) -> tuple[StyleProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def resolve_layout(
        self,
        profile_id: str,
        *,
        width_px: int,
        height_px: int,
    ) -> LayoutPolicy:
        profile = self.require(profile_id)
        family = classify_output_layout(width_px, height_px)
        return profile.composition.layout_for(family)


DEFAULT_STYLE_PROFILE_REGISTRY = StyleProfileRegistry(BUILTIN_STYLE_PROFILES)


def get_style_profile(profile_id: str) -> StyleProfile | None:
    return DEFAULT_STYLE_PROFILE_REGISTRY.get(profile_id)


def list_style_profiles() -> tuple[StyleProfile, ...]:
    return DEFAULT_STYLE_PROFILE_REGISTRY.list_profiles()


def resolve_style_layout(
    profile_id: str,
    *,
    width_px: int,
    height_px: int,
) -> LayoutPolicy:
    return DEFAULT_STYLE_PROFILE_REGISTRY.resolve_layout(
        profile_id,
        width_px=width_px,
        height_px=height_px,
    )


__all__ = [
    "DEFAULT_STYLE_PROFILE_REGISTRY",
    "StyleProfileRegistry",
    "StyleProfileRegistryError",
    "get_style_profile",
    "list_style_profiles",
    "resolve_style_layout",
]
