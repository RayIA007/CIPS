"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 033
Archivo  : knowledge_injector.py
Estado   : RELEASE
=========================================================

Inyector genérico de conocimiento para CIPS.

Responsabilidades:
- descubrir archivos de conocimiento;
- convertirlos en KnowledgeModule;
- seleccionar módulos relevantes;
- resolver dependencias declaradas;
- ordenar por prioridad y relevancia;
- eliminar módulos y bloques duplicados;
- respetar un presupuesto máximo de caracteres;
- construir ContextObject compatible con runtime_models.py.

Este módulo no ejecuta modelos LLM, no realiza búsquedas web y no
modifica los archivos originales de conocimiento.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import json
from pathlib import Path
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from runtime_models import ContextObject, KnowledgeModule, Project


KNOWLEDGE_INJECTOR_VERSION = "1.0.0"
DEFAULT_MAX_CONTEXT_CHARACTERS = 48_000
DEFAULT_EXTENSIONS = (
    ".md",
    ".markdown",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
)
DEFAULT_ENCODING = "utf-8"

_WORD_PATTERN = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)
_FRONT_MATTER_PATTERN = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?",
    re.DOTALL,
)
_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


class KnowledgeInjectionError(ValueError):
    """Error controlado del proceso de inyección."""


@dataclass(frozen=True)
class KnowledgeSelection:
    """Resultado auditable de la selección de módulos."""

    modules: tuple[KnowledgeModule, ...]
    query: str = ""
    requested_ids: tuple[str, ...] = ()
    dependency_ids: tuple[str, ...] = ()
    excluded_ids: tuple[str, ...] = ()
    scores: dict[str, float] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_ids": [
                module.module_id for module in self.modules
            ],
            "query": self.query,
            "requested_ids": list(self.requested_ids),
            "dependency_ids": list(self.dependency_ids),
            "excluded_ids": list(self.excluded_ids),
            "scores": dict(self.scores),
            "warnings": list(self.warnings),
        }


class KnowledgeInjector:
    """
    Descubre, selecciona e inyecta conocimiento local en CIPS.

    Convenciones opcionales de metadatos en front matter:

        ---
        module_id: storytelling
        name: Storytelling
        category: narrativa
        priority: 80
        dependencies: psicologia, copywriting
        tags: historias, retencion, guion
        enabled: true
        ---

    Los archivos sin front matter también son válidos.
    """

    component_name = "knowledge_injector"
    version = KNOWLEDGE_INJECTOR_VERSION

    def __init__(
        self,
        knowledge_root: str | Path = "09_KNOWLEDGE",
        *,
        max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS,
        extensions: Sequence[str] = DEFAULT_EXTENSIONS,
        recursive: bool = True,
        encoding: str = DEFAULT_ENCODING,
    ) -> None:
        self.knowledge_root = Path(knowledge_root)
        self.max_context_characters = self._positive_int(
            max_context_characters,
            "max_context_characters",
        )
        self.extensions = self._normalize_extensions(extensions)
        self.recursive = bool(recursive)
        self.encoding = str(encoding or DEFAULT_ENCODING)

    def discover(self) -> list[Path]:
        """Devuelve los archivos de conocimiento compatibles."""

        if not self.knowledge_root.exists():
            return []

        if not self.knowledge_root.is_dir():
            raise KnowledgeInjectionError(
                f"La ruta de conocimiento no es un directorio: "
                f"{self.knowledge_root}"
            )

        iterator = (
            self.knowledge_root.rglob("*")
            if self.recursive
            else self.knowledge_root.glob("*")
        )

        return sorted(
            (
                path
                for path in iterator
                if path.is_file()
                and path.suffix.lower() in self.extensions
                and not path.name.startswith(".")
            ),
            key=lambda path: path.as_posix().lower(),
        )

    def load_modules(
        self,
        paths: Iterable[str | Path] | None = None,
    ) -> list[KnowledgeModule]:
        """Carga archivos y los convierte en KnowledgeModule."""

        candidates = (
            [Path(path) for path in paths]
            if paths is not None
            else self.discover()
        )

        modules: list[KnowledgeModule] = []
        seen_ids: set[str] = set()

        for path in candidates:
            module = self._load_module(path)

            if module.module_id in seen_ids:
                raise KnowledgeInjectionError(
                    "module_id duplicado: "
                    f"{module.module_id!r}."
                )

            seen_ids.add(module.module_id)
            modules.append(module)

        return modules

    def select(
        self,
        modules: Sequence[KnowledgeModule],
        *,
        query: str = "",
        module_ids: Iterable[str] | None = None,
        categories: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        minimum_score: float = 0.0,
        include_all_when_empty: bool = True,
    ) -> KnowledgeSelection:
        """
        Selecciona módulos por IDs, categorías, etiquetas y relevancia.

        La relevancia es lexical y determinista. La selección semántica
        avanzada corresponde a KnowledgeResolver.
        """

        normalized_ids = {
            self._slug(value)
            for value in (module_ids or [])
            if str(value).strip()
        }
        normalized_categories = {
            self._normalize_term(value)
            for value in (categories or [])
            if str(value).strip()
        }
        normalized_tags = {
            self._normalize_term(value)
            for value in (tags or [])
            if str(value).strip()
        }

        has_filters = bool(
            normalized_ids
            or normalized_categories
            or normalized_tags
            or query.strip()
        )

        selected: list[KnowledgeModule] = []
        excluded: list[str] = []
        scores: dict[str, float] = {}

        for module in modules:
            metadata = dict(module.metadata or {})

            if not self._as_bool(metadata.get("enabled", True)):
                excluded.append(module.module_id)
                continue

            score = self._relevance_score(module, query)
            scores[module.module_id] = score

            id_match = (
                self._slug(module.module_id) in normalized_ids
                if normalized_ids else False
            )
            category_match = (
                self._normalize_term(module.category)
                in normalized_categories
                if normalized_categories else False
            )
            module_tags = {
                self._normalize_term(tag)
                for tag in self._as_list(metadata.get("tags"))
            }
            tag_match = bool(
                normalized_tags.intersection(module_tags)
            )

            query_match = (
                score >= float(minimum_score)
                and score > 0
                if query.strip()
                else False
            )

            if not has_filters and include_all_when_empty:
                selected.append(module)
            elif id_match or category_match or tag_match or query_match:
                selected.append(module)
            else:
                excluded.append(module.module_id)

        requested = tuple(
            module.module_id
            for module in selected
            if self._slug(module.module_id) in normalized_ids
        )

        return KnowledgeSelection(
            modules=tuple(selected),
            query=query.strip(),
            requested_ids=requested,
            excluded_ids=tuple(excluded),
            scores=scores,
        )

    def resolve_dependencies(
        self,
        selection: KnowledgeSelection,
        available_modules: Sequence[KnowledgeModule],
        *,
        strict: bool = True,
    ) -> KnowledgeSelection:
        """Agrega dependencias transitivas sin ciclos ni duplicados."""

        index = {
            self._slug(module.module_id): module
            for module in available_modules
        }
        selected = list(selection.modules)
        selected_ids = {
            self._slug(module.module_id)
            for module in selected
        }
        dependency_ids: list[str] = list(
            selection.dependency_ids
        )
        warnings = list(selection.warnings)
        visiting: set[str] = set()

        def add_dependencies(module: KnowledgeModule) -> None:
            module_key = self._slug(module.module_id)

            if module_key in visiting:
                warning = (
                    "Dependencia circular detectada en "
                    f"{module.module_id!r}."
                )
                if warning not in warnings:
                    warnings.append(warning)
                return

            visiting.add(module_key)

            declared = list(module.dependencies or [])
            declared.extend(
                self._as_list(
                    (module.metadata or {}).get("dependencies")
                )
            )

            for dependency in declared:
                dependency_key = self._slug(dependency)
                if not dependency_key:
                    continue

                dependency_module = index.get(dependency_key)
                if dependency_module is None:
                    message = (
                        f"Dependencia no encontrada: {dependency!r} "
                        f"requerida por {module.module_id!r}."
                    )
                    if strict:
                        raise KnowledgeInjectionError(message)
                    if message not in warnings:
                        warnings.append(message)
                    continue

                add_dependencies(dependency_module)

                if dependency_key not in selected_ids:
                    selected.append(dependency_module)
                    selected_ids.add(dependency_key)
                    dependency_ids.append(
                        dependency_module.module_id
                    )

            visiting.remove(module_key)

        for module in tuple(selected):
            add_dependencies(module)

        return KnowledgeSelection(
            modules=tuple(selected),
            query=selection.query,
            requested_ids=selection.requested_ids,
            dependency_ids=tuple(dependency_ids),
            excluded_ids=selection.excluded_ids,
            scores=dict(selection.scores),
            warnings=tuple(warnings),
        )

    def prioritize(
        self,
        selection: KnowledgeSelection,
    ) -> KnowledgeSelection:
        """Ordena por prioridad, relevancia, categoría e ID."""

        def key(module: KnowledgeModule) -> tuple[Any, ...]:
            metadata = dict(module.metadata or {})
            priority = self._priority_value(
                metadata.get("priority", 0)
            )
            relevance = selection.scores.get(
                module.module_id,
                0.0,
            )
            required = self._as_bool(
                metadata.get("required", False)
            )

            return (
                -int(required),
                -priority,
                -relevance,
                self._normalize_term(module.category),
                module.module_id.lower(),
            )

        return replace(
            selection,
            modules=tuple(sorted(selection.modules, key=key)),
        )

    def deduplicate(
        self,
        selection: KnowledgeSelection,
    ) -> KnowledgeSelection:
        """
        Elimina módulos idénticos y bloques repetidos entre módulos.
        """

        seen_module_hashes: set[str] = set()
        seen_blocks: set[str] = set()
        clean_modules: list[KnowledgeModule] = []
        excluded = list(selection.excluded_ids)
        warnings = list(selection.warnings)

        for module in selection.modules:
            normalized_content = self._normalize_content(
                module.content
            )
            module_hash = self._content_hash(normalized_content)

            if module_hash in seen_module_hashes:
                excluded.append(module.module_id)
                warnings.append(
                    "Módulo duplicado omitido: "
                    f"{module.module_id}."
                )
                continue

            seen_module_hashes.add(module_hash)
            unique_blocks: list[str] = []

            for block in self._split_blocks(normalized_content):
                block_hash = self._content_hash(block)
                if block_hash in seen_blocks:
                    continue
                seen_blocks.add(block_hash)
                unique_blocks.append(block)

            content = "\n\n".join(unique_blocks).strip()
            if not content:
                excluded.append(module.module_id)
                warnings.append(
                    "Módulo vacío tras deduplicación: "
                    f"{module.module_id}."
                )
                continue

            clean_modules.append(
                replace(module, content=content)
            )

        return replace(
            selection,
            modules=tuple(clean_modules),
            excluded_ids=tuple(dict.fromkeys(excluded)),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def compress(
        self,
        selection: KnowledgeSelection,
        *,
        max_characters: int | None = None,
    ) -> KnowledgeSelection:
        """
        Ajusta el contenido al presupuesto sin usar un LLM.

        Conserva módulos completos mientras sea posible. El último
        módulo que cabe parcialmente se trunca en un límite de bloque.
        """

        limit = self._positive_int(
            max_characters or self.max_context_characters,
            "max_characters",
        )
        remaining = limit
        compressed: list[KnowledgeModule] = []
        excluded = list(selection.excluded_ids)
        warnings = list(selection.warnings)

        for module in selection.modules:
            header_cost = len(self._module_header(module)) + 2
            available = remaining - header_cost

            if available <= 0:
                excluded.append(module.module_id)
                continue

            content = module.content.strip()
            if len(content) <= available:
                compressed.append(module)
                remaining -= header_cost + len(content)
                continue

            truncated = self._truncate_content(
                content,
                available,
            )
            if truncated:
                metadata = dict(module.metadata or {})
                metadata.update(
                    {
                        "compressed": True,
                        "original_characters": len(content),
                        "included_characters": len(truncated),
                    }
                )
                compressed.append(
                    replace(
                        module,
                        content=truncated,
                        metadata=metadata,
                    )
                )
                warnings.append(
                    "Módulo recortado por presupuesto: "
                    f"{module.module_id}."
                )
                remaining = 0
            else:
                excluded.append(module.module_id)

        return replace(
            selection,
            modules=tuple(compressed),
            excluded_ids=tuple(dict.fromkeys(excluded)),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def build_context(
        self,
        project: Project,
        selection: KnowledgeSelection,
    ) -> ContextObject:
        """Construye ContextObject listo para PromptRenderer."""

        if not isinstance(project, Project):
            raise TypeError("project debe ser Project.")

        content = self._render_modules(selection.modules)
        metadata = {
            "component": self.component_name,
            "injector_version": self.version,
            "knowledge_root": str(self.knowledge_root),
            "query": selection.query,
            "modules_total": len(selection.modules),
            "module_ids": [
                module.module_id for module in selection.modules
            ],
            "dependency_ids": list(selection.dependency_ids),
            "excluded_ids": list(selection.excluded_ids),
            "scores": dict(selection.scores),
            "warnings": list(selection.warnings),
            "characters": len(content),
            "estimated_tokens": (
                max(1, len(content) // 4) if content else 0
            ),
            "content_hash": self._content_hash(content),
        }

        return ContextObject(
            project=project,
            modules=list(selection.modules),
            content=content,
            metadata=metadata,
        )

    def inject(
        self,
        project: Project,
        *,
        query: str = "",
        module_ids: Iterable[str] | None = None,
        categories: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        minimum_score: float = 0.0,
        paths: Iterable[str | Path] | None = None,
        strict_dependencies: bool = True,
        max_characters: int | None = None,
        include_all_when_empty: bool = True,
    ) -> ContextObject:
        """Ejecuta el flujo completo de inyección."""

        modules = self.load_modules(paths)
        selection = self.select(
            modules,
            query=query,
            module_ids=module_ids,
            categories=categories,
            tags=tags,
            minimum_score=minimum_score,
            include_all_when_empty=include_all_when_empty,
        )
        selection = self.resolve_dependencies(
            selection,
            modules,
            strict=strict_dependencies,
        )
        selection = self.prioritize(selection)
        selection = self.deduplicate(selection)
        selection = self.compress(
            selection,
            max_characters=max_characters,
        )

        return self.build_context(project, selection)

    def _load_module(self, path: Path) -> KnowledgeModule:
        if not path.exists() or not path.is_file():
            raise KnowledgeInjectionError(
                f"Archivo de conocimiento no encontrado: {path}"
            )

        try:
            raw = path.read_text(
                encoding=self.encoding,
                errors="strict",
            )
        except UnicodeDecodeError:
            raw = path.read_text(
                encoding=self.encoding,
                errors="replace",
            )
        except OSError as error:
            raise KnowledgeInjectionError(
                f"No fue posible leer {path}: {error}"
            ) from error

        metadata, content = self._parse_document(path, raw)

        relative = self._relative_path(path)
        module_id = self._slug(
            metadata.get("module_id")
            or metadata.get("id")
            or relative.with_suffix("").as_posix()
        )
        name = str(
            metadata.get("name")
            or metadata.get("title")
            or self._extract_title(content)
            or path.stem.replace("_", " ").replace("-", " ")
        ).strip()
        category = str(
            metadata.get("category")
            or (
                relative.parts[0]
                if len(relative.parts) > 1
                else "general"
            )
        ).strip()
        dependencies = self._as_list(
            metadata.get("dependencies")
        )

        normalized_metadata = dict(metadata)
        normalized_metadata.update(
            {
                "source_path": str(path),
                "relative_path": relative.as_posix(),
                "extension": path.suffix.lower(),
                "characters": len(content),
                "content_hash": self._content_hash(content),
            }
        )

        return KnowledgeModule(
            module_id=module_id,
            name=name,
            path=path,
            category=category,
            content=self._normalize_content(content),
            dependencies=dependencies,
            metadata=normalized_metadata,
        )

    def _parse_document(
        self,
        path: Path,
        raw: str,
    ) -> tuple[dict[str, Any], str]:
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return {}, raw

            if isinstance(payload, Mapping):
                metadata = dict(
                    payload.get("metadata")
                    if isinstance(payload.get("metadata"), Mapping)
                    else {}
                )
                for key in (
                    "module_id",
                    "id",
                    "name",
                    "title",
                    "category",
                    "priority",
                    "dependencies",
                    "tags",
                    "enabled",
                    "required",
                ):
                    if key in payload and key not in metadata:
                        metadata[key] = payload[key]

                content = payload.get("content")
                if isinstance(content, str):
                    return metadata, content

            return {}, json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

        match = _FRONT_MATTER_PATTERN.match(raw)
        if not match:
            return {}, raw

        metadata = self._parse_front_matter(
            match.group(1)
        )
        content = raw[match.end():]
        return metadata, content

    def _parse_front_matter(
        self,
        source: str,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {}

        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                continue

            if value.startswith("[") and value.endswith("]"):
                try:
                    metadata[key] = json.loads(value)
                    continue
                except json.JSONDecodeError:
                    pass

            if "," in value and key in {
                "dependencies",
                "tags",
                "keywords",
            }:
                metadata[key] = [
                    item.strip()
                    for item in value.split(",")
                    if item.strip()
                ]
            elif value.lower() in {"true", "false"}:
                metadata[key] = value.lower() == "true"
            elif re.fullmatch(r"-?\d+", value):
                metadata[key] = int(value)
            elif re.fullmatch(r"-?\d+\.\d+", value):
                metadata[key] = float(value)
            else:
                metadata[key] = value.strip("'\"")

        return metadata

    def _relevance_score(
        self,
        module: KnowledgeModule,
        query: str,
    ) -> float:
        query_terms = self._tokenize(query)
        if not query_terms:
            return 0.0

        metadata = dict(module.metadata or {})
        title_terms = self._tokenize(
            " ".join(
                [
                    module.name,
                    module.module_id,
                    module.category,
                    " ".join(self._as_list(metadata.get("tags"))),
                    " ".join(self._as_list(metadata.get("keywords"))),
                ]
            )
        )
        content_terms = self._tokenize(module.content)

        title_overlap = len(query_terms.intersection(title_terms))
        content_overlap = len(query_terms.intersection(content_terms))

        phrase_bonus = 0.0
        normalized_query = self._normalize_term(query)
        searchable = self._normalize_term(
            f"{module.name} {module.category} {module.content}"
        )
        if normalized_query and normalized_query in searchable:
            phrase_bonus = 5.0

        return round(
            title_overlap * 3.0
            + content_overlap * 1.0
            + phrase_bonus,
            4,
        )

    def _render_modules(
        self,
        modules: Sequence[KnowledgeModule],
    ) -> str:
        blocks: list[str] = []

        for module in modules:
            blocks.append(
                f"{self._module_header(module)}\n\n"
                f"{module.content.strip()}"
            )

        return "\n\n---\n\n".join(blocks).strip()

    @staticmethod
    def _module_header(module: KnowledgeModule) -> str:
        return (
            f"## {module.name}\n"
            f"- **Módulo:** `{module.module_id}`\n"
            f"- **Categoría:** {module.category}"
        )

    @staticmethod
    def _split_blocks(content: str) -> list[str]:
        return [
            block.strip()
            for block in re.split(r"\n\s*\n", content)
            if block.strip()
        ]

    def _truncate_content(
        self,
        content: str,
        limit: int,
    ) -> str:
        if limit <= 0:
            return ""

        if len(content) <= limit:
            return content

        blocks = self._split_blocks(content)
        selected: list[str] = []
        used = 0

        for block in blocks:
            cost = len(block) + (2 if selected else 0)
            if used + cost > limit:
                break
            selected.append(block)
            used += cost

        if selected:
            return "\n\n".join(selected)

        if limit < 32:
            return ""

        clipped = content[: max(0, limit - 16)].rstrip()
        return clipped + "\n\n[CONTEXTO RECORTADO]"

    @staticmethod
    def _extract_title(content: str) -> str:
        match = _HEADING_PATTERN.search(content)
        return match.group(1).strip() if match else ""

    def _relative_path(self, path: Path) -> Path:
        try:
            return path.resolve().relative_to(
                self.knowledge_root.resolve()
            )
        except ValueError:
            return Path(path.name)

    @staticmethod
    def _normalize_content(content: str) -> str:
        normalized = str(content or "").replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )
        normalized = re.sub(
            r"[ \t]+\n",
            "\n",
            normalized,
        )
        normalized = re.sub(
            r"\n{3,}",
            "\n\n",
            normalized,
        )
        return normalized.strip()

    @staticmethod
    def _content_hash(content: str) -> str:
        normalized = re.sub(
            r"\s+",
            " ",
            str(content or "").strip().lower(),
        )
        return sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _tokenize(value: Any) -> set[str]:
        return {
            match.group(0).lower()
            for match in _WORD_PATTERN.finditer(
                str(value or "")
            )
            if len(match.group(0)) > 1
        }

    @staticmethod
    def _normalize_term(value: Any) -> str:
        return " ".join(
            str(value or "").strip().lower().split()
        )

    @classmethod
    def _slug(cls, value: Any) -> str:
        text = cls._normalize_term(value)
        text = (
            text.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ü", "u")
            .replace("ñ", "n")
        )
        text = re.sub(r"[^a-z0-9]+", "-", text)
        return text.strip("-")

    @staticmethod
    def _as_list(value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return [
                item.strip()
                for item in value.split(",")
                if item.strip()
            ]

        if isinstance(value, Iterable) and not isinstance(
            value,
            (bytes, bytearray, Mapping),
        ):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() not in {
                "false",
                "0",
                "no",
                "off",
                "disabled",
            }

        return bool(value)

    @staticmethod
    def _priority_value(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)

        labels = {
            "critical": 100.0,
            "critica": 100.0,
            "crítica": 100.0,
            "high": 75.0,
            "alta": 75.0,
            "medium": 50.0,
            "media": 50.0,
            "low": 25.0,
            "baja": 25.0,
        }

        normalized = str(value or "").strip().lower()
        if normalized in labels:
            return labels[normalized]

        try:
            return float(normalized)
        except ValueError:
            return 0.0

    @staticmethod
    def _positive_int(
        value: Any,
        field_name: str,
    ) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError) as error:
            raise TypeError(
                f"{field_name} debe ser un entero."
            ) from error

        if result <= 0:
            raise ValueError(
                f"{field_name} debe ser mayor que cero."
            )

        return result

    @staticmethod
    def _normalize_extensions(
        extensions: Sequence[str],
    ) -> tuple[str, ...]:
        normalized: list[str] = []

        for extension in extensions:
            value = str(extension or "").strip().lower()
            if not value:
                continue
            if not value.startswith("."):
                value = "." + value
            if value not in normalized:
                normalized.append(value)

        if not normalized:
            raise ValueError(
                "Debe configurarse al menos una extensión."
            )

        return tuple(normalized)


def inject_knowledge(
    project: Project,
    *,
    knowledge_root: str | Path = "09_KNOWLEDGE",
    query: str = "",
    module_ids: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    tags: Iterable[str] | None = None,
    max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS,
) -> ContextObject:
    """Función de conveniencia para el flujo completo."""

    injector = KnowledgeInjector(
        knowledge_root=knowledge_root,
        max_context_characters=max_context_characters,
    )

    return injector.inject(
        project,
        query=query,
        module_ids=module_ids,
        categories=categories,
        tags=tags,
    )