"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 019
Archivo  : knowledge_engine.py
Estado   : RELEASE
=========================================================

Carga los Knowledge Modules requeridos por el Runtime.

Compatibilidad:
- PipelineEngine legado mediante execute(Project).
- PipelineRunner mediante execute(RuntimeContext).
- Knowledge Modules v1 en Markdown.
- Knowledge Modules v2 en carpetas estructuradas.
"""

import re

from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import EngineResult, KnowledgeModule, Project
from utils import ROOT, read_yaml


KNOWLEDGE_DIR = ROOT / "09_KNOWLEDGE"


class KnowledgeEngine(RuntimeComponent):
    """
    Carga los Knowledge Modules esenciales de CIPS.

    El componente admite dos formas de ejecución:

    1. execute(Project)
       Mantiene compatibilidad con PipelineEngine.

    2. execute(RuntimeContext)
       Implementa el nuevo contrato del Runtime Framework.
    """

    component_name = "knowledge_engine"

    CORE_MODULE_IDS = [
        "KM-000",
        "KM-001",
        "KM-002",
        "KM-003",
        "KM-004",
        "KM-005",
        "KM-006",
        "KM-007",
        "KM-008",
    ]

    def execute(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> EngineResult:
        """
        Carga el conocimiento disponible y devuelve un EngineResult.

        Cuando recibe RuntimeContext, guarda los módulos en:

            runtime_context.knowledge_modules

        Cuando recibe Project, devuelve directamente la lista de módulos
        para conservar compatibilidad con PipelineEngine.
        """

        try:
            runtime_context = self._get_runtime_context(runtime_input)
            project = self._get_project(runtime_input)

            if not KNOWLEDGE_DIR.exists():
                return EngineResult.fail(
                    message="No existe la carpeta 09_KNOWLEDGE.",
                    errors=[str(KNOWLEDGE_DIR)],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                    },
                )

            modules = self._load_required_core_modules()

            if not modules:
                return EngineResult.fail(
                    message="No se encontraron módulos CORE requeridos.",
                    errors=[
                        "Verifica la carpeta 09_KNOWLEDGE/00_CORE."
                    ],
                    metadata={
                        "component": self.component_name,
                        "project_id": project.project_id,
                    },
                )

            metadata = {
                "component": self.component_name,
                "project_id": project.project_id,
                "modules_count": len(modules),
                "module_ids": [
                    module.module_id for module in modules
                ],
                "source": str(KNOWLEDGE_DIR),
                "v1_modules": sum(
                    1
                    for module in modules
                    if module.metadata.get("format") == "v1"
                ),
                "v2_modules": sum(
                    1
                    for module in modules
                    if module.metadata.get("format") == "v2"
                ),
            }

            if runtime_context is not None:
                runtime_context.knowledge_modules = modules

                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "Knowledge Modules cargados en RuntimeContext."
                    ),
                    metadata=metadata,
                )

            return EngineResult.ok(
                data=modules,
                message=(
                    "Knowledge Modules esenciales cargados correctamente."
                ),
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en KnowledgeEngine.",
                errors=[str(error)],
                metadata={
                    "component": self.component_name,
                },
            )

    def _get_runtime_context(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> RuntimeContext | None:
        """
        Devuelve RuntimeContext cuando se usa el nuevo Framework.
        """

        if isinstance(runtime_input, RuntimeContext):
            return runtime_input

        return None

    def _get_project(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> Project:
        """
        Obtiene el objeto Project desde cualquiera de las interfaces.
        """

        if isinstance(runtime_input, RuntimeContext):
            return runtime_input.project

        if isinstance(runtime_input, Project):
            return runtime_input

        raise TypeError(
            "KnowledgeEngine requiere Project o RuntimeContext."
        )

    def _load_required_core_modules(
        self,
    ) -> list[KnowledgeModule]:
        """
        Carga primero módulos v2 y después módulos v1 sin reemplazo v2.
        """

        core_dir = KNOWLEDGE_DIR / "00_CORE"

        if not core_dir.exists():
            return []

        modules = self._load_v2_modules(core_dir)
        loaded_ids = {
            module.module_id for module in modules
        }

        modules.extend(
            self._load_v1_modules(
                core_dir=core_dir,
                excluded_ids=loaded_ids,
            )
        )

        return sorted(
            modules,
            key=lambda module: module.module_id,
        )

    def _load_v2_modules(
        self,
        core_dir,
    ) -> list[KnowledgeModule]:
        """
        Carga módulos v2 almacenados como carpetas.
        """

        modules: list[KnowledgeModule] = []

        for folder_path in sorted(core_dir.glob("KM-*")):
            if not folder_path.is_dir():
                continue

            module_id = self._extract_module_id(
                folder_path.name
            )

            if module_id not in self.CORE_MODULE_IDS:
                continue

            runtime_path = folder_path / "RUNTIME.yaml"
            metadata_path = folder_path / "METADATA.yaml"

            if not runtime_path.exists():
                continue

            runtime_data = read_yaml(runtime_path)

            if not isinstance(runtime_data, dict):
                continue

            metadata = read_yaml(metadata_path)

            if not isinstance(metadata, dict):
                metadata = {}

            content = self._runtime_yaml_to_text(
                runtime_data
            )

            modules.append(
                KnowledgeModule(
                    module_id=module_id,
                    name=folder_path.name,
                    path=folder_path,
                    category=metadata.get(
                        "category",
                        "CORE",
                    ),
                    content=content,
                    dependencies=self._normalize_dependencies(
                        runtime_data.get("dependencies", [])
                    ),
                    metadata={
                        **metadata,
                        "format": "v2",
                        "runtime_path": str(runtime_path),
                        "size": len(content),
                    },
                )
            )

        return modules

    def _load_v1_modules(
        self,
        core_dir,
        excluded_ids: set[str],
    ) -> list[KnowledgeModule]:
        """
        Carga módulos Markdown v1 que no tengan versión v2.
        """

        modules: list[KnowledgeModule] = []

        for file_path in sorted(core_dir.glob("KM-*.md")):
            module_id = self._extract_module_id(
                file_path.name
            )

            if module_id not in self.CORE_MODULE_IDS:
                continue

            if module_id in excluded_ids:
                continue

            content = file_path.read_text(
                encoding="utf-8"
            )

            modules.append(
                KnowledgeModule(
                    module_id=module_id,
                    name=file_path.stem,
                    path=file_path,
                    category="CORE",
                    content=content,
                    dependencies=self._extract_dependencies(
                        content
                    ),
                    metadata={
                        "filename": file_path.name,
                        "format": "v1",
                        "size": len(content),
                    },
                )
            )

        return modules

    def _extract_module_id(
        self,
        filename: str,
    ) -> str:
        """
        Extrae un identificador como KM-000 del nombre recibido.
        """

        match = re.match(
            r"(KM-\d+)",
            filename,
        )

        if match:
            return match.group(1)

        return "UNKNOWN"

    def _extract_dependencies(
        self,
        content: str,
    ) -> list[str]:
        """
        Extrae dependencias declaradas dentro de módulos v1.
        """

        dependencies: list[str] = []

        for line in content.splitlines():
            stripped_line = line.strip()
            match = re.search(
                r"(KM-\d+(?:_[A-Z0-9_]+)?\.md)",
                stripped_line,
                flags=re.IGNORECASE,
            )

            if match:
                dependency = match.group(1)

                if dependency not in dependencies:
                    dependencies.append(dependency)

        return dependencies

    def _normalize_dependencies(
        self,
        dependencies,
    ) -> list[str]:
        """
        Normaliza dependencias procedentes de RUNTIME.yaml.
        """

        if not isinstance(dependencies, list):
            return []

        normalized: list[str] = []

        for dependency in dependencies:
            value = str(dependency).strip()

            if value and value not in normalized:
                normalized.append(value)

        return normalized

    def _runtime_yaml_to_text(
        self,
        data: dict,
    ) -> str:
        """
        Convierte RUNTIME.yaml en texto operativo para ContextEngine.
        """

        blocks: list[str] = []

        for key, value in data.items():
            title = key.replace(
                "_",
                " ",
            ).upper()

            blocks.append(f"## {title}")

            if isinstance(value, list):
                if not value:
                    blocks.append("- Ninguno.")
                else:
                    for item in value:
                        blocks.append(f"- {item}")

            elif isinstance(value, dict):
                if not value:
                    blocks.append("- Ninguno.")
                else:
                    for item_key, item_value in value.items():
                        readable_key = str(item_key).replace(
                            "_",
                            " ",
                        )
                        blocks.append(
                            f"- {readable_key}: {item_value}"
                        )

            elif value is None or value == "":
                blocks.append("No definido.")

            else:
                blocks.append(str(value).strip())

            blocks.append("")

        return "\n".join(blocks).strip()