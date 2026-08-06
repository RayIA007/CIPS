import unittest

from llm_provider import ProviderResult
from mock_provider import MockProvider
from runtime_models import LLMResponse


class TestMockProvider(unittest.TestCase):

    def setUp(self) -> None:
        self.provider = MockProvider()

    def test_generate_returns_successful_result(self) -> None:
        result = self.provider.generate(
            prompt="Genera un briefing sobre inteligencia artificial.",
        )

        self.assertIsInstance(
            result,
            ProviderResult,
        )

        self.assertTrue(
            result.success,
        )

        self.assertIsInstance(
            result.response,
            LLMResponse,
        )

    def test_generated_response_contains_provider_data(self) -> None:
        result = self.provider.generate(
            prompt="Hola mundo",
        )

        self.assertIsNotNone(
            result.response,
        )

        self.assertIn(
            "MockProvider",
            result.response.content,
        )

        self.assertEqual(
            result.response.model,
            "mock-cips-v1",
        )

        self.assertEqual(
            result.response.metadata["provider"],
            "mock",
        )

        self.assertTrue(
            result.response.metadata["simulated"],
        )

    def test_empty_prompt_returns_failure(self) -> None:
        result = self.provider.generate(
            prompt="",
        )

        self.assertFalse(
            result.success,
        )

        self.assertIsNone(
            result.response,
        )

        self.assertTrue(
            result.errors,
        )

        self.assertIn(
            "El prompt está vacío.",
            result.errors,
        )

    def test_metadata_is_preserved(self) -> None:
        result = self.provider.generate(
            prompt="Contenido de prueba",
            metadata={
                "project_id": "PROJECT-001",
                "stage": "research",
            },
        )

        self.assertTrue(
            result.success,
        )

        self.assertEqual(
            result.metadata["project_id"],
            "PROJECT-001",
        )

        self.assertEqual(
            result.metadata["stage"],
            "research",
        )

    def test_provider_information(self) -> None:
        information = self.provider.get_provider_info()

        self.assertEqual(
            information["provider"],
            "mock",
        )

        self.assertEqual(
            information["model"],
            "mock-cips-v1",
        )

    def test_health_check(self) -> None:
        self.assertTrue(
            self.provider.health_check(),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)