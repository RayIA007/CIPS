"""
knowledge_assets.storage
========================

Persistencia simple para el MVP.

ConsejoIA_V5
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_assets.models import KnowledgeAsset
from knowledge_assets.serializers import KnowledgeAssetSerializer


class KnowledgeStorage:

    @staticmethod
    def save(asset: KnowledgeAsset, file_path: str | Path):

        file_path = Path(file_path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.write_text(
            KnowledgeAssetSerializer.to_json(asset),
            encoding="utf-8",
        )