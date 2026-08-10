"""Utilidades compartidas para nombres de proveedores LLM de CIPS."""


def normalize_provider_name(provider_name: str) -> str:
    """Normaliza un identificador de proveedor de forma determinista."""
    if not isinstance(provider_name, str):
        raise TypeError("provider_name debe ser una cadena.")

    normalized = (
        provider_name
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if not normalized:
        raise ValueError("provider_name no puede estar vacío.")

    return normalized


__all__ = ["normalize_provider_name"]
