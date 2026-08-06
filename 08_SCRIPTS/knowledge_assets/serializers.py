"""
knowledge_assets.serializers
=============================

Serialización JSON para KnowledgeAsset.

ConsejoIA_V5
"""

from __future__ import annotations

import json
from typing import Any

from knowledge_assets.models import KnowledgeAsset


class KnowledgeAssetSerializer:
    """Serializador JSON básico para KnowledgeAsset."""

    @staticmethod
    def to_dict(asset: KnowledgeAsset) -> dict[str, Any]:
        return {
            "id": str(asset.id),
            "title": asset.title,
            "knowledge_type": asset.knowledge_type.value,
            "status": asset.status.value,
            "lifecycle": asset.lifecycle.value,
            "scope": asset.scope.value,
            "freshness": asset.freshness.value,
            "publication_state": asset.publication_state.value,
        }

    @classmethod
    def to_json(
        cls,
        asset: KnowledgeAsset,
        *,
        indent: int = 2,
    ) -> str:
        return json.dumps(
            cls.to_dict(asset),
            ensure_ascii=False,
            indent=indent,
        )