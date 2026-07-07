"""
CIPS - Pipeline
Controla el avance automático del proyecto.
"""

from pathlib import Path

from utils import ROOT, write_text, read_yaml, write_yaml, current_datetime
from logger import Logger
from validator import Validator


PROJECTS_DIR = ROOT / "04_PROYECTOS"


STAGES = [
    {
        "estado": "investigacion",
        "input": "CONTEXTO.md",
        "output": "01_INVESTIGACION.md",
        "prompt": "PROMPT_01_INVESTIGACION.md",
        "next_estado": "verificacion",
        "ia": "Gemini",
    },
    {
        "estado": "verificacion",
        "input": "01_INVESTIGACION.md",
        "output": "02_VERIFICACION.md",
        "prompt": "PROMPT_02_VERIFICACION.md",
        "next_estado": "guion",
        "ia": "Gemini",
    },
    {
        "estado": "guion",
        "input": "02_VERIFICACION.md",
        "output": "03_GUION.md",
        "prompt": "PROMPT_03_GUION.md",
        "next_estado": "storyboard",
        "ia": "ChatGPT",
    },
    {
        "estado": "storyboard",
        "input": "03_GUION.md",
        "output": "04_STORYBOARD.md",
        "prompt": "PROMPT_04_STORYBOARD.md",
        "next_estado": "seo",
        "ia": "ChatGPT",
    },
    {
        "estado": "seo",
        "input": "04_STORYBOARD.md",
        "output": "05_SEO.md",
        "prompt": "PROMPT_05_SEO.md",
        "next_estado": "publicacion",
        "ia": "Gemini",
    },
    {
        "estado": "publicacion",
        "input": "05_SEO.md",
        "output": "06_PUBLICACION.md",
        "prompt": "PROMPT_06_PUBLICACION.md",
        "next_estado": "final",
        "ia": "Claude o ChatGPT",
    },
]


class Pipeline:
    def get_latest_project(self) -> Path:
        projects = sorted(
            [
                p for p in PROJECTS_DIR.iterdir()
                if p.is_dir() and p.name.startswith("PROYECTO_")
            ]
        )

        if not projects:
            raise FileNotFoundError("No existe ningún proyecto creado.")

        return projects[-1]

    def get_stage(self, estado: str) -> dict:
        for stage in STAGES:
            if stage["estado"] == estado:
                return stage

        raise ValueError(f"Estado no reconocido: {estado}")

    def is_file_completed(self, path: Path) -> bool:
        if not path.exists():
            return False

        content = path.read_text(encoding="utf-8").strip()

        if not content:
            return False

        if content.lower() == "pendiente":
            return False

        if "pendiente" in content.lower() and len(content) < 80:
            return False

        return True

    def update_project_state(self, project_path: Path, new_state: str) -> None:
        yaml_path = project_path / "proyecto.yaml"
        data = read_yaml(yaml_path)

        old_state = data.get("estado")

        data["estado"] = new_state
        data["ultima_modificacion"] = current_datetime()

        if "pipeline" in data and old_state in data["pipeline"]:
            data["pipeline"][old_state] = "completado"

        if "pipeline" in data and new_state in data["pipeline"]:
            if data["pipeline"][new_state] != "completado":
                data["pipeline"][new_state] = "en_proceso"

        write_yaml(yaml_path, data)

    def build_prompt(self, project_path: Path, stage: dict) -> str:
        project_data = read_yaml(project_path / "proyecto.yaml")
        tema = project_data.get("tema", "Tema no definido")

        input_path = project_path / stage["input"]
        input_content = input_path.read_text(encoding="utf-8")

        estado = stage["estado"]

        if estado == "verificacion":
            instruction = """
Actúa como verificador científico experto en salud, alimentación y ejercicio.
Evalúa la investigación previa. Detecta afirmaciones débiles, exageradas o riesgosas.
Clasifica la evidencia como fuerte, moderada o limitada.
Señala qué partes deben usarse con cuidado.
Devuelve una versión validada y segura para crear contenido.
"""

        elif estado == "guion":
            instruction = """
Actúa como guionista viral especializado en contenido confiable de salud.
Convierte la verificación científica en un guion para video corto de 45 a 60 segundos.
Usa hook fuerte, desarrollo claro, ejemplo práctico y cierre con CTA.
No exageres beneficios. Mantén credibilidad.
"""

        elif estado == "storyboard":
            instruction = """
Actúa como director creativo y editor de video.
Convierte el guion en storyboard escena por escena.
Incluye texto en pantalla, visual sugerido, ritmo, cortes, B-roll e indicaciones de edición.
"""

        elif estado == "seo":
            instruction = """
Actúa como experto SEO para YouTube Shorts, TikTok e Instagram.
Genera títulos, descripción, hashtags, palabras clave, caption y ángulos de publicación.
Optimiza para alcance sin perder credibilidad.
"""

        elif estado == "publicacion":
            instruction = """
Actúa como director editorial.
Integra todo en un paquete final listo para publicar.
Incluye título final, descripción, hashtags, guion final limpio, caption y checklist de publicación.
"""

        else:
            instruction = """
Actúa como investigador experto en alimentación, ejercicio y salud.
Realiza una investigación clara, confiable y práctica.
"""

        prompt = f"""
# PROMPT CIPS — {estado.upper()}

## Tema

{tema}

## IA recomendada

{stage["ia"]}

## Instrucciones

{instruction.strip()}

## Contexto de entrada

{input_content}

## Formato de salida

Devuelve exclusivamente Markdown.
No saludes.
No expliques el prompt.
No incluyas texto fuera del entregable.

## Entregable

Genera el contenido correspondiente para la etapa: {estado}.
"""

        return prompt.strip()

    def continue_project(self) -> dict:
        project_path = self.get_latest_project()

        validator = Validator()
        errors = validator.validate_project(project_path)

        if errors:
            return {
                "ok": False,
                "errors": errors,
            }

        project_data = read_yaml(project_path / "proyecto.yaml")
        estado = project_data.get("estado", "investigacion")

        if estado == "final":
            return {
                "ok": True,
                "finished": True,
                "message": "El proyecto ya está en estado final.",
                "project": project_path.name,
            }

        stage = self.get_stage(estado)

        input_file = project_path / stage["input"]
        output_file = project_path / stage["output"]

        if estado != "investigacion" and not self.is_file_completed(input_file):
            return {
                "ok": False,
                "errors": [
                    f"Falta completar el archivo requerido: {stage['input']}"
                ],
            }

        if self.is_file_completed(output_file):
            self.update_project_state(project_path, stage["next_estado"])
            return {
                "ok": True,
                "advanced": True,
                "message": f"Etapa {estado} marcada como completada.",
                "new_state": stage["next_estado"],
                "project": project_path.name,
            }

        prompt = self.build_prompt(project_path, stage)

        prompts_dir = project_path / "02_PROMPTS"
        prompts_dir.mkdir(exist_ok=True)

        prompt_path = prompts_dir / stage["prompt"]
        write_text(prompt_path, prompt)

        Logger.info(f"Prompt de pipeline generado: {prompt_path}")

        return {
            "ok": True,
            "finished": False,
            "project": project_path.name,
            "state": estado,
            "ia": stage["ia"],
            "prompt_path": str(prompt_path),
            "output_file": str(output_file),
        }