"""
knowledge_assets.factory
========================

Factory para crear activos de conocimiento.

ConsejoIA_V5
"""

from knowledge_assets.models import KnowledgeAsset
from knowledge_assets.enums import KnowledgeType


class KnowledgeFactory:
    """Factory principal."""

    @staticmethod
    def create_document(title: str):

        return KnowledgeAsset.new(
            title=title,
            knowledge_type=KnowledgeType.DOCUMENT,
        )

    @staticmethod
    def create_prompt(title: str):

        return KnowledgeAsset.new(
            title=title,
            knowledge_type=KnowledgeType.TEMPLATE,
        )

    @staticmethod
    def create_template(title: str):

        return KnowledgeAsset.new(
            title=title,
            knowledge_type=KnowledgeType.TEMPLATE,
        )

    @staticmethod
    def create_strategy(title: str):

        return KnowledgeAsset.new(
            title=title,
            knowledge_type=KnowledgeType.STRATEGY,
        )

    @staticmethod
    def create_workflow(title: str):

        return KnowledgeAsset.new(
            title=title,
            knowledge_type=KnowledgeType.WORKFLOW,
        )