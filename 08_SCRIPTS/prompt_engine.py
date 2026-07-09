"""
=========================================================
Proyecto : CIPS
Release  : 0.3
Build    : 007
Archivo  : prompt_engine.py
Estado   : RELEASE
=========================================================
"""

from pathlib import Path

from runtime_models import (
    EngineResult,
    PromptObject,
    ContextObject,
    Project,
)
from utils import write_text


class PromptEngine:
    """
    Construye prompts estructurados para el Runtime 0.3.
    """

    def execute(
        self,
        project: Project,
        context: ContextObject,
    ) -> EngineResult:

        try:
            if not context.content.strip():
                return EngineResult.fail(
                    message="El contexto está vacío.",
                    errors=["ContextObject.content vacío"],
                )

            objective = self._build_objective(project)

            prompt_object = PromptObject(
                project=project,
                objective=objective,
                context=context,
                output_format="Markdown",
                restrictions=[
                    "No inventes datos.",
                    "No exageres beneficios.",
                    "No uses lenguaje sensacionalista.",
                    "Respeta la evidencia disponible.",
                    "Distingue hechos, opiniones e incertidumbre.",
                    "Entrega únicamente el resultado solicitado.",
                ],
                metadata={
                    "stage": project.stage_actual,
                    "project_id": project.project_id,
                },
            )

            prompt_markdown = self._render_markdown(prompt_object)
            prompt_path = self._save_prompt(project, prompt_markdown)

            return EngineResult.ok(
                data={
                    "prompt_object": prompt_object,
                    "prompt_markdown": prompt_markdown,
                    "prompt_path": str(prompt_path),
                },
                message="Prompt construido correctamente.",
                metadata={
                    "prompt_path": str(prompt_path),
                    "characters": len(prompt_markdown),
                },
            )

        except Exception as error:
            return EngineResult.fail(
                message="Error inesperado en PromptEngine.",
                errors=[str(error)],
            )

    def _build_objective(self, project: Project) -> str:
        objectives = {
            "investigacion": "Realizar una investigación clara, útil y confiable sobre el tema del proyecto.",
            "verificacion": "Verificar la investigación previa y clasificar la calidad de la evidencia.",
            "guion": "Convertir la información validada en un guion claro, atractivo y responsable.",
            "storyboard": "Transformar el guion en una estructura visual escena por escena.",
            "seo": "Optimizar el contenido para descubrimiento en plataformas digitales sin perder credibilidad.",
            "publicacion": "Preparar el paquete final listo para publicación.",
        }

        return objectives.get(
            project.stage_actual,
            "Generar el entregable correspondiente al Stage actual del proyecto.",
        )

    def _render_markdown(self, prompt: PromptObject) -> str:
        restrictions = "\n".join(
            f"- {item}" for item in prompt.restrictions
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

## Contexto del sistema

{prompt.context.content}

---

## Restricciones

{restrictions}

---

## Formato de salida

Entrega la respuesta exclusivamente en {prompt.output_format}.

No saludes.

No expliques el prompt.

No incluyas texto fuera del entregable.

---

## Entregable esperado

Genera el contenido correspondiente al Stage actual:

**{prompt.project.stage_actual}**
"""

    def _save_prompt(
        self,
        project: Project,
        prompt_markdown: str,
    ) -> Path:

        prompts_dir = project.path / "02_PROMPTS"
        prompts_dir.mkdir(exist_ok=True)

        filename = f"PROMPT_{project.stage_actual.upper()}.md"
        prompt_path = prompts_dir / filename

        write_text(prompt_path, prompt_markdown)

        return prompt_path