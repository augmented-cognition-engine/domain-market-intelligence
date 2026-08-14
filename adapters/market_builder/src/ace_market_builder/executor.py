"""Trusted executor for the recorded Market Intelligence proof."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib.metadata import distribution

from ace.application import (
    IntelligenceBuildFirstBriefRequestV1Alpha2,
    PreparedShiftSignalDerivationRequestV1Alpha1,
    RecordedSourceAdmission,
    RecordedSourceMaterialV1Alpha1,
)
from ace.application.intelligence_build_execution import (
    REQUIRED_INTELLIGENCE_BUILD_EFFECTS,
    AuthorizedIntelligenceBuild,
    IntelligenceBuildExecutor,
    IntelligenceBuildHostServices,
)
from ace.intelligence import (
    EntitySnapshotV1Alpha1,
    IntelligenceOnboardingProfileV1Alpha1,
    IntelligenceResourceKind,
    IntelligenceResourceMode,
    resource_reference,
)

MARKET_INTELLIGENCE_PROFILE_ID = "onboarding_profile:market-intelligence"
SUPPORTED_RECORDED_SOURCE_GROUP_IDS = ("competitor_public_evidence",)
READ_KINDS = (
    IntelligenceResourceKind.CONNECTION,
    IntelligenceResourceKind.SOURCE,
    IntelligenceResourceKind.SOURCE_HEALTH,
    IntelligenceResourceKind.ENTITY,
    IntelligenceResourceKind.OBSERVATION,
    IntelligenceResourceKind.SIGNAL,
    IntelligenceResourceKind.SHIFT,
    IntelligenceResourceKind.CASE,
    IntelligenceResourceKind.BRIEF,
    IntelligenceResourceKind.MONITOR,
    IntelligenceResourceKind.SUBSCRIPTION,
    IntelligenceResourceKind.BUILDER_PROFILE,
    IntelligenceResourceKind.BUILDER_SESSION,
)
_INVENTORY_PATH = "domain_packs/market_intelligence/conformance/openai_terra_price_recorded_sources.json"
_PROFILE_PATH = "domain_packs/market_intelligence/onboarding_profile.json"
_SUBJECT_BINDING_ID = "listed_product"
_ENTITY_TYPE_ID = "product"
_ENTITY_REF = "product:gpt-5-6-terra-input-tokens"
_DETECTOR_ID = "product_price_move"


class MarketIntelligenceBuilderExecutorError(RuntimeError):
    """A reviewed Market request cannot be executed by the recorded adapter."""


def _market_domain_file(relative_path: str):
    return distribution("ace-domain-market-intelligence").locate_file(relative_path)


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MarketIntelligenceBuilderExecutorError("recorded source time must include a timezone")
    return parsed.astimezone(UTC)


def _inventory() -> dict:
    try:
        material = json.loads(_market_domain_file(_INVENTORY_PATH).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise MarketIntelligenceBuilderExecutorError("recorded Market source inventory is unavailable") from exc
    if (
        material.get("inventory_id") != "openai_terra_price_progression"
        or material.get("source_group_id") != SUPPORTED_RECORDED_SOURCE_GROUP_IDS[0]
        or material.get("mapping_id") != "product_price_snapshot"
        or material.get("subject_binding")
        != {
            "subject_binding_id": _SUBJECT_BINDING_ID,
            "entity_type_id": _ENTITY_TYPE_ID,
            "entity_ref": _ENTITY_REF,
        }
        or not isinstance(material.get("materials"), list)
        or len(material["materials"]) != 2
    ):
        raise MarketIntelligenceBuilderExecutorError("recorded Market source inventory changed shape")
    return material


def load_market_onboarding_profile() -> IntelligenceOnboardingProfileV1Alpha1:
    """Load the inert profile shipped by the separate Market Domain Pack."""

    return IntelligenceOnboardingProfileV1Alpha1.model_validate_json(
        _market_domain_file(_PROFILE_PATH).read_text(encoding="utf-8")
    )


def load_recorded_market_source_materials(recorded_sources) -> tuple[RecordedSourceMaterialV1Alpha1, ...]:
    """Bind the exact packaged price pair for Core-owned recorded admission."""

    inventory = _inventory()
    subject = recorded_sources.bind_subject(
        subject_binding_id=_SUBJECT_BINDING_ID,
        entity_type_id=_ENTITY_TYPE_ID,
        entity_ref=_ENTITY_REF,
    )
    return tuple(
        RecordedSourceMaterialV1Alpha1(
            source_group_id=inventory["source_group_id"],
            mapping_id=inventory["mapping_id"],
            subject_binding=subject,
            source_definition_ref=inventory["source_definition_ref"],
            source_type_ref=inventory["source_type_ref"],
            source_uri=item["source_uri"],
            captured_payload_json=item["captured_payload_json"],
            captured_payload_digest=item["captured_payload_digest"],
            source_published_at=_time(item["source_published_at"]),
            observed_at=_time(item["observed_at"]),
            locator=item["locator"],
        )
        for item in inventory["materials"]
    )


def _exact_price_entities(
    admission: RecordedSourceAdmission,
    *,
    product_id: str,
) -> tuple[EntitySnapshotV1Alpha1, EntitySnapshotV1Alpha1]:
    entities = tuple(admission.entity_snapshots)
    if len(entities) != 2:
        raise MarketIntelligenceBuilderExecutorError("recorded Market admission did not return its exact Entity pair")
    if any(
        item.mode is not IntelligenceResourceMode.PREPARED
        or item.product_id != product_id
        or item.entity_ref != _ENTITY_REF
        or item.entity_type_ref != _ENTITY_TYPE_ID
        for item in entities
    ):
        raise MarketIntelligenceBuilderExecutorError("recorded Market admission crossed its PREPARED product subject")
    ordered = tuple(sorted(entities, key=lambda item: (item.as_of, str(item.resource_id))))
    if (
        ordered[0].activation_revision != ordered[1].activation_revision
        or ordered[0].as_of >= ordered[1].as_of
        or ordered[0].resource_id == ordered[1].resource_id
    ):
        raise MarketIntelligenceBuilderExecutorError("recorded Market Entity pair lost its semantic progression")
    return ordered


class MarketIntelligenceBuilderExecutor(IntelligenceBuildExecutor):
    """Execute one exact approved Market build through Core-owned host ports."""

    profile_id = MARKET_INTELLIGENCE_PROFILE_ID

    async def start(self, build: AuthorizedIntelligenceBuild, host_services: IntelligenceBuildHostServices):
        request = build.request
        context = build.authority_use.authenticated_context
        if request.profile_id != self.profile_id:
            raise MarketIntelligenceBuilderExecutorError("Market Builder received an unsupported onboarding profile")
        if tuple(request.approved_effects) != REQUIRED_INTELLIGENCE_BUILD_EFFECTS:
            raise MarketIntelligenceBuilderExecutorError("Market Builder requires the exact bounded onboarding effects")
        if tuple(sorted(request.source_group_ids)) != SUPPORTED_RECORDED_SOURCE_GROUP_IDS:
            raise MarketIntelligenceBuilderExecutorError(
                "Market recorded proof supports only competitor_public_evidence"
            )
        if (
            context.product_id != build.product_id
            or context.actor_ref != build.actor_ref
            or build.authority_use.use_subject_ref != build.build_id
            or build.authority_use.use_subject_digest != build.request_digest
            or context.expires_at <= build.authority_use.evaluated_at
        ):
            raise MarketIntelligenceBuilderExecutorError("authorized build identity crossed its authenticated context")
        if (
            host_services.recorded_sources is None
            or host_services.prepared_derivations is None
            or host_services.first_brief is None
        ):
            raise MarketIntelligenceBuilderExecutorError(
                "Market Builder requires Core recorded-source, PREPARED-derivation, and first-Brief host ports"
            )

        materials = load_recorded_market_source_materials(host_services.recorded_sources)
        admission = await host_services.recorded_sources.admit(materials)
        baseline, current = _exact_price_entities(admission, product_id=build.product_id)
        derivation_key = f"prepared_derivation:{build.build_id}"
        derivation = await host_services.prepared_derivations.derive(
            PreparedShiftSignalDerivationRequestV1Alpha1(
                derivation_key=derivation_key,
                detector_id=_DETECTOR_ID,
                baseline_snapshot=resource_reference(baseline),
                current_snapshot=resource_reference(current),
                evaluated_at=build.authority_use.evaluated_at,
            )
        )
        if (
            not derivation.material_shift
            or derivation.shift is None
            or derivation.signal is None
            or derivation.admission is None
        ):
            raise MarketIntelligenceBuilderExecutorError(
                "recorded Market price progression did not produce its declared Shift and Signal"
            )
        attention = derivation.admission.attention_receipt
        await host_services.first_brief.create_first_brief(
            IntelligenceBuildFirstBriefRequestV1Alpha2(
                build_id=build.build_id,
                build_request_digest=build.request_digest,
                derivation_key=derivation_key,
                attention_receipt_id=str(attention.receipt_id),
                attention_receipt_digest=str(attention.receipt_digest),
                requested_at=build.authority_use.evaluated_at,
            )
        )
        evaluated_at = build.authority_use.evaluated_at
        return await host_services.resources.query(
            resource_kinds=READ_KINDS,
            subject_refs=(),
            as_of=evaluated_at,
            available_at=evaluated_at,
            evaluated_at=evaluated_at,
            page_size=200,
        )


__all__ = [
    "MARKET_INTELLIGENCE_PROFILE_ID",
    "READ_KINDS",
    "SUPPORTED_RECORDED_SOURCE_GROUP_IDS",
    "MarketIntelligenceBuilderExecutor",
    "MarketIntelligenceBuilderExecutorError",
    "load_market_onboarding_profile",
    "load_recorded_market_source_materials",
]
