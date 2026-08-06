import json
import unittest
from pathlib import Path

from knowledge_assets.factory import KnowledgeFactory
from knowledge_assets.storage import KnowledgeStorage


class TestKnowledgeStorage(unittest.TestCase):

    def test_save(self):

        asset = KnowledgeFactory.create_document(
            "Documento Persistente"
        )

        file = Path("tests/tmp_asset.json")

        KnowledgeStorage.save(asset, file)

        self.assertTrue(file.exists())

        data = json.loads(
            file.read_text(encoding="utf-8")
        )

        self.assertEqual(
            data["title"],
            "Documento Persistente"
        )

        file.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)