"""Public PM8 multi-asset resolution API."""

from .errors import (
    AssetDeliveryUnavailableError,
    AssetOutputValidationError,
    AssetProviderExecutionError,
    AssetProviderSelectionError,
    AssetReceiptIntegrityError,
    AssetResolutionError,
)
from .models import (
    ASSET_RESOLUTION_FILENAME,
    ASSET_RESOLUTION_SCHEMA_NAME,
    ASSET_RESOLUTION_SCHEMA_VERSION,
    AssetBinary,
    AssetResolutionBundle,
    AssetRole,
    CostStatus,
    MediaFamily,
    ResolutionStatus,
    ResolvedAsset,
    deterministic_record_id,
    deterministic_request_sha256,
    deterministic_resolution_id,
)
from .policy import AssetProviderPolicy, ProviderSelection
from .providers import BinaryAssetProviderAdapter, ExistingAssetProvider
from .resolver import AssetResolutionRun, ManifestAssetResolver
from .serialization import (
    asset_resolution_json_schema,
    deserialize_asset_resolution,
    serialize_asset_resolution,
)
from .wikimedia_commons import (
    WIKIMEDIA_COMMONS_API,
    WIKIMEDIA_PROVIDER_NAME,
    WikimediaCommonsProvider,
    image_dimensions,
)

__all__ = [
    "ASSET_RESOLUTION_FILENAME",
    "ASSET_RESOLUTION_SCHEMA_NAME",
    "ASSET_RESOLUTION_SCHEMA_VERSION",
    "AssetBinary",
    "AssetDeliveryUnavailableError",
    "AssetOutputValidationError",
    "AssetProviderExecutionError",
    "AssetProviderPolicy",
    "AssetProviderSelectionError",
    "AssetReceiptIntegrityError",
    "AssetResolutionBundle",
    "AssetResolutionError",
    "AssetResolutionRun",
    "AssetRole",
    "BinaryAssetProviderAdapter",
    "CostStatus",
    "ExistingAssetProvider",
    "ManifestAssetResolver",
    "MediaFamily",
    "ProviderSelection",
    "ResolutionStatus",
    "ResolvedAsset",
    "WIKIMEDIA_COMMONS_API",
    "WIKIMEDIA_PROVIDER_NAME",
    "WikimediaCommonsProvider",
    "asset_resolution_json_schema",
    "deserialize_asset_resolution",
    "deterministic_record_id",
    "deterministic_request_sha256",
    "deterministic_resolution_id",
    "image_dimensions",
    "serialize_asset_resolution",
]
