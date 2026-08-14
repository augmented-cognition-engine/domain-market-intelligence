from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ace.application import (
    REQUIRED_INTELLIGENCE_BUILD_EFFECTS,
    IntelligenceBuildPlanRequestV1Alpha2,
    IntelligenceBuildPlanV1Alpha3,
    validate_intelligence_build_planner_v1alpha3_registration,
)
from ace.intelligence import IntelligenceOnboardingProfileV1Alpha1
from ace.intelligence.packs import compile_pack_document

import ace_market_builder.planner as planner_module
from ace_market_builder import (
    MARKET_INTELLIGENCE_PACK,
    MarketIntelligenceBuilderPlanner,
    MarketIntelligenceBuilderPlannerError,
)

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "domain_packs/market_intelligence"
NOW = datetime(2026, 8, 14, 18, tzinfo=UTC)


def _pack():
    manifest = (PACK / "manifest.json").read_bytes()
    material = json.loads(manifest)
    return compile_pack_document(
        manifest,
        {item["path"]: (PACK / item["path"]).read_bytes() for item in material["resources"]},
    )


def _profile() -> IntelligenceOnboardingProfileV1Alpha1:
    return IntelligenceOnboardingProfileV1Alpha1.model_validate_json(
        (PACK / "onboarding_profile.json").read_text(encoding="utf-8")
    )


def _request(profile: IntelligenceOnboardingProfileV1Alpha1, **updates) -> IntelligenceBuildPlanRequestV1Alpha2:
    material = {
        "product_id": "product:market-v1",
        "actor_ref": "principal:owner",
        "client_request_id": "atrium:market-v1",
        "profile_id": profile.profile_id,
        "profile_digest": profile.profile_digest,
        "subject": "Track GPT-5.6 Terra pricing and positioning implications.",
        "outcome_id": "competitive_intelligence",
        "source_group_ids": ("competitor_public_evidence",),
        "cadence_id": "daily_pulse",
        "proposed_effects": REQUIRED_INTELLIGENCE_BUILD_EFFECTS,
        "requested_at": NOW,
    }
    material.update(updates)
    return IntelligenceBuildPlanRequestV1Alpha2(**material)


@pytest.fixture(autouse=True)
def _source_checkout(monkeypatch):
    monkeypatch.setattr(planner_module, "_market_domain_file", lambda relative: ROOT / relative)
    monkeypatch.setattr(MarketIntelligenceBuilderPlanner, "artifact_identity", planner_module._artifact_identity())


@pytest.mark.asyncio
async def test_market_planner_proposes_exact_two_source_program_without_authority_binding() -> None:
    profile = _profile()
    planner = MarketIntelligenceBuilderPlanner()
    plan = await planner.prepare(_request(profile), profile=profile, pack=_pack())

    assert IntelligenceBuildPlanV1Alpha3.model_validate(plan.model_dump(mode="python")) == plan
    assert validate_intelligence_build_planner_v1alpha3_registration(
        planner,
        profile_id=profile.profile_id,
    ) == (MARKET_INTELLIGENCE_PACK, planner.artifact_identity)
    assert plan.pack_reference == MARKET_INTELLIGENCE_PACK
    assert plan.activation_proposal.activation_key == "market_intelligence_command_center"
    assert plan.activation_proposal.capability_requirement_ids == ("public_product_snapshot",)
    assert plan.activation_proposal.authority_request_ids == ("read_public_product_source",)
    assert len(plan.recorded_source_selections) == 2
    assert {item.source_uri for item in plan.recorded_source_selections} == {
        "https://openai.com/index/gpt-5-6/",
        "https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/",
    }
    assert not hasattr(plan, "execution_request_id")
    assert not hasattr(plan.activation_proposal, "capability_bindings")
    assert not hasattr(plan.activation_proposal, "authority_grant_bindings")


@pytest.mark.asyncio
async def test_market_planner_rejects_an_unimplemented_source_group() -> None:
    profile = _profile()
    with pytest.raises(MarketIntelligenceBuilderPlannerError, match="exact competitor_public_evidence"):
        await MarketIntelligenceBuilderPlanner().prepare(
            _request(profile, source_group_ids=("owned_customer_data",)),
            profile=profile,
            pack=_pack(),
        )
