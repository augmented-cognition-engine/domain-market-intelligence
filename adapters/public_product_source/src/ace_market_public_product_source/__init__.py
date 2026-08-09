"""Public API for the separately distributed Market public-product adapter."""

from ace_market_public_product_source.adapter import (
    ADAPTER_CAPABILITY,
    ADAPTER_CONTRACT,
    ADAPTER_IMPLEMENTATION_ID,
    ADAPTER_IMPLEMENTATION_VERSION,
    PUBLIC_PRODUCT_LOCATOR,
    PUBLIC_PRODUCT_SOURCE_TYPE,
    PublicProductRetrievalRequest,
    PublicProductRetrievalResult,
    PublicProductSourceAdapter,
    PublicProductSourceAdapterError,
    PublicProductTransport,
)

__all__ = [
    "ADAPTER_CAPABILITY",
    "ADAPTER_CONTRACT",
    "ADAPTER_IMPLEMENTATION_ID",
    "ADAPTER_IMPLEMENTATION_VERSION",
    "PUBLIC_PRODUCT_LOCATOR",
    "PUBLIC_PRODUCT_SOURCE_TYPE",
    "PublicProductRetrievalRequest",
    "PublicProductRetrievalResult",
    "PublicProductSourceAdapter",
    "PublicProductSourceAdapterError",
    "PublicProductTransport",
]
