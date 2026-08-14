#!/usr/bin/env python3
"""Governed Market P1D1 PREPARED Brief acceptance through public ACE APIs."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib import metadata, resources
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import ace
from ace.application import (
    BriefSynthesisError,
    BriefSynthesisReplayConflict,
    BriefSynthesisService,
    DomainActivationAdmissionService,
    PreparedIntelligenceLedgerService,
    bind_committed_activation,
)
from ace.core import (
    AuthenticatedRuntimeContextV1Alpha1,
    AuthorityUseReceiptV1Alpha1,
    CanonicalSourceSnapshotV1Alpha1,
    CapabilityArtifactIdentityV1Alpha1,
    CapabilityUseReceiptV1Alpha1,
    GovernedOperationBindingV1Alpha1,
    GovernedReasoningService,
    GovernedStateHeadPreconditionV1Alpha1,
    GovernedStateHeadV1,
    ProviderRouteV1Alpha1,
    ProviderStructuredOutputV1Alpha1,
    ProviderUsageV1Alpha1,
    ReasoningExecutionBindingV1Alpha1,
    ResolvedApprovalReceiptV1,
    ResolvedAuthorityGrantV1,
    SourceAcquisitionMode,
    canonical_json,
    capability_state_ref_for_artifact,
)
from ace.intelligence import (
    ActivationState,
    AuthorityBindingV1,
    BriefDraftClaimV1Alpha1,
    BriefDraftSectionV1Alpha1,
    BriefSynthesisDraftV1Alpha1,
    BriefSynthesisRequestV1Alpha1,
    BriefV1Alpha1,
    CapabilityBindingV1,
    CitationV1Alpha1,
    ClaimGroundingKind,
    GroundedClaimV1Alpha1,
    IntelligenceRecordKind,
    IntelligenceResourceMode,
    LineageReferenceV1Alpha1,
    LineageRelation,
    LineageResourceKind,
    OrganizationOverlayV1,
    PreparedResourceAdmissionV1Alpha1,
    ResolvedSubjectBindingV1Alpha1,
    SynthesisModuleV1,
    detect_numeric_shift,
    deterministic_resource_order,
    interpret_prepared_source_mapping,
    resource_reference,
    route_shift_as_signal,
)
from ace.intelligence.packs import (
    compile_overlay,
    compile_pack_document,
    prepare_activation_revision,
    prepare_domain_activation,
)
from ace.testing import InMemoryImmutableRecordStore

CORE_WHEEL_SHA256 = "a7c5be2f8025937fb6e3b7b06ac2f7c67a806110034e610adcd4a88e1b1d1cab"
OLD_DERIVATION_KEY = "derivation:market-intelligence:p1c:prepared-price-move:v1"
INPUT_NAME = "p1d1_prepared_brief_input.json"
EXPECTED_NAME = "p1d1_prepared_brief_expected.json"
NEGATIVE_NAME = "p1d1_prepared_brief_negative_cases.json"
P1D1_RECORD_KINDS = (
    IntelligenceRecordKind.OBSERVATION,
    IntelligenceRecordKind.ENTITY_SNAPSHOT,
    IntelligenceRecordKind.SHIFT,
    IntelligenceRecordKind.SIGNAL,
    IntelligenceRecordKind.BRIEF,
    IntelligenceRecordKind.ATTENTION_DISPOSITION,
)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("fixture time must include a timezone")
    return parsed.astimezone(UTC)


def _pack_file(path: str) -> bytes:
    try:
        return resources.files("domain_packs.market_intelligence").joinpath(path).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError):
        return (
            Path(__file__).resolve().parents[1] / "domain_packs" / "market_intelligence" / path
        ).read_bytes()


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads(_pack_file(f"releases/v0_4_0/conformance/{name}"))


def load_compatibility_fixture(name: str) -> dict[str, Any]:
    return json.loads(_pack_file(f"conformance/compatibility/core_0_8_3/{name}"))


def _load_historical_fixture(name: str) -> dict[str, Any]:
    return json.loads(_pack_file(f"releases/v0_3_0/conformance/{name}"))


def compile_market_pack(*, release: str | None = None):
    prefix = "" if release is None else f"releases/{release}/"
    manifest_bytes = _pack_file(f"{prefix}manifest.json")
    manifest = json.loads(manifest_bytes)
    return compile_pack_document(
        manifest_bytes,
        {item["path"]: _pack_file(f"{prefix}{item['path']}") for item in manifest["resources"]},
    )


class MemoryGovernedStateStore:
    """Minimal public activation-store protocol with immutable revision history."""

    def __init__(self) -> None:
        self.heads: dict[tuple[str, str, str], Any] = {}
        self.revisions: dict[tuple[str, str], Any] = {}
        self.receipts: dict[tuple[str, str], Any] = {}

    async def commit(self, request):
        revision = request.revision
        key = (revision.state_kind, revision.product_id, revision.state_id)
        current = self.heads.get(key)
        current_revision_id = None if current is None else current.revision_id
        if current_revision_id != request.expected_head_revision_id:
            raise ValueError("governed state head conflict")
        receipt = request.receipt()
        self.revisions[(revision.product_id, revision.revision_id)] = revision
        self.receipts[(revision.product_id, str(receipt.receipt_id))] = receipt
        self.heads[key] = GovernedStateHeadV1(
            state_kind=revision.state_kind,
            product_id=revision.product_id,
            state_id=revision.state_id,
            sequence=revision.sequence,
            revision_id=revision.revision_id,
            commit_receipt_id=str(receipt.receipt_id),
            updated_at=request.committed_at,
        )
        return receipt

    async def load_head(self, *, state_kind: str, product_id: str, state_id: str):
        return self.heads.get((state_kind, product_id, state_id))

    async def load_revision(self, revision_id: str, *, product_id: str):
        return self.revisions.get((product_id, revision_id))

    async def load_receipt(self, receipt_id: str, *, product_id: str):
        return self.receipts.get((product_id, receipt_id))


class ExactActivationAuthority:
    async def resolve_approval(self, **request):
        return ResolvedApprovalReceiptV1(
            receipt_ref=request["receipt_ref"],
            product_id=request["product_id"],
            subject_ref=request["subject_ref"],
            actor_ref=request["actor_ref"],
            receipt_hash="a" * 64,
            approved_at=request["effective_at"] - timedelta(seconds=1),
        )

    async def resolve_grant(self, **request):
        return ResolvedAuthorityGrantV1(
            grant_ref=request["grant_ref"],
            product_id=request["product_id"],
            authority=request["authority"],
            grant_hash="b" * 64,
            effective_at=request["effective_at"],
        )


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        if not values:
            raise ValueError("sequence clock requires at least one value")
        self.values = list(values)

    def __call__(self) -> datetime:
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


class PackArchive:
    def __init__(self, *packs) -> None:
        self.packs = {
            (
                item.metadata.pack_id,
                item.metadata.version,
                item.compiled_pack_id,
                item.pack_digest,
            ): item
            for item in packs
        }

    async def load_exact(self, *, reference):
        pack = self.packs.get(
            (
                reference.pack_id,
                reference.pack_version,
                reference.compiled_pack_id,
                reference.pack_digest,
            )
        )
        return None if pack is None else type(pack).model_validate(pack.model_dump(mode="python"))


class WrongPackResolver:
    """Deliberately violates exact historical coordinates for one negative proof."""

    def __init__(self, pack) -> None:
        self.pack = pack

    async def load_exact(self, *, reference):
        del reference
        return type(self.pack).model_validate(self.pack.model_dump(mode="python"))


def _activation_bindings(boundary: dict[str, Any]):
    capability = dict(boundary["prepared_binding"]["capability"])
    identity_material = capability.pop("artifact_identity_material")
    expected = f"sha256:{hashlib.sha256(identity_material.encode()).hexdigest()}"
    if capability["artifact_digest"] != expected:
        raise ValueError("prepared capability artifact digest changed")
    return (
        CapabilityBindingV1(**capability),
        AuthorityBindingV1(**boundary["prepared_binding"]["authority"]),
    )


def _activation_spec(
    *,
    pack,
    version: str,
    product_id: str,
    activation_key: str,
    compilation_receipt_ref: str,
    conformance_receipt_ref: str,
    boundary: dict[str, Any],
):
    capability, authority = _activation_bindings(boundary)
    overlay = compile_overlay(
        pack,
        OrganizationOverlayV1(
            overlay_id="market_intelligence_conformance",
            version=version,
            pack_id=pack.metadata.pack_id,
            pack_version=pack.metadata.version,
            pack_digest=pack.pack_digest,
        ),
    )
    return prepare_domain_activation(
        product_id=product_id,
        activation_key=activation_key,
        pack=pack,
        overlay=overlay,
        compilation_receipt_ref=compilation_receipt_ref,
        conformance_receipt_refs=(conformance_receipt_ref,),
        capability_bindings=(capability,),
        authority_bindings=(authority,),
    )


def _prepared_context(*, binding, fixture: dict[str, Any], scenario: dict[str, Any]):
    observations = []
    snapshots = []
    for item in fixture["snapshots"]:
        source = item["source"]
        source_snapshot = CanonicalSourceSnapshotV1Alpha1(
            source_definition_ref=source["source_definition_ref"],
            source_type_ref=source["source_type_ref"],
            source_uri=source["source_uri"],
            captured_payload_json=canonical_json(source["captured_payload"]),
            captured_payload_digest=source["captured_payload_digest"],
            source_published_at=(
                None
                if source["source_published_at"] is None
                else _time(source["source_published_at"])
            ),
            event_effective_at=(
                None
                if source["event_effective_at"] is None
                else _time(source["event_effective_at"])
            ),
            observed_at=_time(source["observed_at"]),
            ingested_at=_time(source["ingested_at"]),
            locator=source["locator"],
            acquisition_mode=SourceAcquisitionMode(source["acquisition_mode"]),
            acquisition_receipt_ref=source["acquisition_receipt_ref"],
            acquisition_receipt_digest=source["acquisition_receipt_digest"],
        )
        subject = item["resolved_subject"]
        mapped = interpret_prepared_source_mapping(
            binding=binding,
            mapping_id="product_price_snapshot",
            source_snapshot=source_snapshot,
            subject_binding=ResolvedSubjectBindingV1Alpha1(
                product_id=scenario["product_id"],
                activation_revision=binding.reference,
                subject_binding_id=subject["subject_binding_id"],
                entity_type_id=subject["entity_type_id"],
                entity_ref=subject["entity_ref"],
            ),
        )
        observations.append(mapped.observation)
        snapshots.append(mapped.entity_snapshot)
    shift = detect_numeric_shift(
        binding=binding,
        detector_id="product_price_move",
        baseline=snapshots[0],
        current=snapshots[1],
        detected_at=_time(scenario["shift_detected_at"]),
    )
    if shift is None:
        raise AssertionError("fixture price move must be material")
    signal = route_shift_as_signal(
        binding=binding,
        detector_id="product_price_move",
        shift=shift,
        detected_at=_time(scenario["signal_detected_at"]),
    )
    return {
        "observations": tuple(observations),
        "entity_snapshots": tuple(snapshots),
        "shift": shift,
        "signal": signal,
    }


def _manual_p1b_brief(*, binding, pack, fixture, context) -> BriefV1Alpha1:
    synthesis_ir = next(
        item for item in pack.modules if item.contract == "ace.intelligence.synthesis/v1alpha1"
    )
    synthesis = SynthesisModuleV1.model_validate_json(synthesis_ir.canonical_payload)
    citations = tuple(
        CitationV1Alpha1(
            source_ref=observation.source_ref,
            source_digest=observation.source_digest,
            acquisition_mode=observation.acquisition_mode,
            acquisition_receipt_ref=observation.acquisition_receipt_ref,
            acquisition_receipt_digest=observation.acquisition_receipt_digest,
            source_as_of=observation.observed_at,
            retrieved_at=observation.ingested_at,
            locator=item["source"]["locator"],
        )
        for observation, item in zip(context["observations"], fixture["snapshots"], strict=True)
    )
    expected = fixture["expected_prepared_brief"]
    claim = GroundedClaimV1Alpha1(
        statement=expected["claim"],
        citation_ids=tuple(item.citation_id for item in citations),
        confidence=expected["confidence"],
    )
    shift = context["shift"]
    signal = context["signal"]
    brief_as_of = max(
        shift.detected_at,
        signal.detected_at,
        *(item.ingested_at for item in context["observations"]),
    )
    return BriefV1Alpha1(
        product_id=fixture["scenario"]["product_id"],
        mode=IntelligenceResourceMode.PREPARED,
        activation_revision=binding.reference,
        as_of=brief_as_of,
        lineage=(
            LineageReferenceV1Alpha1(
                resource_kind=LineageResourceKind.SHIFT,
                relation=LineageRelation.DERIVED_FROM,
                resource_id=shift.resource_id,
                resource_digest=shift.resource_digest,
                resource_as_of=shift.as_of,
                resource_available_at=shift.detected_at,
            ),
            LineageReferenceV1Alpha1(
                resource_kind=LineageResourceKind.SIGNAL,
                relation=LineageRelation.CONTEXT,
                resource_id=signal.resource_id,
                resource_digest=signal.resource_digest,
                resource_as_of=signal.as_of,
                resource_available_at=signal.detected_at,
            ),
        ),
        brief_type_ref=synthesis.brief_templates[0].brief_type,
        title=expected["title"],
        executive_summary=expected["executive_summary"],
        body_markdown=expected["body_markdown"],
        generated_at=_time(fixture["scenario"]["brief_generated_at"]),
        citations=citations,
        claims=(claim,),
    )


def _batch(
    *,
    binding,
    context,
    derivation_key: str,
    attention_evaluated_at: datetime,
    brief: BriefV1Alpha1 | None = None,
) -> PreparedResourceAdmissionV1Alpha1:
    values = (
        *context["observations"],
        *context["entity_snapshots"],
        context["shift"],
        context["signal"],
        *((brief,) if brief is not None else ()),
    )
    return PreparedResourceAdmissionV1Alpha1(
        derivation_key=derivation_key,
        product_id=binding.prepared_binding.revision.spec.product_id,
        activation_revision=binding.prepared_binding.reference,
        pack=binding.prepared_binding.revision.spec.pack,
        observations=context["observations"],
        entity_snapshots=context["entity_snapshots"],
        shift=context["shift"],
        signal=context["signal"],
        brief=brief,
        processing_order=deterministic_resource_order(values),
        attention_evaluated_at=attention_evaluated_at,
    )


def _head(
    product_id: str,
    kind: str,
    state_id: str,
    *,
    sequence: int = 1,
    updated_at: datetime,
) -> GovernedStateHeadV1:
    return GovernedStateHeadV1(
        state_kind=kind,
        product_id=product_id,
        state_id=state_id,
        sequence=sequence,
        revision_id=f"{kind}_revision:{sequence}",
        commit_receipt_id=f"governed_state_commit:{kind}-{sequence}",
        updated_at=updated_at,
    )


class ExactRuntimeUse:
    def __init__(self, *, execution_binding, append_binding, store, updated_at) -> None:
        self.execution_binding = execution_binding
        self.append_binding = append_binding
        self.store = store
        self.updated_at = updated_at
        self.capability_calls = 0
        self.authority_calls = 0

    def _binding(self, *, artifact=None, grant_ref=None):
        if artifact is not None:
            return (
                self.execution_binding
                if artifact == self.execution_binding.artifact
                else self.append_binding
            )
        return (
            self.execution_binding
            if grant_ref == self.execution_binding.grant_ref
            else self.append_binding
        )

    async def resolve_capability_use(self, **request):
        self.capability_calls += 1
        binding = self._binding(artifact=request["artifact"])
        state = GovernedStateHeadPreconditionV1Alpha1.from_head(
            _head(
                binding.product_id,
                "capability_state",
                capability_state_ref_for_artifact(binding.artifact),
                updated_at=self.updated_at,
            )
        )
        return CapabilityUseReceiptV1Alpha1(
            product_id=binding.product_id,
            actor_ref=request["context"].actor_ref,
            authenticated_context=request["context"],
            use_subject_ref=request["use_subject_ref"],
            use_subject_digest=request["use_subject_digest"],
            operation=request["operation"],
            artifact=request["artifact"],
            capability_state_ref=request["capability_state_ref"],
            configuration_ref=request["configuration_ref"],
            evaluated_at=request["evaluated_at"],
            resolved_at=request["evaluated_at"],
            state_head_precondition=state,
        )

    async def resolve_authority_use(self, **request):
        self.authority_calls += 1
        binding = self._binding(grant_ref=request["grant_ref"])
        return AuthorityUseReceiptV1Alpha1(
            product_id=binding.product_id,
            actor_ref=request["context"].actor_ref,
            authenticated_context=request["context"],
            use_subject_ref=request["use_subject_ref"],
            use_subject_digest=request["use_subject_digest"],
            operation=request["operation"],
            authority=request["authority"],
            grant_ref=request["grant_ref"],
            grant_hash="d" * 64,
            evaluated_at=request["evaluated_at"],
            expires_at=request["context"].expires_at,
            state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(
                _head(
                    binding.product_id,
                    "authority_grant",
                    binding.grant_ref,
                    updated_at=self.updated_at,
                )
            ),
        )


class FixtureProvider:
    def __init__(self, *, fixture: dict[str, Any], artifact, mutation=None) -> None:
        self.fixture = fixture
        self.artifact_identity = artifact
        self.mutation = mutation
        self.calls = 0
        self.requests = []

    @staticmethod
    def _support_groups(request):
        by_kind: dict[str, tuple[str, ...]] = {}
        for kind in ("observation", "entity_snapshot", "shift", "signal"):
            by_kind[kind] = tuple(
                item.record_key for item in request.context_items if item.record_kind == kind
            )
        return {
            "all_observations": by_kind["observation"],
            "shift_and_snapshots": (
                *by_kind["shift"],
                *by_kind["entity_snapshot"],
            ),
            "signal": by_kind["signal"],
            "shift": by_kind["shift"],
        }

    def _draft(self, request):
        groups = self._support_groups(request)
        sections = []
        recommendation_id = None
        for section_payload in self.fixture["provider_draft"]["sections"]:
            claims = []
            for payload in section_payload["claims"]:
                supports = groups[payload["support_group"]]
                if self.mutation == "cited_claim_non_observation_support" and (
                    payload["grounding_kind"] == "cited"
                ):
                    supports = groups["shift"]
                elif self.mutation == "unknown_support" and (payload["grounding_kind"] == "cited"):
                    supports = (*supports, "observation:unknown-support")
                elif self.mutation == "unused_selected_support" and (
                    payload["grounding_kind"] == "cited"
                ):
                    supports = supports[1:]
                claim = BriefDraftClaimV1Alpha1(
                    statement=payload["statement"],
                    grounding_kind=ClaimGroundingKind(payload["grounding_kind"]),
                    support_refs=supports,
                    confidence=payload["confidence"],
                    uncertainty=payload["uncertainty"],
                )
                claims.append(claim)
                if section_payload["section_id"] == "recommendation":
                    recommendation_id = str(claim.claim_id)
            sections.append(
                BriefDraftSectionV1Alpha1(
                    section_id=section_payload["section_id"],
                    claims=tuple(claims),
                )
            )
        if self.mutation == "missing_required_section":
            sections.pop()
        elif self.mutation == "reordered_required_sections":
            sections = list(reversed(sections))
        draft = BriefSynthesisDraftV1Alpha1(
            brief_type=(
                "wrong_brief_type"
                if self.mutation == "wrong_provider_brief_type"
                else self.fixture["provider_draft"]["brief_type"]
            ),
            persona_ids=(
                ("product_marketer",)
                if self.mutation == "wrong_provider_persona"
                else tuple(self.fixture["provider_draft"]["persona_ids"])
            ),
            sections=tuple(sections),
            recommendation_claim_id=recommendation_id,
        )
        return draft

    async def execute(self, request):
        self.calls += 1
        self.requests.append(request)
        draft = self._draft(request)
        return ProviderStructuredOutputV1Alpha1(
            route=ProviderRouteV1Alpha1(**self.fixture["reasoning"]["provider_route"]),
            usage=ProviderUsageV1Alpha1(**self.fixture["reasoning"]["provider_usage"]),
            structured_json=canonical_json(draft.model_dump(mode="json")),
            referenced_context_ids=tuple(str(item.context_id) for item in request.context_items),
        )


class ForbiddenProvider:
    def __init__(self, artifact) -> None:
        self.artifact_identity = artifact
        self.calls = 0

    async def execute(self, request):
        del request
        self.calls += 1
        raise AssertionError("historical replay must not invoke a provider")


@dataclass(slots=True)
class Environment:
    fixture: dict[str, Any]
    old_fixture: dict[str, Any]
    old_pack: Any
    new_pack: Any
    activation_store: MemoryGovernedStateStore
    activation_service: DomainActivationAdmissionService
    rev1: Any
    rev2: Any
    rev1_binding: Any
    rev2_binding: Any
    old_context: dict[str, Any]
    new_context: dict[str, Any]
    manual_brief: BriefV1Alpha1
    old_admission: Any
    pre_brief_batch: PreparedResourceAdmissionV1Alpha1
    pre_brief_admission: Any
    store: InMemoryImmutableRecordStore
    provider: FixtureProvider
    runtime: ExactRuntimeUse
    reasoning: GovernedReasoningService
    execution_binding: ReasoningExecutionBindingV1Alpha1
    append_binding: GovernedOperationBindingV1Alpha1
    request: BriefSynthesisRequestV1Alpha1
    service: BriefSynthesisService


def _prebuilt_p1d1_brief(*, binding, context, generated_at: datetime) -> BriefV1Alpha1:
    citations = tuple(
        CitationV1Alpha1(
            source_ref=observation.source_ref,
            source_digest=observation.source_digest,
            acquisition_mode=observation.acquisition_mode,
            acquisition_receipt_ref=observation.acquisition_receipt_ref,
            acquisition_receipt_digest=observation.acquisition_receipt_digest,
            source_as_of=observation.observed_at,
            retrieved_at=observation.ingested_at,
            locator=None,
        )
        for observation in context["observations"]
    )
    claim = GroundedClaimV1Alpha1(
        statement="The listed Edge X1 price changed from USD 1,200 to USD 1,080.",
        citation_ids=tuple(item.citation_id for item in citations),
        confidence=1.0,
    )
    shift = context["shift"]
    signal = context["signal"]
    brief_as_of = max(
        shift.detected_at,
        signal.detected_at,
        *(item.ingested_at for item in context["observations"]),
    )
    return BriefV1Alpha1(
        product_id=binding.prepared_binding.revision.spec.product_id,
        mode=IntelligenceResourceMode.PREPARED,
        activation_revision=binding.prepared_binding.reference,
        as_of=brief_as_of,
        lineage=(
            LineageReferenceV1Alpha1(
                resource_kind=LineageResourceKind.SHIFT,
                relation=LineageRelation.DERIVED_FROM,
                resource_id=shift.resource_id,
                resource_digest=shift.resource_digest,
                resource_as_of=shift.as_of,
                resource_available_at=shift.detected_at,
            ),
            LineageReferenceV1Alpha1(
                resource_kind=LineageResourceKind.SIGNAL,
                relation=LineageRelation.CONTEXT,
                resource_id=signal.resource_id,
                resource_digest=signal.resource_digest,
                resource_as_of=signal.as_of,
                resource_available_at=signal.detected_at,
            ),
        ),
        brief_type_ref="competitive_intelligence",
        title="Prebuilt Price Move Brief",
        executive_summary=claim.statement,
        body_markdown=claim.statement,
        generated_at=generated_at,
        citations=citations,
        claims=(claim,),
    )


async def build_environment(
    *,
    provider_mutation: str | None = None,
    prebuilt_brief_derivation: bool = False,
) -> Environment:
    fixture = load_fixture(INPUT_NAME)
    old_fixture = _load_historical_fixture("p1_price_move_golden.json")
    boundary = _load_historical_fixture("public_product_price_boundary.json")
    old_pack = compile_market_pack(release="v0_3_0")
    new_pack = compile_market_pack(release="v0_4_0")
    activation_store = MemoryGovernedStateStore()
    activation_service = DomainActivationAdmissionService(
        store=activation_store,
        authority=ExactActivationAuthority(),
    )
    product_id = fixture["activation"]["product_id"]
    activation_key = fixture["activation"]["activation_key"]
    spec1 = _activation_spec(
        pack=old_pack,
        version=old_fixture["fixture_version"],
        product_id=product_id,
        activation_key=activation_key,
        compilation_receipt_ref=old_fixture["scenario"]["compilation_receipt_ref"],
        conformance_receipt_ref=old_fixture["scenario"]["conformance_receipt_ref"],
        boundary=boundary,
    )
    revision1 = prepare_activation_revision(
        spec=spec1,
        state=ActivationState.ACTIVE,
        actor_ref=old_fixture["scenario"]["actor_ref"],
        approval_receipt_ref=old_fixture["scenario"]["approval_receipt_ref"],
        occurred_at=_time(old_fixture["scenario"]["activation_occurred_at"]),
    )
    rev1 = await activation_service.admit(
        revision1,
        expected_head_revision_id=None,
        committed_at=revision1.occurred_at + timedelta(seconds=1),
    )
    rev1_binding = bind_committed_activation(pack=old_pack, committed=rev1)
    store = InMemoryImmutableRecordStore()
    activation_head1 = activation_store.heads[
        (rev1.commit_receipt.state_kind, product_id, rev1.commit_receipt.state_id)
    ]
    store.set_governed_state_head(activation_head1)
    old_context = _prepared_context(
        binding=rev1_binding.prepared_binding,
        fixture=old_fixture,
        scenario={
            "product_id": product_id,
            "shift_detected_at": old_fixture["scenario"]["shift_detected_at"],
            "signal_detected_at": old_fixture["scenario"]["signal_detected_at"],
        },
    )
    manual_brief = _manual_p1b_brief(
        binding=rev1_binding.prepared_binding,
        pack=old_pack,
        fixture=old_fixture,
        context=old_context,
    )
    old_batch = _batch(
        binding=rev1_binding,
        context=old_context,
        derivation_key=OLD_DERIVATION_KEY,
        attention_evaluated_at=_time("2026-02-15T12:04:00Z"),
        brief=manual_brief,
    )
    old_admission = await PreparedIntelligenceLedgerService(
        binding=rev1_binding, store=store
    ).admit(old_batch)

    spec2 = _activation_spec(
        pack=new_pack,
        version=fixture["fixture_version"],
        product_id=product_id,
        activation_key=activation_key,
        compilation_receipt_ref=fixture["activation"]["revision_2_compilation_receipt_ref"],
        conformance_receipt_ref=fixture["activation"]["revision_2_conformance_receipt_ref"],
        boundary=boundary,
    )
    revision2 = prepare_activation_revision(
        spec=spec2,
        state=ActivationState.ACTIVE,
        actor_ref=fixture["activation"]["actor_ref"],
        approval_receipt_ref=fixture["activation"]["revision_2_approval_receipt_ref"],
        occurred_at=_time(fixture["activation"]["revision_2_occurred_at"]),
        prior_revision=rev1.revision,
    )
    rev2 = await activation_service.admit(
        revision2,
        expected_head_revision_id=str(rev1.revision.revision_id),
        committed_at=_time(fixture["activation"]["revision_2_committed_at"]),
    )
    rev2_binding = bind_committed_activation(pack=new_pack, committed=rev2)
    activation_head2 = activation_store.heads[
        (rev2.commit_receipt.state_kind, product_id, rev2.commit_receipt.state_id)
    ]
    store.set_governed_state_head(activation_head2)
    new_context = _prepared_context(
        binding=rev2_binding.prepared_binding,
        fixture=fixture,
        scenario={
            "product_id": product_id,
            "shift_detected_at": fixture["derivation"]["shift_detected_at"],
            "signal_detected_at": fixture["derivation"]["signal_detected_at"],
        },
    )
    prebuilt_brief = None
    if prebuilt_brief_derivation:
        prebuilt_brief = _prebuilt_p1d1_brief(
            binding=rev2_binding,
            context=new_context,
            generated_at=_time(fixture["derivation"]["signal_detected_at"]) + timedelta(seconds=10),
        )
    pre_brief_batch = _batch(
        binding=rev2_binding,
        context=new_context,
        derivation_key=fixture["derivation"]["derivation_key"],
        attention_evaluated_at=_time(fixture["derivation"]["attention_evaluated_at"]),
        brief=prebuilt_brief,
    )
    pre_brief_admission = await PreparedIntelligenceLedgerService(
        binding=rev2_binding, store=store
    ).admit(pre_brief_batch)

    reasoning_artifact = CapabilityArtifactIdentityV1Alpha1(
        **fixture["reasoning"]["reasoning_artifact"]
    )
    append_artifact = CapabilityArtifactIdentityV1Alpha1(**fixture["reasoning"]["append_artifact"])
    updated_at = _time(fixture["activation"]["revision_2_occurred_at"])
    execution_head = _head(
        product_id,
        "reasoning_configuration",
        "reasoning_configuration:market-p1d1",
        updated_at=updated_at,
    )
    append_head = _head(
        product_id,
        "governed_operation_configuration",
        "governed_operation_configuration:market-p1d1-append",
        updated_at=updated_at,
    )
    execution_binding = ReasoningExecutionBindingV1Alpha1(
        product_id=product_id,
        artifact=reasoning_artifact,
        configuration_ref=execution_head.state_id,
        authority="reason",
        grant_ref="authority_grant:market-p1d1-reason",
        state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(execution_head),
    )
    append_binding = GovernedOperationBindingV1Alpha1(
        product_id=product_id,
        artifact=append_artifact,
        configuration_ref=append_head.state_id,
        authority="append_immutable_records",
        grant_ref="authority_grant:market-p1d1-append",
        state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(append_head),
    )
    for head in (
        execution_head,
        append_head,
        _head(
            product_id,
            "capability_state",
            capability_state_ref_for_artifact(reasoning_artifact),
            updated_at=updated_at,
        ),
        _head(
            product_id,
            "authority_grant",
            execution_binding.grant_ref,
            updated_at=updated_at,
        ),
        _head(
            product_id,
            "capability_state",
            capability_state_ref_for_artifact(append_artifact),
            updated_at=updated_at,
        ),
        _head(
            product_id,
            "authority_grant",
            append_binding.grant_ref,
            updated_at=updated_at,
        ),
    ):
        store.set_governed_state_head(head)
    runtime = ExactRuntimeUse(
        execution_binding=execution_binding,
        append_binding=append_binding,
        store=store,
        updated_at=updated_at,
    )
    provider = FixtureProvider(
        fixture=fixture,
        artifact=reasoning_artifact,
        mutation=provider_mutation,
    )
    requested_at = _time(fixture["reasoning"]["requested_at"])
    generated_at = _time(fixture["reasoning"]["generated_at"])
    reasoning = GovernedReasoningService(
        store=store,
        runtime_use=runtime,
        provider=provider,
        clock=SequenceClock(
            requested_at,
            requested_at + timedelta(seconds=5),
            requested_at + timedelta(seconds=10),
            generated_at,
            generated_at,
        ),
    )
    auth = fixture["reasoning"]["authentication"]
    context = AuthenticatedRuntimeContextV1Alpha1(
        product_id=product_id,
        actor_ref=auth["actor_ref"],
        authentication_receipt_ref=auth["receipt_ref"],
        authentication_receipt_digest=auth["receipt_digest"],
        authenticated_at=_time(auth["authenticated_at"]),
        expires_at=_time(auth["expires_at"]),
    )
    request = BriefSynthesisRequestV1Alpha1(
        synthesis_key=fixture["reasoning"]["synthesis_key"],
        reasoning_attempt_key=fixture["reasoning"]["reasoning_attempt_key"],
        derivation_key=pre_brief_batch.derivation_key,
        product_id=product_id,
        authenticated_context=context,
        activation_revision=rev2_binding.prepared_binding.reference,
        pack=rev2_binding.prepared_binding.revision.spec.pack,
        attention_receipt_id=str(pre_brief_admission.attention_receipt.receipt_id),
        attention_receipt_digest=str(pre_brief_admission.attention_receipt.receipt_digest),
        brief_as_of=pre_brief_batch.attention_evaluated_at,
        context_cutoff_at=pre_brief_batch.attention_evaluated_at,
        requested_at=requested_at,
    )
    service = BriefSynthesisService(
        activation_service=activation_service,
        pack=new_pack,
        store=store,
        reasoning=reasoning,
        execution_binding=execution_binding,
        append_binding=append_binding,
        clock=SequenceClock(generated_at),
    )
    return Environment(
        fixture=fixture,
        old_fixture=old_fixture,
        old_pack=old_pack,
        new_pack=new_pack,
        activation_store=activation_store,
        activation_service=activation_service,
        rev1=rev1,
        rev2=rev2,
        rev1_binding=rev1_binding,
        rev2_binding=rev2_binding,
        old_context=old_context,
        new_context=new_context,
        manual_brief=manual_brief,
        old_admission=old_admission,
        pre_brief_batch=pre_brief_batch,
        pre_brief_admission=pre_brief_admission,
        store=store,
        provider=provider,
        runtime=runtime,
        reasoning=reasoning,
        execution_binding=execution_binding,
        append_binding=append_binding,
        request=request,
        service=service,
    )


@dataclass(frozen=True, slots=True)
class PositiveResult:
    environment: Environment
    first: Any
    same_service_replay: Any
    rev3: Any
    rollback_replay: Any
    forbidden_provider_calls: int
    historical_manual_brief: BriefV1Alpha1


async def run_positive() -> PositiveResult:
    env = await build_environment()
    first = await env.service.synthesize(env.request)
    same_service_replay = await env.service.synthesize(env.request)
    fixture = env.fixture
    revision3 = prepare_activation_revision(
        spec=env.rev1.revision.spec,
        state=ActivationState.ACTIVE,
        actor_ref=fixture["activation"]["actor_ref"],
        approval_receipt_ref=fixture["activation"]["revision_3_approval_receipt_ref"],
        occurred_at=_time(fixture["activation"]["revision_3_rollback_occurred_at"]),
        prior_revision=env.rev2.revision,
        rollback_of=env.rev1.revision,
    )
    rev3 = await env.activation_service.admit(
        revision3,
        expected_head_revision_id=str(env.rev2.revision.revision_id),
        committed_at=_time(fixture["activation"]["revision_3_rollback_committed_at"]),
    )
    product_id = fixture["activation"]["product_id"]
    activation_head3 = env.activation_store.heads[
        (rev3.commit_receipt.state_kind, product_id, rev3.commit_receipt.state_id)
    ]
    env.store.set_governed_state_head(activation_head3)
    replay_fixture = fixture["rollback_replay"]
    fresh_context = AuthenticatedRuntimeContextV1Alpha1(
        product_id=product_id,
        actor_ref=env.request.authenticated_context.actor_ref,
        authentication_receipt_ref=replay_fixture["fresh_authentication_receipt_ref"],
        authentication_receipt_digest=replay_fixture["fresh_authentication_receipt_digest"],
        authenticated_at=_time(replay_fixture["fresh_authenticated_at"]),
        expires_at=_time(replay_fixture["fresh_expires_at"]),
    )
    forbidden = ForbiddenProvider(env.execution_binding.artifact)
    replay_reasoning = GovernedReasoningService(
        store=env.store,
        runtime_use=env.runtime,
        provider=forbidden,
        clock=SequenceClock(_time(replay_fixture["delivery_evaluated_at"])),
    )
    restarted = BriefSynthesisService(
        activation_service=env.activation_service,
        pack=env.old_pack,
        pack_resolver=PackArchive(env.old_pack, env.new_pack),
        store=env.store,
        reasoning=replay_reasoning,
        execution_binding=env.execution_binding,
        append_binding=env.append_binding,
        clock=SequenceClock(_time(replay_fixture["delivery_evaluated_at"])),
    )
    rollback_replay = await restarted.synthesize(
        env.request,
        delivery_context=fresh_context,
    )
    historical_rev1 = await env.activation_service.load_exact(
        product_id=product_id,
        revision_id=str(env.rev1.revision.revision_id),
        commit_receipt_id=str(env.rev1.commit_receipt.receipt_id),
    )
    if historical_rev1 is None:
        raise AssertionError("historical revision 1 must remain loadable")
    historical_binding = bind_committed_activation(
        pack=env.old_pack,
        committed=historical_rev1,
    )
    loaded_manual = await PreparedIntelligenceLedgerService(
        binding=historical_binding,
        store=env.store,
    ).load_exact(resource_reference(env.manual_brief))
    if not isinstance(loaded_manual, BriefV1Alpha1):
        raise AssertionError("historical manual Brief must remain readable")
    return PositiveResult(
        environment=env,
        first=first,
        same_service_replay=same_service_replay,
        rev3=rev3,
        rollback_replay=rollback_replay,
        forbidden_provider_calls=forbidden.calls,
        historical_manual_brief=loaded_manual,
    )


def _reference_projection(value) -> dict[str, Any]:
    exact = resource_reference(value)
    return exact.model_dump(mode="json")


def _activation_projection(committed) -> dict[str, Any]:
    return {
        "revision": committed.revision.model_dump(mode="json"),
        "commit_receipt": committed.commit_receipt.model_dump(mode="json"),
    }


async def positive_projection(result: PositiveResult) -> dict[str, Any]:
    env = result.environment
    first = result.first
    product_id = env.fixture["activation"]["product_id"]
    rollback_binding = bind_committed_activation(
        pack=env.old_pack,
        committed=result.rev3,
    )
    ledger = PreparedIntelligenceLedgerService(
        binding=rollback_binding,
        store=env.store,
    )
    counts = {}
    for kind in P1D1_RECORD_KINDS:
        counts[kind.value] = await ledger.count_as_of(
            product_id=product_id,
            mode=IntelligenceResourceMode.PREPARED,
            kind=kind,
            available_at=_time("2026-08-06T15:30:00Z"),
        )
    live_counts = {}
    for kind in P1D1_RECORD_KINDS:
        live_counts[kind.value] = await ledger.count_as_of(
            product_id=product_id,
            mode=IntelligenceResourceMode.LIVE,
            kind=kind,
            available_at=_time("2026-08-06T15:30:00Z"),
        )
    record_kind_counts: dict[str, int] = {}
    for record in env.store.records.values():
        record_kind_counts[record.record_kind] = record_kind_counts.get(record.record_kind, 0) + 1
    provider_request = env.provider.requests[0]
    return {
        "platform_dependency": {
            "ace_core_wheel_sha256": CORE_WHEEL_SHA256,
        },
        "packs": {
            "v0_3_0": {
                "compiled_pack_id": env.old_pack.compiled_pack_id,
                "pack_digest": env.old_pack.pack_digest,
                "synthesis_module_digest": next(
                    item.module_digest
                    for item in env.old_pack.modules
                    if item.module_id == "market_synthesis"
                ),
            },
            "v0_4_0": {
                "compiled_pack_id": env.new_pack.compiled_pack_id,
                "pack_digest": env.new_pack.pack_digest,
                "synthesis_module_digest": next(
                    item.module_digest
                    for item in env.new_pack.modules
                    if item.module_id == "market_synthesis"
                ),
            },
        },
        "activation_lifecycle": {
            "revision_1": _activation_projection(env.rev1),
            "revision_2": _activation_projection(env.rev2),
            "revision_3_rollback": _activation_projection(result.rev3),
        },
        "historical_manual_p1b": {
            "brief": _reference_projection(result.historical_manual_brief),
            "readable_after_rollback": True,
            "attention_receipt_id": str(env.old_admission.attention_receipt.receipt_id),
            "attention_receipt_digest": str(env.old_admission.attention_receipt.receipt_digest),
        },
        "pre_brief_derivation": {
            "batch_id": str(env.pre_brief_batch.batch_id),
            "batch_digest": str(env.pre_brief_batch.batch_digest),
            "derivation_key": env.pre_brief_batch.derivation_key,
            "brief": None,
            "resources": [
                _reference_projection(item) for item in env.pre_brief_admission.resources
            ],
            "attention_receipt": env.pre_brief_admission.attention_receipt.model_dump(mode="json"),
            "transaction_receipt": env.pre_brief_admission.transaction_receipt.model_dump(
                mode="json"
            ),
        },
        "synthesis_request": env.request.model_dump(mode="json"),
        "provider_request": {
            "request_id": provider_request.request_id,
            "request_digest": provider_request.request_digest,
            "attempt_key": provider_request.attempt_key,
            "instruction_json": provider_request.instruction_json,
            "context_ids": [str(item.context_id) for item in provider_request.context_items],
            "context_record_keys": [item.record_key for item in provider_request.context_items],
        },
        "brief": first.brief.model_dump(mode="json"),
        "synthesis_receipt": first.synthesis_receipt.model_dump(mode="json"),
        "atomic_append_transaction": first.transaction_receipt.model_dump(mode="json"),
        "replay": {
            "same_service_equal": result.same_service_replay == replace(first, replayed=True),
            "rollback_fresh_service_equal": result.rollback_replay == replace(first, replayed=True),
            "provider_calls": env.provider.calls,
            "forbidden_replay_provider_calls": result.forbidden_provider_calls,
        },
        "persistence": {
            "prepared_counts": counts,
            "live_counts": live_counts,
            "record_kind_counts": dict(sorted(record_kind_counts.items())),
            "transaction_count": len(env.store.receipts),
            "delivery_authority": False,
        },
    }


def assert_positive(result: PositiveResult, projection: dict[str, Any]) -> None:
    env = result.environment
    first = result.first
    fixture = env.fixture
    if result.same_service_replay != replace(first, replayed=True):
        raise AssertionError("same-service replay changed exact admission")
    if result.rollback_replay != replace(first, replayed=True):
        raise AssertionError("rollback fresh-service replay changed exact admission")
    if env.provider.calls != 1 or result.forbidden_provider_calls != 0:
        raise AssertionError("historical replay invoked the provider")
    if env.pre_brief_batch.brief is not None:
        raise AssertionError("route-triggered derivation must not contain a Brief")
    if len(env.pre_brief_admission.resources) != 6:
        raise AssertionError("P1D1 pre-Brief closure must contain exactly six resources")
    if len(env.pre_brief_admission.transaction_receipt.records) != 7:
        raise AssertionError("pre-Brief transaction must include six resources and attention")
    if (
        env.old_admission.attention_receipt.receipt_id
        == env.pre_brief_admission.attention_receipt.receipt_id
    ):
        raise AssertionError("P1D1 must not reuse the historical attention receipt")
    if first.brief.title != "Competitive Price Move Brief":
        raise AssertionError("canonical template title changed")
    expected_sections = tuple(fixture["pack"]["required_sections"])
    if first.synthesis_receipt.actual_section_ids != expected_sections:
        raise AssertionError("required section order changed")
    if first.synthesis_receipt.required_section_ids != expected_sections:
        raise AssertionError("resolved template order changed")
    if first.brief.body_markdown.count("## Recommendation") != 1:
        raise AssertionError("canonical Brief must render one recommendation section")
    if any(item.locator is not None for item in first.brief.citations):
        raise AssertionError("canonical Brief citation locators must remain null")
    rendered = canonical_json(first.brief)
    if "Northstar" in rendered or "northstar" in rendered.lower():
        raise AssertionError("invented competitor attribution reached the final Brief")
    exact_claim = "The listed Edge X1 price changed from USD 1,200 to USD 1,080."
    if exact_claim not in {item.statement for item in first.brief.claims}:
        raise AssertionError("exact grounded price assertion changed")
    if not any(
        item.statement == "Ownership, motive, and market effect are not established."
        for item in first.brief.claims
    ):
        raise AssertionError("required limitation is absent")
    if result.rev3.revision.spec != env.rev1.revision.spec:
        raise AssertionError("rollback did not restore exact revision-1 spec")
    if (
        len(
            {
                env.rev1.revision.activation_id,
                env.rev2.revision.activation_id,
                result.rev3.revision.activation_id,
            }
        )
        != 1
    ):
        raise AssertionError("logical activation identity changed across revisions")
    if projection["persistence"]["delivery_authority"]:
        raise AssertionError("P1D1 grants no delivery authority")
    if any(projection["persistence"]["live_counts"].values()):
        raise AssertionError("P1D1 persisted LIVE material")
    historical = fixture["historical_archive"]
    if historical != {
        "pack_version": "0.3.0",
        "compiled_pack_id": "pack_ir:19de6d59b28095f7bd7600364c3b4de7",
        "pack_digest": ("sha256:19de6d59b28095f7bd7600364c3b4de787cce0365764cf54ab9f282f3412c2dd"),
        "manual_brief_id": "brief:1bf59d3e6c5a47634c345a9366b555be",
        "manual_brief_digest": (
            "sha256:1bf59d3e6c5a47634c345a9366b555be04e45f3ab2f8099d54b998cef4c6d5b8"
        ),
    }:
        raise AssertionError("historical archive coordinates changed")
    if any(
        citation.retrieved_at > result.historical_manual_brief.as_of
        for citation in result.historical_manual_brief.citations
    ):
        raise AssertionError("compatibility replay admitted future citation evidence")


def _synthesis_output_counts(store) -> dict[str, int]:
    counts = {
        "brief": 0,
        "brief_synthesis_receipt": 0,
        "prepared_synthesis_transaction_receipt": 0,
    }
    for record in store.records.values():
        if record.record_kind in counts:
            counts[record.record_kind] += 1
    counts["prepared_synthesis_transaction_receipt"] = sum(
        receipt.record_space == "prepared"
        and receipt.transaction_key.startswith("brief_synthesis:")
        for receipt in store.receipts.values()
    )
    return counts


def _rebuild_request(env: Environment, **updates) -> BriefSynthesisRequestV1Alpha1:
    payload = env.request.model_dump(
        mode="python",
        exclude={"request_id", "request_digest"},
    )
    payload.update(updates)
    return BriefSynthesisRequestV1Alpha1.model_validate(payload)


async def _record_failed_case(
    case_id: str,
    *,
    env: Environment,
    request: BriefSynthesisRequestV1Alpha1,
) -> dict[str, Any]:
    before = _synthesis_output_counts(env.store)
    try:
        await env.service.synthesize(request)
    except (BriefSynthesisError, BriefSynthesisReplayConflict) as exc:
        after = _synthesis_output_counts(env.store)
        return {
            "case_id": case_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "cause": None if exc.__cause__ is None else str(exc.__cause__),
            "provider_calls": env.provider.calls,
            "brief_residue_delta": after["brief"] - before["brief"],
            "synthesis_receipt_residue_delta": (
                after["brief_synthesis_receipt"] - before["brief_synthesis_receipt"]
            ),
            "prepared_synthesis_transaction_residue_delta": (
                after["prepared_synthesis_transaction_receipt"]
                - before["prepared_synthesis_transaction_receipt"]
            ),
        }
    raise AssertionError(f"negative case unexpectedly succeeded: {case_id}")


async def run_negative_inventory() -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []

    async def request_case(case_id: str, **updates) -> None:
        env = await build_environment()
        observed.append(
            await _record_failed_case(
                case_id,
                env=env,
                request=_rebuild_request(env, **updates),
            )
        )

    old_attention = await build_environment()
    observed.append(
        await _record_failed_case(
            "old_attention_receipt",
            env=old_attention,
            request=_rebuild_request(
                old_attention,
                attention_receipt_id=str(old_attention.old_admission.attention_receipt.receipt_id),
                attention_receipt_digest=str(
                    old_attention.old_admission.attention_receipt.receipt_digest
                ),
            ),
        )
    )
    await request_case("wrong_attention_digest", attention_receipt_digest="sha256:" + "f" * 64)

    prebuilt = await build_environment(prebuilt_brief_derivation=True)
    observed.append(
        await _record_failed_case(
            "prebuilt_brief_derivation",
            env=prebuilt,
            request=prebuilt.request,
        )
    )

    wrong_version = await build_environment()
    observed.append(
        await _record_failed_case(
            "wrong_pack_version",
            env=wrong_version,
            request=_rebuild_request(
                wrong_version,
                pack=wrong_version.rev1_binding.prepared_binding.revision.spec.pack,
            ),
        )
    )
    wrong_activation = await build_environment()
    observed.append(
        await _record_failed_case(
            "wrong_activation_revision",
            env=wrong_activation,
            request=_rebuild_request(
                wrong_activation,
                activation_revision=wrong_activation.rev1_binding.prepared_binding.reference,
            ),
        )
    )
    await request_case("wrong_derivation_key", derivation_key="derivation:missing")

    as_of = await build_environment()
    observed.append(
        await _record_failed_case(
            "as_of_mismatch",
            env=as_of,
            request=_rebuild_request(
                as_of,
                brief_as_of=as_of.request.brief_as_of - timedelta(seconds=1),
                context_cutoff_at=(as_of.request.context_cutoff_at - timedelta(seconds=1)),
            ),
        )
    )
    cutoff = await build_environment()
    observed.append(
        await _record_failed_case(
            "cutoff_before_signal_availability",
            env=cutoff,
            request=_rebuild_request(
                cutoff,
                brief_as_of=(cutoff.new_context["signal"].detected_at - timedelta(seconds=1)),
                context_cutoff_at=cutoff.new_context["signal"].detected_at - timedelta(seconds=1),
            ),
        )
    )

    for mutation in (
        "wrong_provider_brief_type",
        "wrong_provider_persona",
        "missing_required_section",
        "reordered_required_sections",
        "cited_claim_non_observation_support",
        "unknown_support",
        "unused_selected_support",
    ):
        env = await build_environment(provider_mutation=mutation)
        observed.append(
            await _record_failed_case(
                mutation,
                env=env,
                request=env.request,
            )
        )

    divergent = await build_environment()
    await divergent.service.synthesize(divergent.request)
    observed.append(
        await _record_failed_case(
            "divergent_same_synthesis_key",
            env=divergent,
            request=_rebuild_request(
                divergent,
                reasoning_attempt_key="reasoning:market-intelligence:p1d1:divergent",
            ),
        )
    )

    historical = await run_positive()
    env = historical.environment
    for case_id, resolver in (
        ("wrong_historical_pack", WrongPackResolver(env.old_pack)),
        ("missing_historical_pack", PackArchive(env.old_pack)),
    ):
        forbidden = ForbiddenProvider(env.execution_binding.artifact)
        replay_reasoning = GovernedReasoningService(
            store=env.store,
            runtime_use=env.runtime,
            provider=forbidden,
            clock=SequenceClock(_time(env.fixture["rollback_replay"]["delivery_evaluated_at"])),
        )
        archive_service = BriefSynthesisService(
            activation_service=env.activation_service,
            pack=env.old_pack,
            pack_resolver=resolver,
            store=env.store,
            reasoning=replay_reasoning,
            execution_binding=env.execution_binding,
            append_binding=env.append_binding,
            clock=SequenceClock(_time(env.fixture["rollback_replay"]["delivery_evaluated_at"])),
        )
        before = _synthesis_output_counts(env.store)
        try:
            await archive_service.synthesize(env.request)
        except BriefSynthesisError as exc:
            after = _synthesis_output_counts(env.store)
            observed.append(
                {
                    "case_id": case_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "cause": None if exc.__cause__ is None else str(exc.__cause__),
                    "provider_calls": env.provider.calls,
                    "forbidden_provider_calls": forbidden.calls,
                    "brief_residue_delta": after["brief"] - before["brief"],
                    "synthesis_receipt_residue_delta": (
                        after["brief_synthesis_receipt"] - before["brief_synthesis_receipt"]
                    ),
                    "prepared_synthesis_transaction_residue_delta": (
                        after["prepared_synthesis_transaction_receipt"]
                        - before["prepared_synthesis_transaction_receipt"]
                    ),
                }
            )
        else:
            raise AssertionError(f"negative case unexpectedly succeeded: {case_id}")

    return observed


async def run_acceptance(
    *,
    check_expected: bool = True,
    check_negative: bool = True,
) -> dict[str, Any]:
    result = await run_positive()
    projection = await positive_projection(result)
    assert_positive(result, projection)
    if check_expected:
        expected = load_compatibility_fixture(EXPECTED_NAME)
        if projection != expected["expected"]:
            raise AssertionError("P1D1 result differs from pinned expected artifact")
    if check_negative:
        negative = load_compatibility_fixture(NEGATIVE_NAME)
        if await run_negative_inventory() != negative["cases"]:
            raise AssertionError("P1D1 negative inventory differs from pinned artifact")
    return projection


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_supplied_wheel(path: Path, expected: str, *, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} wheel is missing: {path}")
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"{label} wheel SHA-256 mismatch: {actual}")


def _installed_from_exact_wheel(
    *,
    distribution_name: str,
    wheel: Path,
    import_path: Path,
    owned_relative_path: str,
) -> dict[str, str]:
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as exc:
        raise SystemExit(
            f"{distribution_name} is not installed from the supplied exact wheel"
        ) from exc
    direct_url_raw = distribution.read_text("direct_url.json")
    if direct_url_raw is None:
        raise SystemExit(f"{distribution_name} lacks exact local-wheel installation provenance")
    direct_url = json.loads(direct_url_raw)
    parsed = urlsplit(direct_url.get("url", ""))
    installed_from = Path(unquote(parsed.path)).resolve() if parsed.scheme == "file" else None
    if installed_from != wheel.resolve():
        raise SystemExit(
            f"{distribution_name} was not installed from the supplied exact wheel: {installed_from}"
        )
    wheel_sha256 = _sha256(wheel)
    archive_info = direct_url.get("archive_info")
    archive_hashes = archive_info.get("hashes") if isinstance(archive_info, dict) else None
    installed_archive_sha256 = (
        archive_hashes.get("sha256") if isinstance(archive_hashes, dict) else None
    )
    if installed_archive_sha256 is None and isinstance(archive_info, dict):
        legacy_hash = archive_info.get("hash")
        if isinstance(legacy_hash, str) and legacy_hash.startswith("sha256="):
            installed_archive_sha256 = legacy_hash.removeprefix("sha256=")
    if installed_archive_sha256 != wheel_sha256:
        raise SystemExit(
            f"{distribution_name} direct-url archive digest does not match the supplied exact wheel"
        )
    owned_files = {str(item): item for item in (distribution.files or ())}
    owned_file = owned_files.get(owned_relative_path)
    if owned_file is None or owned_file.hash is None:
        raise SystemExit(
            f"{distribution_name} RECORD does not own {owned_relative_path} with a hash"
        )
    expected_import = Path(distribution.locate_file(owned_file)).resolve()
    resolved_import = import_path.resolve()
    if resolved_import != expected_import:
        raise SystemExit(
            f"{distribution_name} import/resource is not its exact RECORD-owned file: "
            f"{resolved_import} != {expected_import}"
        )
    record_hash = owned_file.hash
    if record_hash.mode != "sha256":
        raise SystemExit(
            f"{distribution_name} RECORD uses unsupported hash mode for "
            f"{owned_relative_path}: {record_hash.mode}"
        )
    installed_digest = hashlib.sha256(resolved_import.read_bytes()).digest()
    installed_record_value = base64.urlsafe_b64encode(installed_digest).decode().rstrip("=")
    if installed_record_value != record_hash.value:
        raise SystemExit(
            f"{distribution_name} installed bytes do not match the RECORD hash for "
            f"{owned_relative_path}"
        )
    return {
        "distribution": distribution_name,
        "wheel": str(wheel.resolve()),
        "wheel_sha256": wheel_sha256,
        "installed_archive_sha256": installed_archive_sha256,
        "import_path": str(resolved_import),
        "record_path": owned_relative_path,
        "record_hash": str(record_hash),
        "installed_file_sha256": installed_digest.hex(),
    }


def _verify_installed_core(core_wheel: Path) -> dict[str, Any]:
    modules = {}
    for module_name, relative_path in (
        ("ace", "ace/__init__.py"),
        ("ace.application", "ace/application/__init__.py"),
        ("ace.core", "ace/core/__init__.py"),
        ("ace.intelligence", "ace/intelligence/__init__.py"),
    ):
        module = importlib.import_module(module_name)
        modules[module_name] = _installed_from_exact_wheel(
            distribution_name="ace-core",
            wheel=core_wheel,
            import_path=Path(module.__file__),
            owned_relative_path=relative_path,
        )
    return {
        "wheel": str(core_wheel.resolve()),
        "wheel_sha256": _sha256(core_wheel),
        "modules": modules,
    }


def _verify_installed_market(market_wheel: Path) -> dict[str, Any]:
    distribution = metadata.distribution("ace-ext-b2b-marketing")
    owned_json = sorted(
        str(item)
        for item in (distribution.files or ())
        if str(item).startswith("domain_packs/market_intelligence/") and str(item).endswith(".json")
    )
    if len(owned_json) != 25:
        raise SystemExit("ace-ext-b2b-marketing must RECORD-own exactly 25 Market JSON files")
    package_root = resources.files("domain_packs.market_intelligence")
    verified = []
    prefix = "domain_packs/market_intelligence/"
    for owned_relative_path in owned_json:
        package_relative_path = owned_relative_path.removeprefix(prefix)
        resource_path = package_root.joinpath(*Path(package_relative_path).parts)
        result = _installed_from_exact_wheel(
            distribution_name="ace-ext-b2b-marketing",
            wheel=market_wheel,
            import_path=Path(str(resource_path)),
            owned_relative_path=owned_relative_path,
        )
        verified.append(result)
    p1d1_resources = [
        item["record_path"]
        for item in verified
        if "/releases/v0_4_0/conformance/p1d1_" in f"/{item['record_path']}"
    ]
    if len(p1d1_resources) != 4:
        raise SystemExit("Market wheel does not RECORD-own all four P1D1 JSON artifacts")
    return {
        "wheel": str(market_wheel.resolve()),
        "wheel_sha256": _sha256(market_wheel),
        "record_owned_json_count": len(verified),
        "p1d1_resources": p1d1_resources,
        "manifest": next(
            item
            for item in verified
            if item["record_path"] == "domain_packs/market_intelligence/manifest.json"
        ),
    }


def _installed_origin(distribution_name: str) -> str | None:
    try:
        distribution = metadata.distribution(distribution_name)
        direct_url = distribution.read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None
    if direct_url is None:
        return None
    return json.loads(direct_url)["url"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-wheel", type=Path)
    parser.add_argument("--core-wheel-sha256", default=CORE_WHEEL_SHA256)
    parser.add_argument("--market-wheel", type=Path)
    parser.add_argument("--market-wheel-sha256")
    parser.add_argument("--emit-expected", action="store_true")
    parser.add_argument("--emit-negative-cases", action="store_true")
    args = parser.parse_args()
    artifact_bound = args.core_wheel is not None or args.market_wheel is not None
    if artifact_bound and (args.core_wheel is None or args.market_wheel is None):
        parser.error(
            "--core-wheel and --market-wheel are required together for artifact-bound acceptance"
        )
    artifact_verification = None
    if artifact_bound:
        assert args.core_wheel is not None and args.market_wheel is not None
        _verify_supplied_wheel(
            args.core_wheel,
            args.core_wheel_sha256,
            label="Core",
        )
        if args.market_wheel_sha256 is None:
            parser.error("--market-wheel-sha256 is required with --market-wheel")
        _verify_supplied_wheel(
            args.market_wheel,
            args.market_wheel_sha256,
            label="Market",
        )
        artifact_verification = {
            "core": _verify_installed_core(args.core_wheel),
            "market": _verify_installed_market(args.market_wheel),
        }
    if args.emit_negative_cases:
        print(json.dumps(asyncio.run(run_negative_inventory()), indent=2, sort_keys=True))
        return
    projection = asyncio.run(
        run_acceptance(
            check_expected=not args.emit_expected,
            check_negative=not args.emit_expected,
        )
    )
    if args.emit_expected:
        print(json.dumps(projection, indent=2, sort_keys=True))
        return
    print(
        json.dumps(
            {
                "status": "passed",
                "core_origin": str(Path(ace.__file__).resolve()),
                "core_distribution_origin": _installed_origin("ace-core"),
                "market_distribution_origin": _installed_origin("ace-ext-b2b-marketing"),
                "pack": projection["packs"]["v0_4_0"],
                "brief_id": projection["brief"]["resource_id"],
                "brief_digest": projection["brief"]["resource_digest"],
                "synthesis_receipt_id": projection["synthesis_receipt"]["receipt_id"],
                "provider_calls": projection["replay"]["provider_calls"],
                "artifact_verification": artifact_verification,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
