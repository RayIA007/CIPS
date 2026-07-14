"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 026
Archivo  : runtime_framework_smoke_test.py
Estado   : RELEASE
=========================================================

Prueba de extremo a extremo del Runtime Framework usando:

- RuntimeContext
- PipelineRunner
- RuntimeComponent
- Engines migrados

La prueba utiliza una respuesta LLM simulada porque todavía
no existe un LLMAdapter conectado a un proveedor externo.
"""

from project_manager import ProjectManager
from runtime_context import RuntimeContext
from runtime_models import LLMResponse
from pipeline_runner import PipelineRunner

from knowledge_engine import KnowledgeEngine
from knowledge_resolver import KnowledgeResolver
from context_compressor import ContextCompressor
from context_engine import ContextEngine
from prompt_engine import PromptEngine
from validator_engine import ValidatorEngine
from memory_engine import MemoryEngine


def print_result(
    label: str,
    success: bool,
    message: str,
) -> None:
    """
    Imprime el resultado de una etapa de forma uniforme.
    """

    status = "OK" if success else "ERROR"
    print(f"{label}: {status}")
    print(f"  {message}")


def build_pre_llm_runner() -> PipelineRunner:
    """
    Construye el pipeline previo a la respuesta del modelo.
    """

    return PipelineRunner(
        components=[
            KnowledgeEngine(),
            KnowledgeResolver(),
            ContextCompressor(),
            ContextEngine(),
            PromptEngine(),
        ]
    )


def build_post_llm_runner() -> PipelineRunner:
    """
    Construye el pipeline posterior a la respuesta del modelo.
    """

    return PipelineRunner(
        components=[
            ValidatorEngine(),
            MemoryEngine(),
        ]
    )


def build_fake_response(
    runtime_context: RuntimeContext,
) -> LLMResponse:
    """
    Genera una respuesta simulada suficientemente completa
    para validar el flujo del Framework.
    """

    project = runtime_context.project

    content = f"""# Resultado simulado

## Proyecto

ID: {project.project_id}

Tema: {project.tema}

Stage: {project.stage_actual}

## Resultado

Esta es una respuesta simulada creada para verificar que el
Runtime Framework de CIPS puede ejecutar correctamente el flujo
completo desde la carga de conocimiento hasta la validación y
actualización de memoria.

El contenido es deliberadamente mayor a cien caracteres para
superar la validación mínima del ValidatorEngine.

## Conclusión

El pipeline basado en RuntimeContext y PipelineRunner funciona
de extremo a extremo sin depender de la coordinación manual del
PipelineEngine clásico.
"""

    return LLMResponse(
        content=content,
        model="framework_smoke_test",
        metadata={
            "source": "simulated",
            "project_id": project.project_id,
            "stage": project.stage_actual,
        },
    )


def main() -> None:
    """
    Ejecuta la prueba completa del Runtime Framework.
    """

    print("CIPS Runtime Framework Smoke Test")
    print("-" * 50)

    project_manager = ProjectManager()
    project = project_manager.load_project()

    runtime_context = RuntimeContext(
        project=project
    )

    print(f"Proyecto: {project.project_id}")
    print(f"Tema: {project.tema}")
    print(f"Stage: {project.stage_actual}")
    print()

    pre_llm_runner = build_pre_llm_runner()

    pre_result = pre_llm_runner.execute(
        runtime_context
    )

    print_result(
        label="Pre-LLM Pipeline",
        success=pre_result.success,
        message=pre_result.message,
    )

    if not pre_result.success:
        print()
        print("Errores:")
        for error in pre_result.errors:
            print(f"- {error}")
        return

    print(
        "Componentes ejecutados: "
        f"{pre_result.metadata.get('executed_components', [])}"
    )
    print(
        "Knowledge Modules cargados: "
        f"{len(runtime_context.knowledge_modules)}"
    )
    print(
        "Knowledge Modules resueltos: "
        f"{len(runtime_context.resolved_modules)}"
    )
    print(
        "Knowledge Modules comprimidos: "
        f"{len(runtime_context.compressed_modules)}"
    )
    print(
        "ContextObject disponible: "
        f"{runtime_context.context_object is not None}"
    )
    print(
        "PromptObject disponible: "
        f"{runtime_context.prompt_object is not None}"
    )
    print(
        "Prompt guardado en: "
        f"{runtime_context.prompt_path}"
    )
    print()

    runtime_context.llm_response = build_fake_response(
        runtime_context
    )

    post_llm_runner = build_post_llm_runner()

    post_result = post_llm_runner.execute(
        runtime_context
    )

    print_result(
        label="Post-LLM Pipeline",
        success=post_result.success,
        message=post_result.message,
    )

    if not post_result.success:
        print()
        print("Errores:")
        for error in post_result.errors:
            print(f"- {error}")
        return

    print(
        "Componentes ejecutados: "
        f"{post_result.metadata.get('executed_components', [])}"
    )
    print(
        "LLMResponse disponible: "
        f"{runtime_context.llm_response is not None}"
    )
    print(
        "ValidationResult disponible: "
        f"{runtime_context.validation_result is not None}"
    )
    print(
        "Respuesta aprobada: "
        f"{runtime_context.validation_result.approved}"
    )
    print(
        "Memoria actualizada: "
        f"{bool(runtime_context.memory_data)}"
    )
    print(
        "Último Stage validado: "
        f"{runtime_context.memory_data.get('ultimo_stage_validado')}"
    )
    print(
        "Siguiente Stage: "
        f"{runtime_context.memory_data.get('siguiente_stage')}"
    )
    print()

    print("Component Results")
    print("-" * 50)

    for component_name, result in (
        runtime_context.component_results.items()
    ):
        print(
            f"{component_name}: "
            f"{'OK' if result.success else 'ERROR'}"
        )

    print()
    print(
        "Runtime Framework Smoke Test "
        "completado correctamente."
    )


if __name__ == "__main__":
    main()