"""Authority-neutral planner for the recorded Market Intelligence proof."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib.metadata import distribution

from ace.application import (
    INTELLIGENCE_BUILD_PLANNER_V1ALPHA3_CONTRACT,
    INTELLIGENCE_BUILD_PLANNING_CAPABILITY,
    IntelligenceBuildActivationProposalV1Alpha1,
    IntelligenceBuildPlanRequestV1Alpha2,
    IntelligenceBuildPlanV1Alpha3,
    RecordedSourceSelectionV1Alpha1,
)
from ace.core import CapabilityArtifactIdentityV1Alpha1, canonical_hash
from ace.intelligence import CompiledOverlayV1, CompiledPackRefV1
from ace.intelligence.contracts.intelligence_builder_presentation import IntelligenceOnboardingProfileV1Alpha1
from ace.intelligence.contracts.pack import CompiledDomainPackV1

from .executor import MARKET_INTELLIGENCE_PROFILE_ID

MARKET_INTELLIGENCE_PACK = CompiledPackRefV1(
    pack_id="market_intelligence",
    pack_version="0.8.0",
    compiled_pack_id="pack_ir:47304b9a62a147de39d38ece0290b12a",
    pack_digest="sha256:47304b9a62a147de39d38ece0290b12a2078dcdf032236f3dbceebcb23758e71",
)
MARKET_INTELLIGENCE_PLANNER_VERSION = "0.1.0"
_INVENTORY_PATH = "domain_packs/market_intelligence/conformance/openai_terra_price_recorded_sources.json"
_INVENTORY_DIGEST = "14e2c03c1dd2d329323d504b062423ec7770263e2fd35cadad8135d59d84d57f"


class MarketIntelligenceBuilderPlannerError(RuntimeError):
    """The installed Market planner cannot preserve exact reviewed material."""


def _market_domain_file(relative_path: str):
    return distribution("ace-domain-market-intelligence").locate_file(relative_path)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MarketIntelligenceBuilderPlannerError("recorded source time must include a timezone")
    return parsed.astimezone(UTC)


def _inventory() -> dict:
    try:
        material = json.loads(_market_domain_file(_INVENTORY_PATH).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise MarketIntelligenceBuilderPlannerError("recorded Market source inventory is unavailable") from exc
    if (
        material.get("contract") != "ace.market-intelligence.recorded-source-inventory/v1alpha1"
        or material.get("inventory_id") != "openai_terra_price_progression"
        or material.get("inventory_version") != "0.8.0"
        or material.get("source_group_id") != "competitor_public_evidence"
        or canonical_hash(material) != _INVENTORY_DIGEST
    ):
        raise MarketIntelligenceBuilderPlannerError("recorded Market source inventory identity changed")
    materials = material.get("materials")
    if not isinstance(materials, list) or len(materials) != 2:
        raise MarketIntelligenceBuilderPlannerError("recorded Market inventory must contain exactly two materials")
    return material


def _artifact_identity() -> CapabilityArtifactIdentityV1Alpha1:
    return CapabilityArtifactIdentityV1Alpha1(
        capability=INTELLIGENCE_BUILD_PLANNING_CAPABILITY,
        contract=INTELLIGENCE_BUILD_PLANNER_V1ALPHA3_CONTRACT,
        implementation_id="market_terra_price_planner",
        implementation_version=MARKET_INTELLIGENCE_PLANNER_VERSION,
        artifact_digest=f"sha256:{canonical_hash([MARKET_INTELLIGENCE_PLANNER_VERSION, MARKET_INTELLIGENCE_PACK.model_dump(mode='json'), _INVENTORY_DIGEST])}",
    )


class MarketIntelligenceBuilderPlanner:
    """Propose the exact two-source Market program without binding authority."""

    profile_id = MARKET_INTELLIGENCE_PROFILE_ID
    pack_reference = MARKET_INTELLIGENCE_PACK
    artifact_identity = _artifact_identity()

    async def prepare(
        self,
        request: IntelligenceBuildPlanRequestV1Alpha2,
        *,
        profile: IntelligenceOnboardingProfileV1Alpha1,
        pack: CompiledDomainPackV1,
    ) -> IntelligenceBuildPlanV1Alpha3:
        if profile.profile_id != self.profile_id or request.profile_id != self.profile_id:
            raise MarketIntelligenceBuilderPlannerError("Market planner received a different onboarding profile")
        if request.source_group_ids != ("competitor_public_evidence",):
            raise MarketIntelligenceBuilderPlannerError(
                "Market recorded proof requires the exact competitor_public_evidence group"
            )
        if (
            pack.metadata.pack_id != self.pack_reference.pack_id
            or pack.metadata.version != self.pack_reference.pack_version
            or pack.compiled_pack_id != self.pack_reference.compiled_pack_id
            or pack.pack_digest != self.pack_reference.pack_digest
        ):
            raise MarketIntelligenceBuilderPlannerError("Market planner received a different compiled Pack")
        inventory = _inventory()
        subject = inventory.get("subject_binding")
        if not isinstance(subject, dict):
            raise MarketIntelligenceBuilderPlannerError("recorded Market inventory omitted its exact subject")
        selections = tuple(
            RecordedSourceSelectionV1Alpha1(
                product_id=request.product_id,
                pack=self.pack_reference,
                source_group_id=inventory["source_group_id"],
                mapping_id=inventory["mapping_id"],
                subject_binding_id=subject["subject_binding_id"],
                entity_type_id=subject["entity_type_id"],
                entity_ref=subject["entity_ref"],
                source_definition_ref=inventory["source_definition_ref"],
                source_type_ref=inventory["source_type_ref"],
                source_uri=item["source_uri"],
                captured_payload_digest=item["captured_payload_digest"],
                source_published_at=_time(item["source_published_at"]),
                event_effective_at=_time(item["event_effective_at"]),
                observed_at=_time(item["observed_at"]),
                locator=item["locator"],
            )
            for item in inventory["materials"]
        )
        proposal = IntelligenceBuildActivationProposalV1Alpha1(
            product_id=request.product_id,
            activation_key="market_intelligence_command_center",
            pack=self.pack_reference,
            overlay=CompiledOverlayV1(
                overlay_id="market_intelligence_recorded_sources",
                version="0.8.0",
                pack_id=self.pack_reference.pack_id,
                pack_version=self.pack_reference.pack_version,
                pack_digest=self.pack_reference.pack_digest,
            ),
            capability_requirement_ids=tuple(item.requirement_id for item in pack.capability_requirements),
            authority_request_ids=tuple(item.request_id for item in pack.authority_requests),
        )
        return IntelligenceBuildPlanV1Alpha3(
            request=request,
            planner_artifact=self.artifact_identity,
            pack_reference=self.pack_reference,
            activation_proposal=proposal,
            recorded_source_selections=selections,
        )


__all__ = [
    "MARKET_INTELLIGENCE_PACK",
    "MARKET_INTELLIGENCE_PLANNER_VERSION",
    "MarketIntelligenceBuilderPlanner",
    "MarketIntelligenceBuilderPlannerError",
]
