"""
=========================================================
Proyecto : CIPS
Release  : 0.5
Build    : 032
Archivo  : prompt_renderer.py
Estado   : RELEASE
=========================================================

Renderizador genérico de prompts para CIPS.

Responsabilidades:
- convertir PromptObject en un prompt Markdown determinista;
- renderizar plantillas con variables {{ variable }};
- resolver rutas anidadas como {{ project.project_id }};
- detectar variables faltantes;
- normalizar secciones, listas y metadatos;
- mantener la construcción del prompt desacoplada del proveedor LLM.

Este módulo NO:
- ejecuta modelos de Inteligencia Artificial;
- carga archivos de conocimiento;
- modifica RuntimeContext;
- persiste prompts;
- selecciona proveedores.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import json
import re
from collections.abc import Mapping
from typing import Any

from runtime_models import PromptObject


PROMPT_RENDERER_VERSION = "1.0.0"

_VARIABLE_PATTERN = re.compile(
    r"{{\s*([a-zA-Z_][a-zA-Z0-9_.-]*)\s*}}"
)


class PromptRenderError(ValueError):
    """
    Error controlado durante la validación o renderización.
    """


@dataclass(frozen=True)
class RenderedPrompt:
    """
    Resultado inmutable producido por PromptRenderer.
    """

    content: str
    variables_used: tuple[str, ...] = ()
    missing_variables: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """
        Indica si el prompt fue renderizado sin variables faltantes.
        """

        return bool(self.content.strip()) and not self.missing_variables

    @property
    def character_count(self) -> int:
        """
        Devuelve la cantidad de caracteres del prompt final.
        """

        return len(self.content)

    @property
    def estimated_tokens(self) -> int:
        """
        Estimación conservadora de tokens basada en caracteres.
        """

        return max(1, self.character_count // 4) if self.content else 0

    def to_dict(self) -> dict[str, Any]:
        """
        Devuelve una representación serializable.
        """

        return {
            "success": self.success,
            "content": self.content,
            "variables_used": list(self.variables_used),
            "missing_variables": list(self.missing_variables),
            "warnings": list(self.warnings),
            "character_count": self.character_count,
            "estimated_tokens": self.estimated_tokens,
            "metadata": dict(self.metadata),
        }


class PromptRenderer:
    """
    Renderizador oficial de prompts estructurados de CIPS.

    El método principal ``render`` acepta un PromptObject y genera
    Markdown listo para enviarse a cualquier proveedor LLM.

    ``render_template`` permite reutilizar el mismo motor para
    plantillas independientes del Runtime.
    """

    component_name = "prompt_renderer"
    version = PROMPT_RENDERER_VERSION

    def __init__(
        self,
        *,
        strict: bool = True,
        include_metadata: bool = False,
        heading_level: int = 2,
    ) -> None:
        self.strict = bool(strict)
        self.include_metadata = bool(include_metadata)
        self.heading_level = self._normalize_heading_level(
            heading_level
        )

    def render(
        self,
        prompt_object: PromptObject,
        variables: Mapping[str, Any] | None = None,
    ) -> RenderedPrompt:
        """
        Convierte PromptObject en un prompt Markdown.

        Args:
            prompt_object:
                Estructura oficial definida en runtime_models.py.

            variables:
                Variables adicionales disponibles para sustituir
                marcadores ``{{ variable }}``.

        Returns:
            RenderedPrompt:
                Prompt final y datos de trazabilidad.

        Raises:
            TypeError:
                Si prompt_object no es PromptObject.

            PromptRenderError:
                Si faltan datos obligatorios o variables en modo estricto.
        """

        self._validate_prompt_object(prompt_object)

        render_context = self._build_render_context(
            prompt_object=prompt_object,
            variables=variables,
        )

        sections = self._build_sections(prompt_object)
        template = self._join_sections(sections)

        rendered = self.render_template(
            template=template,
            variables=render_context,
            strict=self.strict,
        )

        metadata = {
            **rendered.metadata,
            "component": self.component_name,
            "renderer_version": self.version,
            "project_id": prompt_object.project.project_id,
            "stage": prompt_object.project.stage_actual,
            "output_format": prompt_object.output_format,
            "knowledge_modules": len(
                prompt_object.context.modules
            ),
            "restrictions": len(
                prompt_object.restrictions
            ),
        }

        return RenderedPrompt(
            content=rendered.content,
            variables_used=rendered.variables_used,
            missing_variables=rendered.missing_variables,
            warnings=rendered.warnings,
            metadata=metadata,
        )

    def render_text(
        self,
        prompt_object: PromptObject,
        variables: Mapping[str, Any] | None = None,
    ) -> str:
        """
        Atajo que devuelve únicamente el texto final.
        """

        return self.render(
            prompt_object=prompt_object,
            variables=variables,
        ).content

    def render_template(
        self,
        template: str,
        variables: Mapping[str, Any] | None = None,
        *,
        strict: bool | None = None,
    ) -> RenderedPrompt:
        """
        Sustituye marcadores ``{{ variable }}`` en una plantilla.

        Se admiten rutas anidadas:

            {{ project.project_id }}
            {{ metadata.language }}

        Los valores complejos se convierten de forma determinista:
        - listas: viñetas Markdown;
        - diccionarios: JSON legible;
        - dataclasses: diccionario serializable.
        """

        if not isinstance(template, str):
            raise TypeError(
                "template debe ser una cadena de texto."
            )

        if not template.strip():
            raise PromptRenderError(
                "La plantilla del prompt está vacía."
            )

        source = dict(variables or {})
        effective_strict = (
            self.strict if strict is None else bool(strict)
        )

        used: list[str] = []
        missing: list[str] = []

        def replace(match: re.Match[str]) -> str:
            path = match.group(1)
            found, value = self._resolve_path(
                source,
                path,
            )

            if not found:
                if path not in missing:
                    missing.append(path)
                return match.group(0)

            if path not in used:
                used.append(path)

            return self._format_value(value)

        content = _VARIABLE_PATTERN.sub(
            replace,
            template,
        )
        content = self._normalize_output(content)

        if missing and effective_strict:
            joined = ", ".join(missing)
            raise PromptRenderError(
                "Variables requeridas no encontradas: "
                f"{joined}."
            )

        warnings: list[str] = []
        if missing:
            warnings.append(
                "El prompt conserva variables sin resolver: "
                + ", ".join(missing)
            )

        return RenderedPrompt(
            content=content,
            variables_used=tuple(used),
            missing_variables=tuple(missing),
            warnings=tuple(warnings),
            metadata={
                "component": self.component_name,
                "renderer_version": self.version,
                "strict": effective_strict,
                "template_characters": len(template),
            },
        )

    def extract_variables(
        self,
        template: str,
    ) -> tuple[str, ...]:
        """
        Devuelve las variables únicas utilizadas por una plantilla.
        """

        if not isinstance(template, str):
            raise TypeError(
                "template debe ser una cadena de texto."
            )

        ordered: list[str] = []
        for match in _VARIABLE_PATTERN.finditer(template):
            variable = match.group(1)
            if variable not in ordered:
                ordered.append(variable)

        return tuple(ordered)

    def validate_template(
        self,
        template: str,
        variables: Mapping[str, Any] | None = None,
    ) -> list[str]:
        """
        Valida una plantilla sin lanzar errores por variables faltantes.
        """

        errors: list[str] = []

        if not isinstance(template, str):
            return [
                "template debe ser una cadena de texto."
            ]

        if not template.strip():
            return [
                "La plantilla del prompt está vacía."
            ]

        source = dict(variables or {})
        for variable in self.extract_variables(template):
            found, _ = self._resolve_path(
                source,
                variable,
            )
            if not found:
                errors.append(
                    f"Variable no encontrada: {variable}"
                )

        return errors

    def _build_sections(
        self,
        prompt_object: PromptObject,
    ) -> list[str]:
        """
        Construye las secciones oficiales del prompt.
        """

        project = prompt_object.project
        context = prompt_object.context

        sections = [
            self._section(
                "Identidad del proyecto",
                self._project_identity(project),
            ),
            self._section(
                "Objetivo",
                prompt_object.objective,
            ),
            self._section(
                "Contexto y conocimiento disponible",
                context.content,
            ),
        ]

        if context.modules:
            sections.append(
                self._section(
                    "Módulos de conocimiento utilizados",
                    self._knowledge_modules(
                        context.modules
                    ),
                )
            )

        if prompt_object.restrictions:
            sections.append(
                self._section(
                    "Restricciones obligatorias",
                    self._bullet_list(
                        prompt_object.restrictions
                    ),
                )
            )

        sections.append(
            self._section(
                "Formato de salida",
                (
                    "Entrega el resultado en formato "
                    f"{prompt_object.output_format.strip()}."
                ),
            )
        )

        sections.append(
            self._section(
                "Instrucción final",
                (
                    "Cumple el objetivo utilizando únicamente el "
                    "contexto pertinente. Separa claramente hechos, "
                    "inferencias y recomendaciones. No inventes datos "
                    "ni fuentes. Cuando falte información necesaria, "
                    "decláralo de forma explícita."
                ),
            )
        )

        if self.include_metadata and prompt_object.metadata:
            sections.append(
                self._section(
                    "Metadatos operativos",
                    self._format_value(
                        prompt_object.metadata
                    ),
                )
            )

        return sections

    def _build_render_context(
        self,
        prompt_object: PromptObject,
        variables: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Crea el espacio de variables disponible al renderizar.
        """

        project = prompt_object.project
        context = prompt_object.context

        source: dict[str, Any] = {
            "project": project,
            "context": context,
            "prompt": prompt_object,
            "objective": prompt_object.objective,
            "output_format": prompt_object.output_format,
            "restrictions": prompt_object.restrictions,
            "metadata": prompt_object.metadata,
        }

        if variables:
            source.update(dict(variables))

        return source

    def _validate_prompt_object(
        self,
        prompt_object: PromptObject,
    ) -> None:
        """
        Valida el contrato mínimo requerido para renderizar.
        """

        if not isinstance(prompt_object, PromptObject):
            raise TypeError(
                "prompt_object debe ser PromptObject."
            )

        if not prompt_object.objective.strip():
            raise PromptRenderError(
                "El objetivo del prompt está vacío."
            )

        if not prompt_object.context.content.strip():
            raise PromptRenderError(
                "El contexto del prompt está vacío."
            )

        if not prompt_object.output_format.strip():
            raise PromptRenderError(
                "El formato de salida está vacío."
            )

    def _project_identity(
        self,
        project: Any,
    ) -> str:
        """
        Construye la identidad operativa del proyecto.
        """

        rows = [
            f"- **ID:** {project.project_id}",
            f"- **Tema:** {project.tema or 'No especificado'}",
            f"- **Stage actual:** {project.stage_actual}",
            f"- **Estado:** {project.estado}",
        ]

        return "\n".join(rows)

    def _knowledge_modules(
        self,
        modules: list[Any],
    ) -> str:
        """
        Resume los módulos sin duplicar su contenido.
        """

        rows: list[str] = []

        for module in modules:
            name = str(module.name or module.module_id).strip()
            category = str(
                module.category or "sin categoría"
            ).strip()
            rows.append(
                f"- **{name}** — categoría: {category}; "
                f"id: `{module.module_id}`"
            )

        return "\n".join(rows)

    def _section(
        self,
        title: str,
        content: str,
    ) -> str:
        """
        Renderiza una sección Markdown.
        """

        clean_title = str(title or "").strip()
        clean_content = str(content or "").strip()

        if not clean_title:
            raise PromptRenderError(
                "Una sección no tiene título."
            )

        if not clean_content:
            raise PromptRenderError(
                f"La sección '{clean_title}' está vacía."
            )

        heading = "#" * self.heading_level
        return f"{heading} {clean_title}\n\n{clean_content}"

    def _join_sections(
        self,
        sections: list[str],
    ) -> str:
        """
        Une secciones eliminando bloques vacíos.
        """

        clean = [
            section.strip()
            for section in sections
            if section and section.strip()
        ]

        if not clean:
            raise PromptRenderError(
                "No se generaron secciones para el prompt."
            )

        return "\n\n".join(clean)

    def _resolve_path(
        self,
        source: Mapping[str, Any],
        path: str,
    ) -> tuple[bool, Any]:
        """
        Resuelve una ruta usando Mapping, atributos y dataclasses.
        """

        current: Any = source

        for segment in path.split("."):
            if isinstance(current, Mapping):
                if segment not in current:
                    return False, None
                current = current[segment]
                continue

            if is_dataclass(current):
                if not hasattr(current, segment):
                    return False, None
                current = getattr(current, segment)
                continue

            if hasattr(current, segment):
                current = getattr(current, segment)
                continue

            return False, None

        return True, current

    def _format_value(
        self,
        value: Any,
    ) -> str:
        """
        Convierte valores Python a texto estable para prompts.
        """

        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, Mapping):
            return json.dumps(
                self._to_primitive(value),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

        if is_dataclass(value):
            return json.dumps(
                self._to_primitive(value),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )

        if isinstance(
            value,
            (list, tuple, set, frozenset),
        ):
            return self._bullet_list(value)

        return str(value).strip()

    def _bullet_list(
        self,
        values: Any,
    ) -> str:
        """
        Convierte una colección en viñetas Markdown.
        """

        rows: list[str] = []

        for value in values:
            text = self._format_value(value)
            if text:
                rows.append(f"- {text}")

        return "\n".join(rows)

    def _to_primitive(
        self,
        value: Any,
    ) -> Any:
        """
        Convierte estructuras complejas a tipos serializables.
        """

        if is_dataclass(value):
            return {
                key: self._to_primitive(item)
                for key, item in asdict(value).items()
            }

        if isinstance(value, Mapping):
            return {
                str(key): self._to_primitive(item)
                for key, item in value.items()
            }

        if isinstance(
            value,
            (list, tuple, set, frozenset),
        ):
            return [
                self._to_primitive(item)
                for item in value
            ]

        return value

    def _normalize_output(
        self,
        content: str,
    ) -> str:
        """
        Normaliza saltos de línea sin modificar el contenido semántico.
        """

        normalized = content.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        normalized = re.sub(
            r"\n{3,}",
            "\n\n",
            normalized,
        )

        return normalized.strip() + "\n"

    @staticmethod
    def _normalize_heading_level(
        value: int,
    ) -> int:
        """
        Limita el nivel Markdown entre 1 y 6.
        """

        try:
            level = int(value)
        except (TypeError, ValueError) as error:
            raise TypeError(
                "heading_level debe ser un entero."
            ) from error

        if not 1 <= level <= 6:
            raise ValueError(
                "heading_level debe estar entre 1 y 6."
            )

        return level


def render_prompt(
    prompt_object: PromptObject,
    variables: Mapping[str, Any] | None = None,
    *,
    strict: bool = True,
    include_metadata: bool = False,
) -> str:
    """
    Función de conveniencia para renderizar PromptObject.
    """

    renderer = PromptRenderer(
        strict=strict,
        include_metadata=include_metadata,
    )

    return renderer.render_text(
        prompt_object=prompt_object,
        variables=variables,
    )