"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 009A
Archivo  : runtime_smoke_test.py
Estado   : RELEASE
=========================================================
"""

from pathlib import Path

from runtime_models import Project, LLMResponse
from knowledge_engine import KnowledgeEngine
from context_engine import ContextEngine
from prompt_engine import PromptEngine
from validator_engine import ValidatorEngine
from memory_engine import MemoryEngine
from utils import ROOT, read_yaml


def get_latest_project() -> Path:
    projects_dir = ROOT / "04_PROYECTOS"

    projects = sorted(
        [
            item for item in projects_dir.iterdir()
            if item.is_dir() and item.name.startswith("PROYECTO_")
        ]
    )

    if not projects:
        raise FileNotFoundError("No existe ningún proyecto creado.")

    return projects[-1]


def load_project(project_path: Path) -> Project:
    data = read_yaml(project_path / "proyecto.yaml")

    return Project(
        project_id=data.get("id", project_path.name),
        path=project_path,
        tema=data.get("tema", ""),
        estado=data.get("estado", "READY"),
        stage_actual=data.get("estado", "investigacion"),
        ultimo_stage_validado=data.get("ultimo_stage_validado", ""),
        config={},
        memory=read_yaml(project_path / "memoria.yaml"),
        metadata=data,
    )


def main():
    print("CIPS Runtime Smoke Test")
    print("-" * 40)

    project_path = get_latest_project()
    project = load_project(project_path)

    print(f"Proyecto: {project.project_id}")
    print(f"Tema: {project.tema}")
    print(f"Stage: {project.stage_actual}")
    print()

    knowledge_result = KnowledgeEngine().execute(project)

    if not knowledge_result.success:
        print("ERROR KnowledgeEngine")
        print(knowledge_result.errors)
        return

    print("KnowledgeEngine OK")

    context_result = ContextEngine().execute(
        project,
        knowledge_result.data,
    )

    if not context_result.success:
        print("ERROR ContextEngine")
        print(context_result.errors)
        return

    print("ContextEngine OK")

    prompt_result = PromptEngine().execute(
        project,
        context_result.data,
    )

    if not prompt_result.success:
        print("ERROR PromptEngine")
        print(prompt_result.errors)
        return

    print("PromptEngine OK")
    print(f"Prompt generado: {prompt_result.data['prompt_path']}")

    fake_response = LLMResponse(
        content="# Prueba de validación\n\nEsta es una respuesta simulada suficientemente larga para validar que el ValidatorEngine funciona correctamente dentro del Runtime de CIPS.",
        model="manual_test",
    )

    validation_result = ValidatorEngine().execute(
        project,
        fake_response,
    )

    if not validation_result.success:
        print("ERROR ValidatorEngine")
        print(validation_result.errors)
        return

    print("ValidatorEngine OK")

    memory_result = MemoryEngine().execute(
        project,
        validation_result.data,
    )

    if not memory_result.success:
        print("ERROR MemoryEngine")
        print(memory_result.errors)
        return

    print("MemoryEngine OK")
    print()
    print("Runtime Smoke Test completado correctamente.")


if __name__ == "__main__":
    main()