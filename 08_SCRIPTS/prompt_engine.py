"""
=========================================================
Proyecto : CIPS
Release  : 0.6
Build    : 042
Archivo  : prompt_engine.py
Estado   : RELEASE
=========================================================

Construye el PromptObject y genera el archivo Markdown
correspondiente al Stage actual.

El PromptEngine mantiene alineados:

- objetivo del Stage;
- contexto operativo;
- restricciones editoriales;
- reglas profesionales de validación;
- encabezados obligatorios;
- encabezados recomendados;
- extensión mínima esperada.

Compatibilidad:
- PipelineEngine mediante execute(Project, ContextObject).
- PipelineRunner mediante execute(RuntimeContext).
"""

from pathlib import Path
from typing import Any

from editorial_contract import render_traceability_contract
from runtime_component import RuntimeComponent
from runtime_context import RuntimeContext
from runtime_models import (
    ContextObject,
    EngineResult,
    Project,
    PromptObject,
)
from utils import ROOT, read_yaml, write_text


VALIDATION_RULES_PATH = (
    ROOT
    / "01_CONFIG"
    / "validation_rules.yaml"
)


class PromptEngine(RuntimeComponent):
    """
    Construye prompts estructurados para el Runtime de CIPS.

    Admite dos formas de ejecución:

    1. execute(Project, ContextObject)
       Mantiene compatibilidad con PipelineEngine.

    2. execute(RuntimeContext)
       Implementa el contrato del Runtime Framework.

    El motor consulta validation_rules.yaml para garantizar
    que la respuesta solicitada pueda superar posteriormente
    la validación profesional del Stage.
    """

    component_name = "prompt_engine"

    DEFAULT_RESTRICTIONS = [
        "No inventes datos.",
        "No exageres beneficios.",
        "No uses lenguaje sensacionalista.",
        "Respeta la evidencia disponible.",
        "Distingue hechos, opiniones e incertidumbre.",
        "No presentes afirmaciones dudosas como hechos confirmados.",
        "No copies instrucciones internas del prompt.",
        "Entrega únicamente el resultado solicitado.",
    ]

    STAGE_OBJECTIVES = {
        "investigacion": (
            "Realizar una investigación clara, útil, estructurada "
            "y confiable sobre el tema del proyecto."
        ),
        "verificacion": (
            "Verificar la investigación previa, clasificar la "
            "calidad de la evidencia y señalar limitaciones."
        ),
        "guion": (
            "Convertir la información validada en un guion claro, "
            "atractivo, responsable y listo para producción."
        ),
        "storyboard": (
            "Transformar el guion en una estructura visual "
            "organizada escena por escena."
        ),
        "seo": (
            "Optimizar el contenido para descubrimiento en "
            "plataformas digitales sin perder credibilidad."
        ),
        "publicacion": (
            "Preparar el paquete editorial final listo para "
            "publicación en la plataforma correspondiente."
        ),
        "narracion": (
            "Convertir el guion y storyboard verificados en una narración "
            "textual natural, pronunciable y ajustada a la duración solicitada."
        ),
        "final": (
            "Consolidar los entregables validados del proyecto "
            "en un resultado final coherente y publicable."
        ),
    }

    def execute(
        self,
        runtime_input: Project | RuntimeContext,
        context: ContextObject | None = None,
    ) -> EngineResult:
        """
        Construye el prompt correspondiente al Stage actual.
        """

        try:
            runtime_context = self._get_runtime_context(
                runtime_input
            )

            project = self._get_project(
                runtime_input
            )

            context_object = self._get_context_object(
                runtime_input=runtime_input,
                context=context,
            )

            if context_object is None:
                return EngineResult.fail(
                    message=(
                        "No existe un ContextObject para "
                        "construir el prompt."
                    ),
                    errors=[
                        "ContextObject no disponible."
                    ],
                    metadata=self._base_metadata(
                        project
                    ),
                )

            if not context_object.content.strip():
                return EngineResult.fail(
                    message="El contexto está vacío.",
                    errors=[
                        "ContextObject.content vacío."
                    ],
                    metadata=self._base_metadata(
                        project
                    ),
                )

            validation_rules = self._load_validation_rules()

            stage_contract = self._build_stage_contract(
                project=project,
                validation_rules=validation_rules,
            )

            objective = self._build_objective(
                project
            )

            restrictions = self._build_restrictions(
                validation_rules
            )

            prompt_object = PromptObject(
                project=project,
                objective=objective,
                context=context_object,
                output_format=(
                    "texto plano UTF-8"
                    if project.stage_actual == "narracion"
                    else "Markdown"
                ),
                restrictions=restrictions,
                metadata={
                    "component": self.component_name,
                    "stage": project.stage_actual,
                    "project_id": project.project_id,
                    "context_characters": len(
                        context_object.content
                    ),
                    "modules_count": len(
                        context_object.modules
                    ),
                    "validation_contract": (
                        stage_contract
                    ),
                    "validation_rules_path": str(
                        VALIDATION_RULES_PATH
                    ),
                },
            )

            prompt_markdown = self._render_markdown(
                prompt=prompt_object,
                stage_contract=stage_contract,
            )

            prompt_path = self._save_prompt(
                project=project,
                prompt_markdown=prompt_markdown,
            )

            metadata = {
                **self._base_metadata(project),
                "prompt_path": str(prompt_path),
                "characters": len(prompt_markdown),
                "context_characters": len(
                    context_object.content
                ),
                "modules_count": len(
                    context_object.modules
                ),
                "minimum_characters": (
                    stage_contract[
                        "minimum_characters"
                    ]
                ),
                "minimum_words": (
                    stage_contract[
                        "minimum_words"
                    ]
                ),
                "required_headings": (
                    stage_contract[
                        "required_headings"
                    ]
                ),
                "recommended_headings": (
                    stage_contract[
                        "recommended_headings"
                    ]
                ),
                "validation_rules_path": str(
                    VALIDATION_RULES_PATH
                ),
            }

            if runtime_context is not None:
                runtime_context.prompt_object = (
                    prompt_object
                )

                runtime_context.prompt_markdown = (
                    prompt_markdown
                )

                runtime_context.prompt_path = str(
                    prompt_path
                )

                runtime_context.metadata[
                    "prompt_contract"
                ] = stage_contract

                return EngineResult.ok(
                    data=runtime_context,
                    message=(
                        "Prompt construido en RuntimeContext "
                        "con contrato de validación."
                    ),
                    metadata=metadata,
                )

            return EngineResult.ok(
                data={
                    "prompt_object": prompt_object,
                    "prompt_markdown": prompt_markdown,
                    "prompt_path": str(prompt_path),
                    "stage_contract": stage_contract,
                },
                message=(
                    "Prompt construido correctamente "
                    "con contrato de validación."
                ),
                metadata=metadata,
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en PromptEngine.",
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
        Devuelve RuntimeContext cuando se utiliza
        el nuevo Runtime Framework.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input

        return None

    def _get_project(
        self,
        runtime_input: Project | RuntimeContext,
    ) -> Project:
        """
        Obtiene Project desde cualquiera de las interfaces.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.project

        if isinstance(
            runtime_input,
            Project,
        ):
            return runtime_input

        raise TypeError(
            "PromptEngine requiere "
            "Project o RuntimeContext."
        )

    def _get_context_object(
        self,
        runtime_input: Project | RuntimeContext,
        context: ContextObject | None,
    ) -> ContextObject | None:
        """
        Obtiene ContextObject desde RuntimeContext
        o desde el argumento legado.
        """

        if isinstance(
            runtime_input,
            RuntimeContext,
        ):
            return runtime_input.context_object

        return context

    def _load_validation_rules(
        self,
    ) -> dict[str, Any]:
        """
        Carga las reglas profesionales de validación.
        """

        rules = read_yaml(
            VALIDATION_RULES_PATH
        )

        if not isinstance(
            rules,
            dict,
        ):
            raise ValueError(
                "validation_rules.yaml no contiene "
                "una estructura válida."
            )

        return rules

    def _build_stage_contract(
        self,
        project: Project,
        validation_rules: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Construye el contrato de salida del Stage actual.
        """

        general_rules = validation_rules.get(
            "general",
            {},
        )

        if not isinstance(
            general_rules,
            dict,
        ):
            general_rules = {}

        stages = validation_rules.get(
            "stages",
            {},
        )

        if not isinstance(
            stages,
            dict,
        ):
            stages = {}

        stage_rules = stages.get(
            project.stage_actual,
            {},
        )

        if not isinstance(
            stage_rules,
            dict,
        ):
            stage_rules = {}

        minimum_characters = self._safe_positive_int(
            stage_rules.get(
                "minimum_characters",
                general_rules.get(
                    "minimum_characters",
                    300,
                ),
            ),
            default=300,
        )

        minimum_words = self._safe_positive_int(
            stage_rules.get(
                "minimum_words",
                general_rules.get(
                    "minimum_words",
                    50,
                ),
            ),
            default=50,
        )

        required_headings = self._normalize_headings(
            stage_rules.get(
                "required_headings",
                [],
            )
        )

        recommended_headings = self._normalize_headings(
            stage_rules.get(
                "recommended_headings",
                [],
            )
        )

        passing_score = self._safe_positive_int(
            general_rules.get(
                "passing_score",
                70,
            ),
            default=70,
        )

        return {
            "stage": project.stage_actual,
            "minimum_characters": minimum_characters,
            "minimum_words": minimum_words,
            "required_headings": required_headings,
            "recommended_headings": recommended_headings,
            "passing_score": passing_score,
        }

    def _build_objective(
        self,
        project: Project,
    ) -> str:
        """
        Devuelve el objetivo operativo del Stage actual.
        """

        return self.STAGE_OBJECTIVES.get(
            project.stage_actual,
            (
                "Generar el entregable correspondiente "
                "al Stage actual del proyecto."
            ),
        )

    def _build_restrictions(
        self,
        validation_rules: dict[str, Any],
    ) -> list[str]:
        """
        Combina restricciones generales con criterios
        relevantes del ValidatorEngine.
        """

        restrictions = list(
            self.DEFAULT_RESTRICTIONS
        )

        quality_rules = validation_rules.get(
            "quality",
            {},
        )

        if isinstance(
            quality_rules,
            dict,
        ):
            sensationalism_markers = (
                quality_rules.get(
                    "sensationalism_markers",
                    [],
                )
            )

            if isinstance(
                sensationalism_markers,
                list,
            ) and sensationalism_markers:
                markers = ", ".join(
                    str(marker)
                    for marker
                    in sensationalism_markers
                )

                restrictions.append(
                    "Evita expresiones sensacionalistas "
                    f"como: {markers}."
                )

        restrictions.append(
            "La respuesta debe terminar de forma completa, "
            "sin frases cortadas, listas inconclusas ni "
            "marcadores de continuación."
        )

        restrictions.append(
            "Todos los encabezados obligatorios deben aparecer "
            "exactamente como se solicitan."
        )

        return self._deduplicate_text_list(
            restrictions
        )

    def _render_markdown(
        self,
        prompt: PromptObject,
        stage_contract: dict[str, Any],
    ) -> str:
        """
        Renderiza el PromptObject en Markdown.
        """

        restrictions = "\n".join(
            f"- {item}"
            for item in prompt.restrictions
        )

        if prompt.project.stage_actual == "narracion":
            required_structure = (
                "No uses encabezados. Entrega únicamente párrafos de locución "
                "en texto plano."
            )
        else:
            required_structure = (
                self._render_required_headings(
                    stage_contract[
                        "required_headings"
                    ]
                )
            )

        recommended_structure = (
            self._render_recommended_headings(
                stage_contract[
                    "recommended_headings"
                ]
            )
        )

        editorial_contract_applied = bool(
            prompt.context.metadata.get("editorial_context_applied", False)
        )
        editorial_contract = (
            render_traceability_contract(prompt.project.stage_actual)
            if editorial_contract_applied
            else "- Se conserva el contrato histórico de este proyecto."
        )

        return f"""# PROMPT CIPS

## Proyecto

ID: {prompt.project.project_id}

Tema: {prompt.project.tema}

Stage actual: {prompt.project.stage_actual}

---

## Objetivo

{prompt.objective}

---

## Contexto operativo del sistema

{prompt.context.content}

---

## Contrato obligatorio de salida

La respuesta será evaluada automáticamente por ValidatorEngine.

Debe cumplir todos estos requisitos:

- Extensión mínima: {stage_contract["minimum_characters"]} caracteres.
- Extensión mínima: {stage_contract["minimum_words"]} palabras.
- Puntuación mínima de aprobación: {stage_contract["passing_score"]}/100.
- Debe contener oraciones completas.
- Debe terminar de forma natural y completa.
- No debe incluir contenido pendiente ni frases truncadas.
- No debe copiar instrucciones internas del prompt.

### Encabezados obligatorios

{required_structure}

### Reglas para los encabezados obligatorios

- Utiliza cada encabezado obligatorio como encabezado Markdown.
- Escríbelos exactamente con el nombre indicado.
- No omitas ninguno.
- No los renombres.
- No los combines entre sí.
- Incluye contenido sustancial debajo de cada encabezado.

### Encabezados recomendados

{recommended_structure}

Los encabezados recomendados mejoran la calidad y la puntuación
de la respuesta, pero no sustituyen a los obligatorios.

---

## Contrato editorial verificable FAO.3

{editorial_contract}

La solicitud operativa y los entregables aprobados incluidos en el contexto
son autoritativos. No contradigas sus campos ni introduzcas afirmaciones que
no puedan rastrearse hasta ese material.

---

## Restricciones editoriales

{restrictions}

---

## Formato de salida

Entrega la respuesta exclusivamente en {prompt.output_format}.

No saludes.

No expliques cómo realizaste la tarea.

No describas el prompt.

No incluyas comentarios dirigidos al operador.

No incluyas texto fuera del entregable.

---

## Entregable esperado

Genera el contenido completo correspondiente al Stage:

**{prompt.project.stage_actual}**

Antes de finalizar, verifica internamente que:

- todos los encabezados obligatorios estén presentes;
- la extensión mínima se haya cumplido;
- la respuesta no esté truncada;
- cada sección tenga contenido útil;
- el cierre sea completo.
"""

    def _render_required_headings(
        self,
        headings: list[str],
    ) -> str:
        """
        Renderiza la estructura obligatoria.

        Cuando el Stage no define encabezados específicos,
        solicita al menos un encabezado representativo.
        """

        if not headings:
            return (
                "# RESULTADO\n\n"
                "Incluye debajo el contenido completo "
                "correspondiente al Stage."
            )

        blocks: list[str] = []

        for heading in headings:
            blocks.append(
                f"# {heading}\n\n"
                f"Desarrolla aquí la sección {heading}."
            )

        return "\n\n".join(
            blocks
        )

    def _render_recommended_headings(
        self,
        headings: list[str],
    ) -> str:
        """
        Renderiza los encabezados recomendados.
        """

        if not headings:
            return (
                "- No existen encabezados recomendados "
                "adicionales para este Stage."
            )

        return "\n".join(
            f"- {heading}"
            for heading in headings
        )

    def _normalize_headings(
        self,
        values: Any,
    ) -> list[str]:
        """
        Normaliza encabezados sin duplicados.
        """

        if not isinstance(
            values,
            list,
        ):
            return []

        normalized: list[str] = []

        for value in values:
            heading = str(
                value
            ).strip().upper()

            if (
                heading
                and heading not in normalized
            ):
                normalized.append(
                    heading
                )

        return normalized

    def _deduplicate_text_list(
        self,
        values: list[str],
    ) -> list[str]:
        """
        Elimina restricciones duplicadas conservando orden.
        """

        unique_values: list[str] = []

        for value in values:
            normalized = value.strip()

            if (
                normalized
                and normalized not in unique_values
            ):
                unique_values.append(
                    normalized
                )

        return unique_values

    def _safe_positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        """
        Convierte un valor a entero positivo.
        """

        try:
            number = int(value)

        except (TypeError, ValueError):
            return default

        if number <= 0:
            return default

        return number

    def _save_prompt(
        self,
        project: Project,
        prompt_markdown: str,
    ) -> Path:
        """
        Guarda el prompt dentro del proyecto activo.
        """

        prompts_dir = (
            project.path
            / "02_PROMPTS"
        )

        prompts_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = (
            f"PROMPT_"
            f"{project.stage_actual.upper()}.md"
        )

        prompt_path = (
            prompts_dir
            / filename
        )

        write_text(
            prompt_path,
            prompt_markdown,
        )

        return prompt_path

    def _base_metadata(
        self,
        project: Project,
    ) -> dict[str, Any]:
        """
        Construye metadatos comunes del componente.
        """

        return {
            "component": self.component_name,
            "project_id": project.project_id,
            "stage": project.stage_actual,
        }
