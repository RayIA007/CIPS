"""
=========================================================
Proyecto : CIPS
Release  : 0.4
Build    : 014
Archivo  : knowledge_module_builder.py
Estado   : RELEASE
=========================================================

Crea Knowledge Modules v2 automáticamente.
"""

from pathlib import Path

from utils import ROOT, ensure_directory, write_text, write_yaml, current_datetime


KNOWLEDGE_DIR = ROOT / "09_KNOWLEDGE"


class KnowledgeModuleBuilder:
    """
    Genera la estructura oficial de un Knowledge Module v2.
    """

    def create_module(
        self,
        module_id: str,
        name: str,
        category: str = "CORE",
        author: str = "Raymundo Montiel",
        confidence: str = "HIGH",
        priority: str = "MEDIUM",
        tags: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> dict:

        module_id = module_id.strip().upper()
        folder_name = f"{module_id}_{self._normalize_name(name)}"

        category_dir = KNOWLEDGE_DIR / f"00_{category.upper()}"
        module_dir = category_dir / folder_name

        if module_dir.exists():
            raise FileExistsError(f"El módulo ya existe: {module_dir}")

        ensure_directory(module_dir)

        tags = tags or []
        keywords = keywords or []

        self._write_metadata(
            module_dir=module_dir,
            module_id=module_id,
            name=name,
            category=category,
            author=author,
            confidence=confidence,
            priority=priority,
            tags=tags,
            keywords=keywords,
        )

        self._write_human(module_dir, module_id, name)
        self._write_runtime(module_dir)
        self._write_changelog(module_dir)

        return {
            "module_id": module_id,
            "name": name,
            "path": str(module_dir),
        }

    def _write_metadata(
        self,
        module_dir: Path,
        module_id: str,
        name: str,
        category: str,
        author: str,
        confidence: str,
        priority: str,
        tags: list[str],
        keywords: list[str],
    ) -> None:

        data = {
            "module_id": module_id,
            "name": name,
            "category": category.upper(),
            "version": "2.0",
            "status": "Draft",
            "author": author,
            "created_at": current_datetime(),
            "updated_at": current_datetime(),
            "confidence": confidence.upper(),
            "priority": priority.upper(),
            "tags": tags,
            "keywords": keywords,
        }

        write_yaml(module_dir / "METADATA.yaml", data)

    def _write_human(
        self,
        module_dir: Path,
        module_id: str,
        name: str,
    ) -> None:

        content = f"""# {module_id} — {name}

## PROPÓSITO

Describe el propósito humano del módulo.

## CONTEXTO

Describe el contexto necesario.

## FUNDAMENTOS

Explica los conceptos principales.

## EJEMPLOS

Incluye ejemplos prácticos.

## BUENAS PRÁCTICAS

- Agregar buenas prácticas.

## ERRORES COMUNES

- Agregar errores comunes.

## REFERENCIAS

- Agregar referencias.
"""

        write_text(module_dir / "HUMAN.md", content)

    def _write_runtime(self, module_dir: Path) -> None:
        data = {
            "objective": "Definir el objetivo operativo del módulo.",
            "inputs": [],
            "outputs": [],
            "rules": [],
            "checklist": [],
            "dependencies": [],
            "restrictions": [],
            "runtime_notes": "Pendiente de completar.",
        }

        write_yaml(module_dir / "RUNTIME.yaml", data)

    def _write_changelog(self, module_dir: Path) -> None:
        content = """# CHANGELOG

## v2.0

Creación inicial en formato Knowledge Module v2.
"""

        write_text(module_dir / "CHANGELOG.md", content)

    def _normalize_name(self, name: str) -> str:
        clean = name.strip().replace(" ", "_")
        clean = "".join(
            char for char in clean
            if char.isalnum() or char == "_"
        )
        return clean.upper()