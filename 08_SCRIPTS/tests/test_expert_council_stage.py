import unittest

from expert_council_stage import (
    ExpertCouncilRequest,
    ExpertCouncilStage,
)


class TestExpertCouncilStage(unittest.TestCase):

    def setUp(self) -> None:
        self.stage = ExpertCouncilStage()

        self.request = ExpertCouncilRequest(
            topic="Cómo utilizar inteligencia artificial en un negocio",
            platform="youtube",
            target_audience="Emprendedores principiantes",
            objective="Educar",
            language="Español",
            duration="60 segundos",
        )

    def test_build_prompt_contains_project_data(self) -> None:
        prompt = self.stage.build_prompt(self.request)

        self.assertIn(
            "Cómo utilizar inteligencia artificial en un negocio",
            prompt,
        )

        self.assertIn(
            "Emprendedores principiantes",
            prompt,
        )

        self.assertIn(
            "youtube",
            prompt,
        )

        self.assertIn(
            "60 segundos",
            prompt,
        )

    def test_build_prompt_contains_expert_roles(self) -> None:
        prompt = self.stage.build_prompt(self.request)

        self.assertIn(
            "Estratega senior de contenido digital",
            prompt,
        )

        self.assertIn(
            "Investigador y verificador de información",
            prompt,
        )

        self.assertIn(
            "Especialista en marketing y monetización digital",
            prompt,
        )

    def test_build_prompt_contains_verification_rules(self) -> None:
        prompt = self.stage.build_prompt(self.request)

        self.assertIn(
            "No inventes datos",
            prompt,
        )

        self.assertIn(
            "Investigación necesaria",
            prompt,
        )

        self.assertIn(
            "Riesgos de desinformación",
            prompt,
        )

    def test_empty_topic_raises_value_error(self) -> None:
        invalid_request = ExpertCouncilRequest(
            topic="",
            platform="youtube",
            target_audience="Emprendedores",
            objective="Educar",
            language="Español",
            duration="60 segundos",
        )

        with self.assertRaises(ValueError):
            self.stage.build_prompt(invalid_request)


if __name__ == "__main__":
    unittest.main(verbosity=2)