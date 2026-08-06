import unittest

from script_stage import (
    ScriptStage,
    ScriptRequest,
)


class TestScriptStage(unittest.TestCase):

    def test_script_generation(self):

        stage = ScriptStage()

        request = ScriptRequest(
            topic="Cómo aprender inglés",
            platform="youtube",
            duration="60 segundos",
            objective="Educar",
        )

        script = stage.build_script(request)

        self.assertIn(
            "Cómo aprender inglés",
            script
        )

        self.assertIn(
            "Hook",
            script
        )

        self.assertIn(
            "Llamado a la acción",
            script
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)