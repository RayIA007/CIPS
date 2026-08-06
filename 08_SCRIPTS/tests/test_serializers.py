import json
import unittest

from knowledge_assets.factory import KnowledgeFactory
from knowledge_assets.serializers import KnowledgeAssetSerializer


class TestKnowledgeAssetSerializer(unittest.TestCase):

    def setUp(self):
        self.asset = KnowledgeFactory.create_document(
            "Documento serializable"
        )

    def test_to_dict(self):

        data = KnowledgeAssetSerializer.to_dict(self.asset)

        self.assertEqual(
            data["title"],
            "Documento serializable"
        )

        self.assertEqual(
            data["knowledge_type"],
            "document"
        )

        self.assertEqual(
            data["status"],
            "draft"
        )

        self.assertEqual(
            data["publication_state"],
            "not_scheduled"
        )

    def test_to_json(self):

        json_text = KnowledgeAssetSerializer.to_json(self.asset)

        data = json.loads(json_text)

        self.assertEqual(
            data["title"],
            "Documento serializable"
        )

        self.assertEqual(
            data["knowledge_type"],
            "document"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)