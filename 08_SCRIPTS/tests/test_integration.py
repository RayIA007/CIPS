"""
Knowledge Assets Enterprise Integration Tests
=============================================

Smoke tests para validar la integridad del núcleo de la librería.

Autor:
ConsejoIA_V5

Python:
3.14+

"""

import unittest

from knowledge_assets.models import KnowledgeAsset
from knowledge_assets.enums import (
    KnowledgeStatus,
    PublicationState,
    KnowledgeLifecycle,
    KnowledgeScope,
    KnowledgeFreshness,
)


class TestKnowledgeAsset(unittest.TestCase):

    def setUp(self):
        self.asset = KnowledgeAsset.new(
            "Activo de prueba"
        )

    # ---------------------------------------------------------

    def test_asset_creation(self):

        self.assertIsNotNone(self.asset)

        self.assertEqual(
            self.asset.title,
            "Activo de prueba"
        )

    # ---------------------------------------------------------

    def test_default_status(self):

        self.assertEqual(
            self.asset.status,
            KnowledgeStatus.DRAFT
        )

    # ---------------------------------------------------------

    def test_default_publication(self):

        self.assertEqual(
            self.asset.publication_state,
            PublicationState.NOT_SCHEDULED
        )

    # ---------------------------------------------------------

    def test_default_scope(self):

        self.assertEqual(
            self.asset.scope,
            KnowledgeScope.ORGANIZATION
        )

    # ---------------------------------------------------------

    def test_default_freshness(self):

        self.assertEqual(
            self.asset.freshness,
            KnowledgeFreshness.EVERGREEN
        )

    # ---------------------------------------------------------

    def test_default_lifecycle(self):

        self.assertEqual(
            self.asset.lifecycle,
            KnowledgeLifecycle.CREATED
        )

    # ---------------------------------------------------------

    def test_publish(self):

        self.asset.publish()

        self.assertEqual(
            self.asset.status,
            KnowledgeStatus.PUBLISHED
        )

        self.assertEqual(
            self.asset.publication_state,
            PublicationState.PUBLISHED
        )

    # ---------------------------------------------------------

    def test_unpublish(self):

        self.asset.publish()

        self.asset.unpublish()

        self.assertEqual(
            self.asset.status,
            KnowledgeStatus.DRAFT
        )

        self.assertEqual(
            self.asset.publication_state,
            PublicationState.NOT_SCHEDULED
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)