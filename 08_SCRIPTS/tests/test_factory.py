import unittest

from knowledge_assets.factory import KnowledgeFactory
from knowledge_assets.enums import KnowledgeType


class TestFactory(unittest.TestCase):

    def test_create_document(self):

        asset = KnowledgeFactory.create_document("Documento")

        self.assertEqual(
            asset.knowledge_type,
            KnowledgeType.DOCUMENT
        )

    def test_create_prompt(self):

        asset = KnowledgeFactory.create_prompt("Prompt")

        self.assertEqual(
            asset.knowledge_type,
            KnowledgeType.TEMPLATE
        )

    def test_create_template(self):

        asset = KnowledgeFactory.create_template("Template")

        self.assertEqual(
            asset.knowledge_type,
            KnowledgeType.TEMPLATE
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)