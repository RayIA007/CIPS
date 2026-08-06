import unittest

from research_stage import ResearchStage


class TestResearchStage(unittest.TestCase):

    def test_request(self):

        stage = ResearchStage()

        request = stage.build_request(
            topic="Cómo aprender inglés",
            platform="youtube",
        )

        self.assertEqual(
            request.topic,
            "Cómo aprender inglés"
        )

        self.assertEqual(
            request.platform,
            "youtube"
        )

        self.assertEqual(
            request.objective,
            "Educar"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)