"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 038
Archivo  : llm_adapter_gemini_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba integral aislada de:

RuntimeContext
    ↓
LLMAdapter
    ↓
LLMConfigManager
    ↓
LLMProviderFactory
    ↓
GeminiLLMProvider
    ↓
LLMResponse

Esta prueba no:
- genera archivos;
- modifica memoria;
- actualiza proyecto.yaml;
- avanza Stages;
- ejecuta PipelineEngine.
"""

import sys

from llm_adapter import LLMAdapter
from project_manager import ProjectManager
from runtime_context import RuntimeContext


TEST_PROMPT = """
Responde únicamente con esta frase exacta:

CIPS LLM ADAPTER GEMINI OK
""".strip()

EXPECTED_RESPONSE = "CIPS LLM ADAPTER GEMINI OK"


def print_section(title: str) -> None:
    """
    Imprime un separador visual.
    """

    print()
    print(title)
    print("-" * 50)


def build_runtime_context() -> RuntimeContext:
    """
    Construye un RuntimeContext aislado usando el proyecto
    activo solamente como identidad de ejecución.

    No modifica ningún archivo del proyecto.
    """

    project = ProjectManager().load_project()

    runtime_context = RuntimeContext(
        project=project
    )

    runtime_context.prompt_markdown = TEST_PROMPT

    runtime_context.metadata[
        "test_execution"
    ] = {
        "name": "llm_adapter_gemini_smoke_test",
        "isolated": True,
        "allow_project_writes": False,
    }

    return runtime_context


def validate_response(
    runtime_context: RuntimeContext,
) -> tuple[bool, str]:
    """
    Comprueba que LLMAdapter haya guardado una respuesta
    utilizable dentro de RuntimeContext.
    """

    response = runtime_context.llm_response

    if response is None:
        return (
            False,
            "RuntimeContext.llm_response no fue creado.",
        )

    content = (
        response.content
        or ""
    ).strip()

    if not content:
        return (
            False,
            "LLMResponse.content está vacío.",
        )

    normalized_content = content.upper()

    if EXPECTED_RESPONSE not in normalized_content:
        return (
            False,
            (
                "La conexión funcionó, pero la respuesta no "
                "contiene la frase esperada."
            ),
        )

    return (
        True,
        "La respuesta coincide con el resultado esperado.",
    )


def safe_metadata(
    metadata: dict,
) -> dict:
    """
    Elimina cualquier campo potencialmente sensible antes
    de mostrar metadatos en pantalla.
    """

    blocked_terms = (
        "api_key",
        "credential",
        "secret",
        "token_value",
        "authorization",
    )

    return {
        key: value
        for key, value in metadata.items()
        if not any(
            term in key.lower()
            for term in blocked_terms
        )
    }


def main() -> int:
    """
    Ejecuta la prueba integral aislada del LLMAdapter.
    """

    print("CIPS LLMAdapter + Gemini Smoke Test")
    print("=" * 50)

    runtime_context = build_runtime_context()
    adapter = LLMAdapter()

    project = runtime_context.project

    print(f"Proyecto de referencia: {project.project_id}")
    print(f"Stage de referencia: {project.stage_actual}")
    print(
        "Archivos del proyecto modificados por esta prueba: No"
    )

    print_section("Configuración resuelta")

    configuration = (
        adapter.get_configuration_summary()
    )

    for key, value in safe_metadata(
        configuration
    ).items():
        print(f"- {key}: {value}")

    provider = adapter.get_provider()

    print()
    print(
        f"Clase del proveedor: "
        f"{provider.__class__.__name__}"
    )
    print(
        f"Proveedor: {provider.provider_name}"
    )
    print(
        f"Modelo: {provider.model_name}"
    )

    print_section("Ejecución")

    result = adapter.execute(
        runtime_context
    )

    print(f"Éxito del Adapter: {result.success}")
    print(f"Mensaje: {result.message}")

    if result.warnings:
        print()
        print("Advertencias:")

        for warning in result.warnings:
            print(f"- {warning}")

    if result.errors:
        print()
        print("Errores:")

        for error in result.errors:
            print(f"- {error}")

    if not result.success:
        print_section("Metadatos seguros")

        for key, value in safe_metadata(
            result.metadata
        ).items():
            print(f"- {key}: {value}")

        return 1

    response = runtime_context.llm_response

    print_section("Respuesta")

    if response is not None:
        print(response.content)
        print()
        print(f"Modelo registrado: {response.model}")
        print(
            "Caracteres recibidos: "
            f"{len(response.content)}"
        )
    else:
        print("No existe una LLMResponse.")

    response_valid, validation_message = (
        validate_response(
            runtime_context
        )
    )

    print_section("Validación")

    print(
        f"Respuesta válida: {response_valid}"
    )
    print(validation_message)

    print_section("Metadatos seguros")

    for key, value in safe_metadata(
        result.metadata
    ).items():
        print(f"- {key}: {value}")

    provider_state = (
        runtime_context.metadata.get(
            "llm_provider",
            {},
        )
    )

    print_section("Estado registrado en RuntimeContext")

    for key, value in safe_metadata(
        provider_state
    ).items():
        print(f"- {key}: {value}")

    if not response_valid:
        return 2

    print()
    print(
        "LLMAdapter + Gemini Smoke Test "
        "completado correctamente."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())