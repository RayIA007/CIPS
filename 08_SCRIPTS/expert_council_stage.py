"""
ConsejoIA_V5
Expert Council Stage

Construye instrucciones profesionales para que un modelo de IA
genere contenido estratégico, verificable y adaptado a una plataforma.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExpertCouncilRequest:
    """
    Datos necesarios para solicitar el análisis del Consejo de Expertos IA.
    """

    topic: str
    platform: str
    target_audience: str
    objective: str
    language: str
    duration: str


class ExpertCouncilStage:
    """
    Construye un prompt estratégico independiente del proveedor de IA.
    """

    def build_prompt(
        self,
        request: ExpertCouncilRequest,
    ) -> str:
        """
        Genera el prompt que utilizará el modelo de lenguaje.

        Args:
            request:
                Información estratégica de la pieza de contenido.

        Returns:
            Prompt completo listo para enviarse a un modelo de IA.
        """

        self._validate_request(request)

        return (
            "# CONSEJO DE EXPERTOS IA PARA CONTENIDO DIGITAL\n\n"
            "Actúa como un consejo multidisciplinario de especialistas "
            "de nivel senior encargado de diseñar una pieza de contenido "
            "precisa, atractiva, útil y publicable.\n\n"

            "## Especialistas que deben intervenir\n\n"
            "1. Estratega senior de contenido digital.\n"
            "2. Investigador y verificador de información.\n"
            "3. Especialista en psicología de la atención.\n"
            "4. Guionista especializado en retención de audiencia.\n"
            "5. Especialista en marketing y monetización digital.\n"
            "6. Experto en algoritmos y buenas prácticas de la plataforma.\n"
            "7. Editor responsable de claridad, coherencia y credibilidad.\n\n"

            "## Datos del proyecto\n\n"
            f"- Tema: {request.topic}\n"
            f"- Plataforma: {request.platform}\n"
            f"- Audiencia objetivo: {request.target_audience}\n"
            f"- Objetivo: {request.objective}\n"
            f"- Idioma: {request.language}\n"
            f"- Duración estimada: {request.duration}\n\n"

            "## Requisitos obligatorios\n\n"
            "- No inventes datos, estadísticas, estudios ni fuentes.\n"
            "- Separa claramente los hechos verificables de las opiniones.\n"
            "- Señala cualquier dato que necesite investigación adicional.\n"
            "- Evita afirmaciones absolutas o engañosas.\n"
            "- Adapta la estructura, ritmo y lenguaje a la plataforma.\n"
            "- Prioriza utilidad, credibilidad y retención de audiencia.\n"
            "- Evita introducciones largas y contenido de relleno.\n"
            "- No prometas resultados económicos garantizados.\n"
            "- El contenido debe ser comprensible para la audiencia indicada.\n\n"

            "## Trabajo solicitado\n\n"
            "Analiza el tema y genera un briefing estratégico que incluya:\n\n"
            "1. Enfoque principal recomendado.\n"
            "2. Problema o necesidad de la audiencia.\n"
            "3. Promesa de valor realista.\n"
            "4. Ángulo diferenciador.\n"
            "5. Tres posibles hooks.\n"
            "6. Puntos esenciales que debe contener el desarrollo.\n"
            "7. Riesgos de desinformación o afirmaciones no verificadas.\n"
            "8. Información que debe investigarse antes de publicar.\n"
            "9. Llamado a la acción recomendado.\n"
            "10. Oportunidad de monetización ética relacionada con el tema.\n\n"

            "## Formato de respuesta\n\n"
            "Devuelve únicamente Markdown estructurado con los siguientes "
            "encabezados exactos:\n\n"
            "# Briefing Estratégico\n\n"
            "## Enfoque recomendado\n\n"
            "## Necesidad de la audiencia\n\n"
            "## Promesa de valor\n\n"
            "## Ángulo diferenciador\n\n"
            "## Hooks propuestos\n\n"
            "## Puntos esenciales\n\n"
            "## Riesgos de desinformación\n\n"
            "## Investigación necesaria\n\n"
            "## Llamado a la acción\n\n"
            "## Oportunidad de monetización\n"
        )

    @staticmethod
    def _validate_request(
        request: ExpertCouncilRequest,
    ) -> None:
        """
        Valida que los campos esenciales contengan información.
        """

        required_fields = {
            "topic": request.topic,
            "platform": request.platform,
            "target_audience": request.target_audience,
            "objective": request.objective,
            "language": request.language,
            "duration": request.duration,
        }

        empty_fields = [
            field_name
            for field_name, value in required_fields.items()
            if not isinstance(value, str) or not value.strip()
        ]

        if empty_fields:
            fields = ", ".join(empty_fields)

            raise ValueError(
                "Los siguientes campos son obligatorios "
                f"y no pueden estar vacíos: {fields}"
            )