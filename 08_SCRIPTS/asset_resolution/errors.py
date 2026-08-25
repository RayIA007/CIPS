"""Explicit PM8 failure categories."""


class AssetResolutionError(RuntimeError):
    """Base error for provider-neutral asset resolution."""


class AssetProviderSelectionError(AssetResolutionError):
    """No enabled provider satisfies capability, cost and quality policy."""


class AssetProviderExecutionError(AssetResolutionError):
    """The selected provider failed or returned an unsuccessful F4 result."""


class AssetOutputValidationError(AssetResolutionError):
    """The selected provider returned an invalid or incompatible asset."""


class AssetReceiptIntegrityError(AssetResolutionError):
    """A persisted PM8 receipt or referenced F3 artifact is inconsistent."""


class AssetDeliveryUnavailableError(AssetResolutionError):
    """A resolved local asset has no HTTPS delivery location for a remote target."""


__all__ = [
    "AssetDeliveryUnavailableError",
    "AssetOutputValidationError",
    "AssetProviderExecutionError",
    "AssetProviderSelectionError",
    "AssetReceiptIntegrityError",
    "AssetResolutionError",
]
