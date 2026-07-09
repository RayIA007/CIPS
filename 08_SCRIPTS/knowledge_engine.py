"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 005A
Archivo  : knowledge_engine.py
Estado   : RELEASE
=========================================================
"""

from pathlib import Path
import re

from runtime_models import EngineResult, KnowledgeModule
from utils import ROOT, read_yaml 


KNOWLEDGE_DIR = ROOT / "09_KNOWLEDGE"


class KnowledgeEngine:
    """
    Carga únicamente los Knowledge Modules necesarios para operar el Runtime.
    """

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

    def execute(self, project) -> EngineResult:
        try:
            if not KNOWLEDGE_DIR.exists():
                return EngineResult.fail(
                    message="No existe la carpeta 09_KNOWLEDGE.",
                    errors=[str(KNOWLEDGE_DIR)],
                )

            modules = self._load_required_core_modules()

            if not modules:
                return EngineResult.fail(
                    message="No se encontraron módulos CORE requeridos.",
                    errors=["Verifica 09_KNOWLEDGE/00_CORE."],
                )

            return EngineResult.ok(
                data=modules,
                message="Knowledge Modules esenciales cargados correctamente.",
                metadata={
                    "modules_count": len(modules),
                    "source": str(KNOWLEDGE_DIR),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en KnowledgeEngine.",
                errors=[str(error)],
            )

    def _load_required_core_modules(self) -> list[KnowledgeModule]:
            core_dir = KNOWLEDGE_DIR / "00_CORE"

            if not core_dir.exists():
                return []

            modules = []

            for folder_path in sorted(core_dir.glob("KM-*")):
                if not folder_path.is_dir():
                    continue

                module_id = self._extract_module_id(folder_path.name)

                if module_id not in self.CORE_MODULE_IDS:
                    continue

                runtime_path = folder_path / "RUNTIME.yaml"
                metadata_path = folder_path / "METADATA.yaml"

                if not runtime_path.exists():
                    continue

                runtime_data = read_yaml(runtime_path)
                metadata = read_yaml(metadata_path)

                content = self._runtime_yaml_to_text(runtime_data)

                modules.append(
                    KnowledgeModule(
                        module_id=module_id,
                        name=folder_path.name,
                        path=folder_path,
                        category=metadata.get("category", "CORE"),
                        content=content,
                        dependencies=runtime_data.get("dependencies", []),
                        metadata={
                            **metadata,
                            "format": "v2",
                            "runtime_path": str(runtime_path),
                            "size": len(content),
                    },
                )
            )

            loaded_ids = {module.module_id for module in modules}

            for file_path in sorted(core_dir.glob("KM-*.md")):
                module_id = self._extract_module_id(file_path.name)

                if module_id not in self.CORE_MODULE_IDS:
                    continue

                if module_id in loaded_ids:
                    continue

                content = file_path.read_text(encoding="utf-8")

                modules.append(
                    KnowledgeModule(
                        module_id=module_id,
                        name=file_path.stem,
                        path=file_path,
                        category="CORE",
                        content=content,
                        dependencies=self._extract_dependencies(content),
                        metadata={
                            "filename": file_path.name,
                            "format": "v1",
                            "size": len(content),
                    },
                )
            )

                return modules

    def _extract_module_id(self, filename: str) -> str:
        match = re.match(r"(KM-\d+)", filename)

        if match:
            return match.group(1)

        return "UNKNOWN"

    def _extract_dependencies(self, content: str) -> list[str]:
        dependencies = []

        for line in content.splitlines():
            line = line.strip()

            if line.startswith("KM-") and line.endswith(".md"):
                dependencies.append(line)

        return dependencies
    def _runtime_yaml_to_text(self, data: dict) -> str:
            blocks = []

            for key, value in data.items():
                title = key.replace("_", " ").upper()
                blocks.append(f"## {title}")

                if isinstance(value, list):
                    for item in value:
                        blocks.append(f"- {item}")
                else:
                    blocks.append(str(value))

                blocks.append("")

            return "\n".join(blocks).strip()