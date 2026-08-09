"""Credential-free, transport-injected adapter for one exact public-product shape."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ace.core import (
    CapabilityArtifactIdentityV1Alpha1,
    canonical_json,
    validate_exact_https_uri,
    validate_public_ip_literal,
)
from ace.intelligence import (
    CapturedSourceMaterialV1Alpha1,
    SourceAdapterCaptureRequestV1Alpha1,
)

ADAPTER_CAPABILITY = "source_snapshot"
ADAPTER_CONTRACT = "ace.source.snapshot/v1alpha1"
ADAPTER_IMPLEMENTATION_ID = "market_public_product_source"
ADAPTER_IMPLEMENTATION_VERSION = "0.1.1"
PUBLIC_PRODUCT_SOURCE_TYPE = "public_product_page"
PUBLIC_PRODUCT_LOCATOR = "json-pointer:/listed_price"

MAX_RESPONSE_BODY_CHARS = 16_384
MAX_PRODUCT_NAME_CHARS = 256
MAX_PRICE_TEXT_CHARS = 64
_DECIMAL_TEXT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")


class PublicProductSourceAdapterError(ValueError):
    """The injected retrieval result failed the adapter's closed contract."""


@dataclass(frozen=True, slots=True)
class PublicProductRetrievalRequest:
    """Bounded, credential-free request presented to a reviewed injected transport."""

    source_type_ref: str
    requested_uri: str
    max_response_chars: int
    credentials_allowed: bool = False
    redirects_allowed: bool = False
    public_network_only: bool = True
    dns_rebinding_protection_required: bool = True


@dataclass(frozen=True, slots=True)
class PublicProductRetrievalResult:
    """Transport attestation plus untrusted response body; validation occurs in the adapter."""

    source_type_ref: str
    requested_uri: str
    effective_uri: str
    status_code: int
    media_type: str
    response_body: str
    redirect_chain: tuple[str, ...]
    resolved_ip_addresses: tuple[str, ...]
    connected_ip_addresses: tuple[str, ...]
    dns_rebinding_protection_applied: bool
    credentials_used: bool
    locator: str
    observed_at: datetime
    captured_at: datetime
    source_published_at: datetime | None = None
    event_effective_at: datetime | None = None


class PublicProductTransport(Protocol):
    """Host-supplied transport; this package deliberately provides no implementation."""

    async def retrieve(
        self,
        request: PublicProductRetrievalRequest,
    ) -> PublicProductRetrievalResult: ...


def _fail(message: str) -> PublicProductSourceAdapterError:
    return PublicProductSourceAdapterError(message)


def _aware_utc(value: object, *, name: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise _fail(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _fail(f"duplicate public-product field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _fail(f"non-finite JSON token is not allowed: {value}")


def _validate_scalar_text(
    value: object, *, name: str, minimum: int, maximum: int
) -> str:
    if type(value) is not str or not minimum <= len(value) <= maximum:
        raise _fail(f"{name} must be text with length {minimum}..{maximum}")
    if any(
        ord(character) < 0x20
        or ord(character) == 0x7F
        or 0xD800 <= ord(character) <= 0xDFFF
        for character in value
    ):
        raise _fail(f"{name} contains controls, DEL, or a lone surrogate")
    return value


def _canonical_product_payload(response_body: object, *, max_chars: int) -> str:
    if type(response_body) is not str:
        raise _fail("public-product response body must be text")
    if not response_body or len(response_body) > max_chars:
        raise _fail("public-product response body exceeded its exact character bound")
    try:
        payload = json.loads(
            response_body,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except PublicProductSourceAdapterError:
        raise
    except (TypeError, ValueError, RecursionError) as exc:
        raise _fail(
            "public-product response body is not unambiguous bounded JSON"
        ) from exc
    if type(payload) is not dict:
        raise _fail("public-product response must be one JSON object")
    required = {"product_name", "listed_price", "currency"}
    if set(payload) != required:
        raise _fail(
            "public-product response must contain exactly the canonical three fields"
        )

    product_name = _validate_scalar_text(
        payload["product_name"],
        name="product_name",
        minimum=1,
        maximum=MAX_PRODUCT_NAME_CHARS,
    )
    listed_price = _validate_scalar_text(
        payload["listed_price"],
        name="listed_price",
        minimum=1,
        maximum=MAX_PRICE_TEXT_CHARS,
    )
    if _DECIMAL_TEXT.fullmatch(listed_price) is None:
        raise _fail("listed_price must remain faithful bounded decimal text")
    currency = _validate_scalar_text(
        payload["currency"],
        name="currency",
        minimum=3,
        maximum=3,
    )
    if not currency.isascii() or not currency.isupper() or not currency.isalpha():
        raise _fail("currency must be exactly three uppercase ASCII letters")
    return canonical_json(
        {
            "product_name": product_name,
            "listed_price": listed_price,
            "currency": currency,
        }
    )


def _validated_addresses(
    values: object,
    *,
    name: str,
) -> tuple[str, ...]:
    if type(values) is not tuple or not 1 <= len(values) <= 32:
        raise _fail(f"{name} must attest 1..32 addresses")
    try:
        normalized = tuple(
            validate_public_ip_literal(value, name=name)
            for value in values
            if type(value) is str
        )
    except ValueError as exc:
        raise _fail(
            f"{name} must contain only globally routable unicast literals"
        ) from exc
    if len(normalized) != len(values) or len(set(normalized)) != len(normalized):
        raise _fail(f"{name} must contain unique exact IP literals")
    return tuple(sorted(normalized))


class PublicProductSourceAdapter:
    """Validate one injected retrieval and return inert canonical source material."""

    def __init__(
        self, *, transport: PublicProductTransport, artifact_digest: str
    ) -> None:
        self._transport = transport
        self.artifact_identity = CapabilityArtifactIdentityV1Alpha1(
            capability=ADAPTER_CAPABILITY,
            contract=ADAPTER_CONTRACT,
            implementation_id=ADAPTER_IMPLEMENTATION_ID,
            implementation_version=ADAPTER_IMPLEMENTATION_VERSION,
            artifact_digest=artifact_digest,
        )
        self.capture_calls = 0

    async def capture(
        self,
        request: SourceAdapterCaptureRequestV1Alpha1,
    ) -> CapturedSourceMaterialV1Alpha1:
        try:
            validated = SourceAdapterCaptureRequestV1Alpha1.model_validate(
                request.model_dump(mode="python")
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise _fail(
                "source-adapter request failed exact public-contract revalidation"
            ) from exc
        if validated.adapter_artifact != self.artifact_identity:
            raise _fail("source-adapter request names a different installed artifact")
        if validated.source_type_ref != PUBLIC_PRODUCT_SOURCE_TYPE:
            raise _fail("source-adapter request names an unsupported source type")
        validate_exact_https_uri(validated.requested_uri, name="requested_uri")

        transport_request = PublicProductRetrievalRequest(
            source_type_ref=validated.source_type_ref,
            requested_uri=validated.requested_uri,
            max_response_chars=min(
                validated.max_payload_chars, MAX_RESPONSE_BODY_CHARS
            ),
        )
        self.capture_calls += 1
        result = await self._transport.retrieve(transport_request)
        if type(result) is not PublicProductRetrievalResult:
            raise _fail("transport returned an unsupported retrieval-result type")
        if any(
            type(value) is not str
            for value in (
                result.source_type_ref,
                result.requested_uri,
                result.effective_uri,
                result.media_type,
                result.response_body,
                result.locator,
            )
        ):
            raise _fail(
                "retrieval result scalar text fields must use exact string types"
            )
        if type(result.status_code) is not int:
            raise _fail("retrieval result status_code must use the exact integer type")
        if type(result.redirect_chain) is not tuple or result.redirect_chain != ():
            raise _fail(
                "retrieval result redirect_chain must be exactly an empty tuple"
            )
        if (
            type(result.credentials_used) is not bool
            or result.credentials_used is not False
        ):
            raise _fail("retrieval result must attest exact false credentials_used")
        if (
            type(result.dns_rebinding_protection_applied) is not bool
            or result.dns_rebinding_protection_applied is not True
        ):
            raise _fail(
                "retrieval result must attest exact true DNS-rebinding protection"
            )
        if (
            result.source_type_ref != validated.source_type_ref
            or result.requested_uri != validated.requested_uri
            or result.effective_uri != validated.requested_uri
        ):
            raise _fail("retrieval result crossed source type or exact URI scope")
        if result.locator != PUBLIC_PRODUCT_LOCATOR:
            raise _fail("retrieval result does not bind the exact extraction locator")
        if result.status_code != 200 or result.media_type != "application/json":
            raise _fail(
                "retrieval result must be exact HTTP 200 application/json material"
            )

        resolved = _validated_addresses(
            result.resolved_ip_addresses,
            name="resolved_ip_addresses",
        )
        connected = _validated_addresses(
            result.connected_ip_addresses,
            name="connected_ip_addresses",
        )
        if connected != resolved:
            raise _fail(
                "every resolved and connected address must remain exactly attested"
            )

        observed_at = _aware_utc(result.observed_at, name="observed_at")
        captured_at = _aware_utc(result.captured_at, name="captured_at")
        source_published_at = (
            None
            if result.source_published_at is None
            else _aware_utc(result.source_published_at, name="source_published_at")
        )
        event_effective_at = (
            None
            if result.event_effective_at is None
            else _aware_utc(result.event_effective_at, name="event_effective_at")
        )
        if observed_at < validated.started_at or captured_at < observed_at:
            raise _fail(
                "retrieval observation/capture times fall outside the exact operation"
            )
        payload_json = _canonical_product_payload(
            result.response_body,
            max_chars=transport_request.max_response_chars,
        )
        payload_digest = (
            "sha256:" + hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        )
        return CapturedSourceMaterialV1Alpha1(
            capture_request_ref=str(validated.request_id),
            capture_request_digest=str(validated.request_digest),
            source_type_ref=validated.source_type_ref,
            requested_uri=validated.requested_uri,
            effective_uri=result.effective_uri,
            redirect_chain=(),
            resolved_ip_addresses=resolved,
            dns_rebinding_protection_applied=True,
            captured_payload_json=payload_json,
            captured_payload_digest=payload_digest,
            locator=PUBLIC_PRODUCT_LOCATOR,
            source_published_at=source_published_at,
            event_effective_at=event_effective_at,
            observed_at=observed_at,
            captured_at=captured_at,
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
