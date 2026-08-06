import unittest
from pathlib import Path

from content_pipeline import ContentPipeline


class TestContentPipeline(unittest.TestCase):

    def test_run(self):

        pipeline = ContentPipeline()

        project = pipeline.run(
            topic="Video de prueba",
            platform="youtube",
        )

        self.assertTrue(project.exists())

        self.assertTrue(
            (project / "idea.md").exists()
        )

        self.assertTrue(
            (project / "script.md").exists()
        )

        self.assertTrue(
            (project / "storyboard.md").exists()
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)