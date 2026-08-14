from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from ace.application import IntelligenceBuildHostServices
from ace.application.intelligence_build_execution import REQUIRED_INTELLIGENCE_BUILD_EFFECTS
from ace.core import AuthenticatedRuntimeContextV1Alpha1, canonical_hash
from ace.intelligence import (
    ActivationRevisionReferenceV1Alpha1,
    CanonicalJsonValueV1Alpha1,
    EntitySnapshotV1Alpha1,
    IntelligenceResourceMode,
    ResolvedSubjectBindingV1Alpha1,
)
from ace_market_builder import (
    MARKET_INTELLIGENCE_PROFILE_ID,
    MarketIntelligenceBuilderExecutor,
    MarketIntelligenceBuilderExecutorError,
    load_recorded_market_source_materials,
)
import ace_market_builder.executor as executor_module

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 14, 18, tzinfo=UTC)
PRODUCT = "product:market-v1"
ACTOR = "principal:owner"
BUILD_ID = "intelligence_build:market-v1"
BUILD_DIGEST = "sha256:" + "7" * 64
ACTIVATION = ActivationRevisionReferenceV1Alpha1(
    product_id=PRODUCT,
    activation_key="market_intelligence_command_center",
    activation_id=("domain_activation:" + canonical_hash([PRODUCT, "market_intelligence_command_center"])[:32]),
    revision=1,
    revision_id="activation_revision:" + "6" * 32,
    revision_digest="sha256:" + "6" * 64,
)


class RecordedPort:
    def __init__(self) -> None:
        self.materials = None

    def bind_subject(self, *, subject_binding_id, entity_type_id, entity_ref):
        return ResolvedSubjectBindingV1Alpha1(
            product_id=PRODUCT,
            mode=IntelligenceResourceMode.PREPARED,
            activation_revision=ACTIVATION,
            subject_binding_id=subject_binding_id,
            entity_type_id=entity_type_id,
            entity_ref=entity_ref,
        )

    async def admit(self, materials):
        self.materials = tuple(materials)
        entities = tuple(
            EntitySnapshotV1Alpha1(
                product_id=PRODUCT,
                mode=IntelligenceResourceMode.PREPARED,
                activation_revision=ACTIVATION,
                as_of=item.source_published_at,
                entity_ref=item.subject_binding.entity_ref,
                entity_type_ref=item.subject_binding.entity_type_id,
                attributes=CanonicalJsonValueV1Alpha1(value_json=item.captured_payload_json),
                projected_at=NOW,
                confidence=1.0,
            )
            for item in materials
        )
        return SimpleNamespace(entity_snapshots=entities)


class DerivationPort:
    def __init__(self) -> None:
        self.request = None

    async def derive(self, request):
        self.request = request
        attention = SimpleNamespace(
            receipt_id="attention_receipt:market-v1",
            receipt_digest="sha256:" + "4" * 64,
        )
        return SimpleNamespace(
            material_shift=True,
            shift=object(),
            signal=object(),
            admission=SimpleNamespace(attention_receipt=attention),
        )


class FirstBriefPort:
    def __init__(self) -> None:
        self.request = None

    async def create_first_brief(self, request):
        self.request = request
        return SimpleNamespace(replayed=False)


class ResourcePort:
    def __init__(self) -> None:
        self.request = None

    async def query(self, **request):
        self.request = request
        return SimpleNamespace(product_id=PRODUCT, items=("cited-first-brief",))


def _build(*, source_group_ids=("competitor_public_evidence",), effects=REQUIRED_INTELLIGENCE_BUILD_EFFECTS):
    context = AuthenticatedRuntimeContextV1Alpha1(
        product_id=PRODUCT,
        actor_ref=ACTOR,
        authentication_receipt_ref="task_authentication:market-v1",
        authentication_receipt_digest="sha256:" + "8" * 64,
        authenticated_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )
    request = SimpleNamespace(
        profile_id=MARKET_INTELLIGENCE_PROFILE_ID,
        approved_effects=effects,
        source_group_ids=source_group_ids,
    )
    authority = SimpleNamespace(
        authenticated_context=context,
        use_subject_ref=BUILD_ID,
        use_subject_digest=BUILD_DIGEST,
        evaluated_at=NOW,
    )
    return SimpleNamespace(
        request=request,
        authority_use=authority,
        build_id=BUILD_ID,
        request_digest=BUILD_DIGEST,
        product_id=PRODUCT,
        actor_ref=ACTOR,
    )


def _host():
    recorded = RecordedPort()
    derivations = DerivationPort()
    first_brief = FirstBriefPort()
    resources = ResourcePort()
    host = IntelligenceBuildHostServices(
        records=SimpleNamespace(),
        resources=resources,
        activation_authority=SimpleNamespace(),
        recorded_sources=recorded,
        prepared_derivations=derivations,
        first_brief=first_brief,
    )
    return host, recorded, derivations, first_brief, resources


@pytest.fixture(autouse=True)
def _source_checkout(monkeypatch):
    monkeypatch.setattr(executor_module, "_market_domain_file", lambda relative: ROOT / relative)


@pytest.mark.asyncio
async def test_executor_runs_exact_recorded_price_move_to_cited_first_brief() -> None:
    build = _build()
    host, recorded, derivations, first_brief, resources = _host()

    page = await MarketIntelligenceBuilderExecutor().start(build, host)

    assert page.product_id == PRODUCT
    assert len(recorded.materials) == 2
    assert [item.captured_payload_digest for item in recorded.materials] == [
        "sha256:44caaf4fd6e9483c5dcdc853b8267dbc14f0e64676600354424ad54c1d8ae2c4",
        "sha256:40a75b55a2571fac73afc0aebe90545222183c43d81527184f1909210663b892",
    ]
    assert derivations.request.detector_id == "product_price_move"
    assert derivations.request.baseline_snapshot.as_of < derivations.request.current_snapshot.as_of
    assert first_brief.request.build_id == BUILD_ID
    assert first_brief.request.derivation_key == f"prepared_derivation:{BUILD_ID}"
    assert first_brief.request.attention_receipt_id == "attention_receipt:market-v1"
    assert resources.request["page_size"] == 200
    assert any(kind.value == "source_health" for kind in resources.request["resource_kinds"])
    assert any(kind.value == "brief" for kind in resources.request["resource_kinds"])


def test_recorded_materials_preserve_exact_reviewed_publications() -> None:
    materials = load_recorded_market_source_materials(RecordedPort())

    assert [item.source_uri for item in materials] == [
        "https://openai.com/index/gpt-5-6/",
        "https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/",
    ]
    assert [item.source_published_at.date().isoformat() for item in materials] == ["2026-07-09", "2026-07-30"]


@pytest.mark.asyncio
async def test_executor_rejects_unimplemented_sources_before_admission() -> None:
    build = _build(source_group_ids=("owned_customer_data",))
    host, recorded, _, _, _ = _host()

    with pytest.raises(MarketIntelligenceBuilderExecutorError, match="supports only competitor_public_evidence"):
        await MarketIntelligenceBuilderExecutor().start(build, host)
    assert recorded.materials is None


@pytest.mark.asyncio
async def test_executor_requires_all_three_core_ports() -> None:
    build = _build()
    host, recorded, derivations, _, resources = _host()
    incomplete = IntelligenceBuildHostServices(
        records=host.records,
        resources=resources,
        activation_authority=host.activation_authority,
        recorded_sources=recorded,
        prepared_derivations=derivations,
        first_brief=None,
    )

    with pytest.raises(MarketIntelligenceBuilderExecutorError, match="first-Brief host ports"):
        await MarketIntelligenceBuilderExecutor().start(build, incomplete)
    assert recorded.materials is None
