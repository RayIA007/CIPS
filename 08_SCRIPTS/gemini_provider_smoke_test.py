"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 037
Archivo  : gemini_provider_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba aislada del proveedor Google Gemini.

Esta prueba:
- no abre proyectos;
- no modifica memoria;
- no genera archivos;
- no avanza Stages;
- realiza una solicitud breve y controlada.
"""

import os
import sys

from gemini_llm_provider import GeminiLLMProvider


TEST_PROMPT = """
Responde únicamente con esta frase exacta:

CIPS GEMINI PROVIDER OK
""".strip()


def mask_key_status() -> str:
    """
    Indica si existe una credencial sin mostrar su contenido.
    """

    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if google_key:
        return "GOOGLE_API_KEY disponible"

    if gemini_key:
        return "GEMINI_API_KEY disponible"

    return "No se encontró ninguna credencial"


def main() -> int:
    """
    Ejecuta una solicitud mínima contra Gemini.
    """

    print("CIPS Gemini Provider Smoke Test")
    print("-" * 50)
    print(f"Credencial: {mask_key_status()}")
    print()

    provider = GeminiLLMProvider(
        model="gemini-3.5-flash",
        temperature=0.0,
        max_output_tokens=512,
        timeout_seconds=60,
    )

    print(f"Proveedor: {provider.provider_name}")
    print(f"Modelo: {provider.model_name}")
    print()

    result = provider.generate(
        prompt=TEST_PROMPT,
        metadata={
            "test": "gemini_provider_smoke_test",
            "purpose": "connection_validation",
        },
    )

    print(f"Éxito: {result.success}")
    print(f"Mensaje: {result.message}")

    if result.warnings:
        print("\nAdvertencias:")
        for warning in result.warnings:
            print(f"- {warning}")

    if result.errors:
        print("\nErrores:")
        for error in result.errors:
            print(f"- {error}")

    if result.response is not None:
        print("\nRespuesta:")
        print(result.response.content)

    print("\nMetadatos seguros:")

    safe_metadata = {
        key: value
        for key, value in result.metadata.items()
        if "key" not in key.lower()
        and "credential" not in key.lower()
    }

    for key, value in safe_metadata.items():
        print(f"- {key}: {value}")

    if not result.success:
        return 1

    normalized_response = (
        result.response.content.strip().upper()
        if result.response
        else ""
    )

    expected = "CIPS GEMINI PROVIDER OK"

    if expected not in normalized_response:
        print(
            "\nLa conexión funcionó, pero la respuesta "
            "no coincidió exactamente con la esperada."
        )
        return 2

    print()
    print("Gemini Provider Smoke Test completado correctamente.")

    return 0


if __name__ == "__main__":
    sys.exit(main())