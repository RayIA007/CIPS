"""
ConsejoIA_V5
Content Pipeline MVP

Orquestador principal de generación de contenido.
"""

from datetime import datetime
from pathlib import Path

from research_stage import ResearchStage
from script_stage import ScriptStage, ScriptRequest


class ContentPipeline:
    """
    Orquesta la generación del contenido.
    """

    def __init__(self, output_root: str | Path = "05_OUTPUTS"):

        self.output_root = Path(output_root)

    def run(
        self,
        topic: str,
        platform: str,
    ) -> Path:

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        project = (
            self.output_root
            / platform.lower()
            / timestamp
        )

        project.mkdir(
            parents=True,
            exist_ok=True,
        )

        # -----------------------------------------------------
        # Research Stage
        # -----------------------------------------------------

        research_stage = ResearchStage()

        research_request = research_stage.build_request(
            topic=topic,
            platform=platform,
        )

        # -----------------------------------------------------
        # Script Stage
        # -----------------------------------------------------

        script_stage = ScriptStage()

        script_request = ScriptRequest(
            topic=research_request.topic,
            platform=research_request.platform,
            duration=research_request.duration,
            objective=research_request.objective,
        )

        script = script_stage.build_script(
            script_request
        )

        # -----------------------------------------------------
        # Archivos del proyecto
        # -----------------------------------------------------

        files = {

            "idea.md":

            (
                "# Idea\n\n"
                f"{topic}\n"
            ),

            "research.md":

            (
                "# Briefing de Investigación\n\n"

                f"## Tema\n\n"
                f"{research_request.topic}\n\n"

                f"## Plataforma\n\n"
                f"{research_request.platform}\n\n"

                f"## Audiencia\n\n"
                f"{research_request.target_audience}\n\n"

                f"## Objetivo\n\n"
                f"{research_request.objective}\n\n"

                f"## Idioma\n\n"
                f"{research_request.language}\n\n"

                f"## Duración\n\n"
                f"{research_request.duration}\n"
            ),

            "knowledge.md":

            (
                "# Knowledge Assets\n\n"
                "Pendiente.\n"
            ),

            "script.md":

            script,

            "storyboard.md":

            (
                "# Storyboard\n\n"
                "Pendiente.\n"
            ),

            "image_prompts.md":

            (
                "# Prompts de Imágenes\n\n"
                "Pendiente.\n"
            ),

            "video_prompts.md":

            (
                "# Prompts de Video\n\n"
                "Pendiente.\n"
            ),

            "thumbnail_prompt.md":

            (
                "# Prompt para Thumbnail\n\n"
                "Pendiente.\n"
            ),
        }

        for filename, content in files.items():

            (project / filename).write_text(
                content,
                encoding="utf-8",
            )

        return project