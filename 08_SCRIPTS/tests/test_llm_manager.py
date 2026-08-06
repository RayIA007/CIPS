import unittest

from llm_manager import LLMManager


class TestLLMManager(unittest.TestCase):

    def test_manager_creation(self):

        manager = LLMManager()

        self.assertEqual(
            manager.providers(),
            [],
        )

    def test_empty_default(self):

        manager = LLMManager()

        with self.assertRaises(
            RuntimeError
        ):

            manager.get_default()


if __name__ == "__main__":

    unittest.main(verbosity=2)