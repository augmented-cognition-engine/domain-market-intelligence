from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from ace.core import AuthenticatedRuntimeContextV1Alpha1
from ace.intelligence import SourceAdapterCaptureRequestV1Alpha1
from ace_market_public_product_source import (
    ADAPTER_CAPABILITY,
    ADAPTER_CONTRACT,
    ADAPTER_IMPLEMENTATION_ID,
    ADAPTER_IMPLEMENTATION_VERSION,
    PUBLIC_PRODUCT_LOCATOR,
    PUBLIC_PRODUCT_SOURCE_TYPE,
    PublicProductRetrievalResult,
    PublicProductSourceAdapter,
    PublicProductSourceAdapterError,
)

ARTIFACT_DIGEST = "sha256:" + "a" * 64
URI = "https://public.example.test/products/edge-x1"
STARTED = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


class _InjectedTransport:
    def __init__(self, result: PublicProductRetrievalResult) -> None:
        self.result = result
        self.calls = 0
        self.requests = []

    async def retrieve(self, request):
        self.calls += 1
        self.requests.append(request)
        return self.result


def _result(**changes) -> PublicProductRetrievalResult:
    base = PublicProductRetrievalResult(
        source_type_ref=PUBLIC_PRODUCT_SOURCE_TYPE,
        requested_uri=URI,
        effective_uri=URI,
        status_code=200,
        media_type="application/json",
        response_body=(
            '{"product_name":"Edge X1","listed_price":"1080.00","currency":"USD"}'
        ),
        redirect_chain=(),
        resolved_ip_addresses=("1.1.1.1",),
        connected_ip_addresses=("1.1.1.1",),
        dns_rebinding_protection_applied=True,
        credentials_used=False,
        locator=PUBLIC_PRODUCT_LOCATOR,
        observed_at=STARTED + timedelta(seconds=1),
        captured_at=STARTED + timedelta(seconds=2),
    )
    return replace(base, **changes)


def _adapter_and_request(**result_changes):
    transport = _InjectedTransport(_result(**result_changes))
    adapter = PublicProductSourceAdapter(
        transport=transport,
        artifact_digest=ARTIFACT_DIGEST,
    )
    context = AuthenticatedRuntimeContextV1Alpha1(
        product_id="product:market-northstar",
        actor_ref="actor:market-analyst",
        authentication_receipt_ref="authentication_receipt:p1c2",
        authentication_receipt_digest="sha256:" + "b" * 64,
        authenticated_at=STARTED - timedelta(minutes=1),
        expires_at=STARTED + timedelta(minutes=10),
    )
    request = SourceAdapterCaptureRequestV1Alpha1(
        product_id=context.product_id,
        authenticated_context=context,
        use_subject_ref="live_source_ingress_request:fixture",
        use_subject_digest="sha256:" + "c" * 64,
        source_definition_ref="source_definition:public-northstar-edge-x1",
        source_type_ref=PUBLIC_PRODUCT_SOURCE_TYPE,
        requested_uri=URI,
        adapter_artifact=adapter.artifact_identity,
        configuration_ref="config:public-northstar-edge-x1",
        configuration_digest="sha256:" + "d" * 64,
        started_at=STARTED,
        max_payload_chars=4_096,
    )
    return adapter, transport, request


@pytest.mark.asyncio
async def test_adapter_exposes_exact_identity_and_canonical_three_field_capture() -> (
    None
):
    adapter, transport, request = _adapter_and_request()

    capture = await adapter.capture(request)

    assert adapter.artifact_identity.model_dump(mode="json") == {
        "contract_version": "ace.core.capability-artifact-identity/v1alpha1",
        "capability": ADAPTER_CAPABILITY,
        "contract": ADAPTER_CONTRACT,
        "implementation_id": ADAPTER_IMPLEMENTATION_ID,
        "implementation_version": ADAPTER_IMPLEMENTATION_VERSION,
        "artifact_digest": ARTIFACT_DIGEST,
    }
    assert capture.captured_payload_json == (
        '{"currency":"USD","listed_price":"1080.00","product_name":"Edge X1"}'
    )
    assert capture.requested_uri == capture.effective_uri == URI
    assert capture.redirect_chain == ()
    assert capture.resolved_ip_addresses == ("1.1.1.1",)
    assert capture.dns_rebinding_protection_applied is True
    assert capture.locator == PUBLIC_PRODUCT_LOCATOR
    assert adapter.capture_calls == transport.calls == 1
    assert transport.requests[0].credentials_allowed is False
    assert transport.requests[0].redirects_allowed is False
    assert transport.requests[0].public_network_only is True
    assert transport.requests[0].dns_rebinding_protection_required is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"status_code": 404}, "HTTP 200"),
        ({"status_code": True}, "exact integer type"),
        ({"media_type": "text/html"}, "application/json"),
        ({"media_type": 1}, "exact string types"),
        ({"source_type_ref": "other_source"}, "source type"),
        ({"source_type_ref": None}, "exact string types"),
        ({"effective_uri": "https://public.example.test/products/other"}, "URI scope"),
        ({"effective_uri": 1}, "exact string types"),
        ({"redirect_chain": (URI,)}, "exactly an empty tuple"),
        ({"redirect_chain": []}, "exactly an empty tuple"),
        ({"redirect_chain": None}, "exactly an empty tuple"),
        ({"credentials_used": True}, "exact false credentials"),
        ({"credentials_used": 0}, "exact false credentials"),
        ({"dns_rebinding_protection_applied": False}, "exact true DNS-rebinding"),
        ({"dns_rebinding_protection_applied": 1}, "exact true DNS-rebinding"),
        ({"resolved_ip_addresses": ("127.0.0.1",)}, "globally routable"),
        ({"resolved_ip_addresses": ["1.1.1.1"]}, "attest 1..32"),
        ({"resolved_ip_addresses": "1.1.1.1"}, "attest 1..32"),
        ({"connected_ip_addresses": ["1.1.1.1"]}, "attest 1..32"),
        ({"connected_ip_addresses": ("8.8.8.8",)}, "exactly attested"),
        ({"response_body": 1}, "exact string types"),
        ({"locator": 1}, "exact string types"),
        ({"locator": "json-pointer:/product_name"}, "exact extraction locator"),
        ({"observed_at": "2026-08-06T12:00:01Z"}, "timezone-aware datetime"),
        ({"response_body": "not-json"}, "unambiguous bounded JSON"),
        (
            {
                "response_body": (
                    '{"product_name":"Edge X1","product_name":"Other",'
                    '"listed_price":"1080.00","currency":"USD"}'
                )
            },
            "duplicate",
        ),
        (
            {
                "response_body": (
                    '{"product_name":"Edge X1","listed_price":1080.0,"currency":"USD"}'
                )
            },
            "listed_price",
        ),
        (
            {
                "response_body": (
                    '{"product_name":"Edge X1","listed_price":"1080.00",'
                    '"currency":"USD","claim":"cheap"}'
                )
            },
            "exactly the canonical three fields",
        ),
        (
            {
                "response_body": (
                    '{"product_name":"Edge X1","listed_price":"1e3","currency":"USD"}'
                )
            },
            "decimal text",
        ),
        (
            {
                "response_body": (
                    '{"product_name":"Edge X1","listed_price":"1080.00","currency":"usd"}'
                )
            },
            "uppercase ASCII",
        ),
        ({"response_body": "x" * 4_097}, "character bound"),
    ],
)
async def test_adapter_fails_closed_for_untrusted_retrieval_results(
    changes: dict[str, object],
    message: str,
) -> None:
    adapter, _, request = _adapter_and_request(**changes)

    with pytest.raises(PublicProductSourceAdapterError, match=message):
        await adapter.capture(request)


@pytest.mark.asyncio
async def test_adapter_rejects_request_for_different_artifact_before_transport() -> (
    None
):
    adapter, transport, request = _adapter_and_request()
    forged = request.model_copy(
        update={
            "adapter_artifact": request.adapter_artifact.model_copy(
                update={"artifact_digest": "sha256:" + "e" * 64}
            )
        }
    )

    with pytest.raises(PublicProductSourceAdapterError, match="revalidation"):
        await adapter.capture(forged)

    assert transport.calls == 0
