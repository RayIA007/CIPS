"""
CIPS - Prompt Builder
Construye prompts optimizados para trabajar con IA gratuitas.
"""

from pathlib import Path

from utils import ROOT, write_text, read_yaml, current_datetime
from logger import Logger


PROJECTS_DIR = ROOT / "04_PROYECTOS"


class PromptBuilder:
    def get_latest_project(self) -> Path:
        projects = sorted(
            [p for p in PROJECTS_DIR.iterdir() if p.is_dir() and p.name.startswith("PROYECTO_")]
        )

        if not projects:
            raise FileNotFoundError("No existe ningún proyecto creado.")

        return projects[-1]

    def build_research_prompt(self, project_path: Path) -> str:
        proyecto = read_yaml(project_path / "proyecto.yaml")
        contexto = (project_path / "CONTEXTO.md").read_text(encoding="utf-8")

        tema = proyecto.get("tema", "Tema no definido")

        prompt = f"""
# PROMPT MAESTRO — INVESTIGACIÓN Y VERIFICACIÓN

Actúa como un equipo experto compuesto por:

- Investigador científico en salud.
- Nutriólogo basado en evidencia.
- Entrenador físico profesional.
- Verificador de información médica.
- Estratega de contenido para YouTube, TikTok e Instagram.

## Tema del contenido

{tema}

## Contexto del proyecto

{contexto}

## Misión

Realiza una investigación clara, útil y confiable sobre el tema.

El contenido debe enfocarse en la intersección de:

- Alimentación.
- Ejercicio.
- Salud.

## Reglas de credibilidad

1. No inventes datos.
2. No exageres beneficios.
3. Distingue entre evidencia fuerte, moderada y limitada.
4. Señala riesgos, contraindicaciones o casos donde se debe consultar a un profesional.
5. Si mencionas estudios, guías o instituciones, indica claramente cuáles son.
6. Evita promesas absolutas como “cura”, “garantizado” o “milagroso”.

## Entregable requerido

Devuelve exclusivamente en Markdown con esta estructura:

# Investigación

## 1. Resumen ejecutivo

## 2. Lo que sí se sabe con buena evidencia

## 3. Lo que tiene evidencia moderada o limitada

## 4. Riesgos, errores comunes o malentendidos

## 5. Aplicación práctica para una persona común

## 6. Ideas de contenido viral confiable

## 7. Fuentes o referencias recomendadas para verificar

## 8. Resumen para el siguiente módulo

Máximo 1,200 palabras.
No saludes.
No expliques el prompt.
Solo entrega el contenido.
"""

        return prompt.strip()

    def create_next_prompt(self) -> dict:
        project_path = self.get_latest_project()

        prompt = self.build_research_prompt(project_path)

        prompts_dir = project_path / "02_PROMPTS"
        prompts_dir.mkdir(exist_ok=True)

        prompt_path = prompts_dir / "PROMPT_01_INVESTIGACION.md"
        write_text(prompt_path, prompt)

        Logger.info(f"Prompt generado: {prompt_path}")

        return {
            "project": project_path.name,
            "prompt_path": str(prompt_path),
        }