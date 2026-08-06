"""
ConsejoIA_V5
Research Stage

Genera el briefing inicial para el módulo de investigación.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class ResearchRequest:

    topic: str

    platform: str

    target_audience: str = "General"

    objective: str = "Educar"

    language: str = "Español"

    duration: str = "60 segundos"


class ResearchStage:

    def build_request(
        self,
        topic: str,
        platform: str,
    ) -> ResearchRequest:

        return ResearchRequest(
            topic=topic,
            platform=platform,
        )