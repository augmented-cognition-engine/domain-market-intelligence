from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

import pytest
from test_market_intelligence_pack import (
    MANIFEST_PATH,
    NEGATIVE_CASES,
    NEGATIVE_CASES_PATH,
    PACK_ROOT,
    PRICE_MOVE_FIXTURE_PATH,
    PUBLIC_SOURCE_BOUNDARY_PATH,
    _apply_negative_case,
    _compiled_pack,
    _load_json,
    _parse_time,
    _prepared_binding,
    _prepared_observations_and_snapshots,
)

try:
    from ace.application import (
        DecisionOutcomeFeedbackResourceProjectionReader,
        DomainActivationAdmissionService,
        GovernedDestinationDeliveryService,
        PreparedDecisionFeedbackService,
        PreparedIntelligenceAdmissionError,
        PreparedIntelligenceLedgerService,
        bind_committed_activation,
        delivery_payload_digest,
    )
    from ace.core import (
        AuthenticatedRuntimeContextV1Alpha1,
        CapabilityArtifactIdentityV1Alpha1,
        DecisionActionDisposition,
        DecisionDisposition,
        DecisionIntentV1Alpha1,
        GovernedActionAuthorizationProjection,
        GovernedOperationBindingV1Alpha1,
        GovernedStateCommitRequestV1,
        GovernedStateHeadPreconditionV1Alpha1,
        GovernedStateHeadV1,
        ImmutableRecordPersistenceError,
        ImmutableRecordReplayConflict,
        OutcomeIntentV1Alpha1,
        ReceiptReferenceV1Alpha1,
        ResolvedApprovalReceiptV1,
        ResolvedAuthorityGrantV1,
    )
    from ace.core.agent_composition import ExactArtifactReferenceV1Alpha1
    from ace.core.external_operations import (
        DeliveryState,
        DestinationDefinitionV1Alpha1,
        DestinationDeliveryIntentV1Alpha1,
        DestinationLifecycle,
        DestinationPolicyCoordinateV1Alpha1,
        DestinationPolicyKind,
        DestinationRevisionV1Alpha1,
        ExternalOperation,
        ExternalOperationAuthorityV1Alpha1,
        exact_external_reference,
    )
    from ace.core.runtime_use import (
        AuthorityUseReceiptV1Alpha1,
        CapabilityUseReceiptV1Alpha1,
        capability_state_ref_for_artifact,
    )
    from ace.intelligence import (
        BriefV1Alpha1,
        CitationV1Alpha1,
        GroundedClaimV1Alpha1,
        IntelligenceRecordKind,
        IntelligenceResourceKind,
        IntelligenceResourceMode,
        IntelligenceResourceQueryV1Alpha1,
        LineageReferenceV1Alpha1,
        LineageRelation,
        LineageResourceKind,
        PreparedResourceAdmissionV1Alpha1,
        SignalV1Alpha1,
        SynthesisModuleV1,
        detect_numeric_shift,
        deterministic_resource_order,
        resource_reference,
        route_shift_as_signal,
    )
    from ace.testing import (
        InMemoryImmutableRecordStore,
        exercise_prepared_ledger_restart,
    )
    from ace.testing.reference_external_destination import (
        ReferenceExternalDestinationAdapter,
    )
    from ace_market_builder import (
        ApprovedMarketClaimV1Alpha1,
        MarketDirectionPackageV1Alpha1,
        prepare_market_direction_delivery,
    )
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "ace" or exc.name.startswith(("ace.", "pydantic"))):
        pytest.skip(
            "the exact ACE Core P1C1 wheel is required for Market consumer conformance",
            allow_module_level=True,
        )
    raise


DURABLE_EXPECTED_PATH = PACK_ROOT / "conformance" / "p1c_durable_price_move_expected.json"
DERIVATION_KEY = "derivation:market-intelligence:p1c:prepared-price-move:v1"
ATTENTION_EVALUATED_AT = "2026-08-13T18:06:00Z"
HISTORICAL_CUTOFF = "2026-08-13T18:00:59Z"
EXACT_CORE_WHEEL_SHA256 = "07f5134488f7de16800aae290bb05284fdffe8fb679353b0b3f9771630ad302c"
P1C_RECORD_KINDS = (
    IntelligenceRecordKind.OBSERVATION,
    IntelligenceRecordKind.ENTITY_SNAPSHOT,
    IntelligenceRecordKind.SHIFT,
    IntelligenceRecordKind.SIGNAL,
    IntelligenceRecordKind.BRIEF,
    IntelligenceRecordKind.ATTENTION_DISPOSITION,
)

OUTCOME_POLICY_ID = "competitive_price_move_usefulness"
OUTCOME_ACTOR = "principal:single-user-owner"


def _governed_head(
    *,
    product_id: str,
    state_kind: str,
    state_id: str,
    updated_at: datetime,
) -> GovernedStateHeadV1:
    return GovernedStateHeadV1(
        state_kind=state_kind,
        product_id=product_id,
        state_id=state_id,
        sequence=1,
        revision_id=f"{state_kind}_revision:{state_id}",
        commit_receipt_id=f"governed_state_commit:{state_id}",
        updated_at=updated_at,
    )


class _ProposalOnlyActionAuthorizer:
    def __init__(self, *, current_heads: tuple[GovernedStateHeadV1, ...]) -> None:
        self.current_heads = current_heads
        self.requests = []

    async def authorize_action(self, request):
        self.requests.append(request)
        required = {
            (item.state_kind, item.product_id, item.state_id): item
            for item in request.required_state_preconditions
        }
        for head in self.current_heads:
            precondition = GovernedStateHeadPreconditionV1Alpha1.from_head(head)
            required[(precondition.state_kind, precondition.product_id, precondition.state_id)] = (
                precondition
            )
        return GovernedActionAuthorizationProjection(
            authorization_ref=ReceiptReferenceV1Alpha1(
                receipt_id=f"action_authorization:{request.request_id}",
                receipt_digest=str(request.request_digest),
            ),
            authorized_at=request.requested_at + timedelta(seconds=1),
            state_preconditions=tuple(required.values()),
        )


class _ExactPackageDestinationAuthority:
    def __init__(
        self,
        *,
        adapter: ReferenceExternalDestinationAdapter,
        store: InMemoryImmutableRecordStore,
        product_id: str,
        updated_at: datetime,
    ) -> None:
        self.adapter = adapter
        self.store = store
        self.product_id = product_id
        self.updated_at = updated_at
        self.calls = []

    async def resolve(
        self,
        *,
        authenticated_context,
        operation,
        use_subject,
        destination_revision,
        recipient_ref,
        evaluated_at,
    ) -> ExternalOperationAuthorityV1Alpha1:
        del recipient_ref
        if operation is not ExternalOperation.DELIVERY or destination_revision is None:
            raise PermissionError("only exact direction-package delivery is authorized")
        self.calls.append((use_subject, exact_external_reference(destination_revision)))
        artifact = self.adapter.artifact_identity
        capability_state_id = capability_state_ref_for_artifact(artifact)
        grant_id = "authority_grant:market-direction-package-delivery"
        configuration_id = "external_operation_configuration:market-direction-mailbox"
        heads = tuple(
            _governed_head(
                product_id=self.product_id,
                state_kind=kind,
                state_id=state_id,
                updated_at=self.updated_at,
            )
            for kind, state_id in (
                ("capability_state", capability_state_id),
                ("authority_grant", grant_id),
                ("external_operation_configuration", configuration_id),
            )
        )
        for head in heads:
            self.store.set_governed_state_head(head)
        capability_head, grant_head, _ = heads
        capability = CapabilityUseReceiptV1Alpha1(
            product_id=self.product_id,
            actor_ref=authenticated_context.actor_ref,
            authenticated_context=authenticated_context,
            use_subject_ref=use_subject.artifact_id,
            use_subject_digest=use_subject.artifact_digest,
            operation=operation.value,
            artifact=artifact,
            capability_state_ref=capability_state_id,
            configuration_ref=configuration_id,
            evaluated_at=evaluated_at,
            resolved_at=evaluated_at,
            state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(
                capability_head
            ),
        )
        authority = AuthorityUseReceiptV1Alpha1(
            product_id=self.product_id,
            actor_ref=authenticated_context.actor_ref,
            authenticated_context=authenticated_context,
            use_subject_ref=use_subject.artifact_id,
            use_subject_digest=use_subject.artifact_digest,
            operation=operation.value,
            authority=operation.value,
            grant_ref=grant_id,
            grant_hash="d" * 64,
            evaluated_at=evaluated_at,
            expires_at=authenticated_context.expires_at,
            state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(grant_head),
        )
        return ExternalOperationAuthorityV1Alpha1(
            operation=operation,
            product_id=self.product_id,
            actor_ref=authenticated_context.actor_ref,
            authenticated_context=authenticated_context,
            use_subject=use_subject,
            destination_revision=exact_external_reference(destination_revision),
            capability_use=capability,
            authority_use=authority,
            current_heads=tuple(
                GovernedStateHeadPreconditionV1Alpha1.from_head(head) for head in heads
            ),
            evaluated_at=evaluated_at,
        )


class _MemoryGovernedStateStore:
    """Minimal Core-port test double reused only for public activation admission."""

    def __init__(self) -> None:
        self.heads: dict[tuple[str, str, str], Any] = {}
        self.revisions: dict[tuple[str, str], Any] = {}
        self.receipts: dict[tuple[str, str], Any] = {}

    async def commit(self, request: GovernedStateCommitRequestV1):
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


class _ExactMarketAuthority:
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


async def _committed_binding(compiled, fixture: dict[str, Any], boundary: dict[str, Any]):
    prepared = _prepared_binding(compiled, fixture, boundary)
    state_store = _MemoryGovernedStateStore()
    admitted = await DomainActivationAdmissionService(
        store=state_store,
        authority=_ExactMarketAuthority(),
    ).admit(
        prepared.revision,
        expected_head_revision_id=None,
        committed_at=prepared.revision.occurred_at + timedelta(seconds=1),
    )
    reloaded = await DomainActivationAdmissionService(
        store=state_store,
        authority=_ExactMarketAuthority(),
    ).reload(
        product_id=prepared.revision.spec.product_id,
        activation_key=prepared.revision.spec.activation_key,
    )
    assert reloaded == admitted
    return (
        prepared,
        bind_committed_activation(pack=compiled, committed=reloaded),
        state_store,
    )


def _prepared_intelligence_context(
    *,
    binding,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    observations, snapshots = _prepared_observations_and_snapshots(
        binding=binding,
        fixture=fixture,
    )
    shift = detect_numeric_shift(
        binding=binding,
        detector_id=fixture["pack"]["detector_id"],
        baseline=snapshots[0],
        current=snapshots[1],
        detected_at=_parse_time(fixture["scenario"]["shift_detected_at"]),
    )
    assert shift is not None
    signal = route_shift_as_signal(
        binding=binding,
        detector_id=fixture["pack"]["detector_id"],
        shift=shift,
        detected_at=_parse_time(fixture["scenario"]["signal_detected_at"]),
    )
    return {
        "observations": tuple(observations),
        "entity_snapshots": tuple(snapshots),
        "shift": shift,
        "signal": signal,
    }


def _manual_p1b_brief(
    *,
    binding,
    compiled,
    fixture: dict[str, Any],
    context: dict[str, Any],
) -> BriefV1Alpha1:
    observations = context["observations"]
    shift = context["shift"]
    signal = context["signal"]
    synthesis_ir = next(
        module
        for module in compiled.modules
        if module.contract == "ace.intelligence.synthesis/v1alpha1"
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
        for observation, item in zip(observations, fixture["snapshots"], strict=True)
    )
    expected_brief = fixture["expected_prepared_brief"]
    claim = GroundedClaimV1Alpha1(
        statement=expected_brief["claim"],
        citation_ids=tuple(citation.citation_id for citation in citations),
        confidence=expected_brief["confidence"],
    )
    brief = BriefV1Alpha1(
        product_id=fixture["scenario"]["product_id"],
        mode=IntelligenceResourceMode.PREPARED,
        activation_revision=binding.reference,
        as_of=_parse_time(fixture["scenario"]["brief_as_of"]),
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
        title=expected_brief["title"],
        executive_summary=expected_brief["executive_summary"],
        body_markdown=expected_brief["body_markdown"],
        generated_at=_parse_time(fixture["scenario"]["brief_generated_at"]),
        citations=citations,
        claims=(claim,),
    )
    return brief


def _prepared_derivation(
    *,
    binding,
    compiled,
    fixture: dict[str, Any],
) -> dict[str, Any]:
    context = _prepared_intelligence_context(
        binding=binding,
        fixture=fixture,
    )
    brief = _manual_p1b_brief(
        binding=binding,
        compiled=compiled,
        fixture=fixture,
        context=context,
    )
    return {
        **context,
        "brief": brief,
    }


def _batch(binding, derivation: dict[str, Any]) -> PreparedResourceAdmissionV1Alpha1:
    resources = (
        *derivation["observations"],
        *derivation["entity_snapshots"],
        derivation["shift"],
        derivation["signal"],
        derivation["brief"],
    )
    return PreparedResourceAdmissionV1Alpha1(
        derivation_key=DERIVATION_KEY,
        product_id=binding.prepared_binding.revision.spec.product_id,
        activation_revision=binding.prepared_binding.reference,
        pack=binding.prepared_binding.revision.spec.pack,
        observations=derivation["observations"],
        entity_snapshots=derivation["entity_snapshots"],
        shift=derivation["shift"],
        signal=derivation["signal"],
        brief=derivation["brief"],
        processing_order=deterministic_resource_order(resources),
        attention_evaluated_at=_parse_time(ATTENTION_EVALUATED_AT),
    )


def _pre_brief_batch(
    binding,
    context: dict[str, Any],
    *,
    derivation_key: str = DERIVATION_KEY,
    attention_evaluated_at: str = ATTENTION_EVALUATED_AT,
) -> PreparedResourceAdmissionV1Alpha1:
    resources = (
        *context["observations"],
        *context["entity_snapshots"],
        context["shift"],
        context["signal"],
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
        brief=None,
        processing_order=deterministic_resource_order(resources),
        attention_evaluated_at=_parse_time(attention_evaluated_at),
    )


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _identity_projection(batch, admission, binding, historical: dict[str, Any]):
    transaction = admission.transaction_receipt
    activation = binding.prepared_binding.reference
    activation_commit = binding.commit_receipt
    spec = binding.prepared_binding.revision.spec
    overlay = spec.overlay
    pack = binding.prepared_binding.pack
    source_mapping = batch.observations[0].source_mapping
    assert source_mapping is not None
    resource_by_id = {str(resource.resource_id): resource for resource in admission.resources}
    resources = []
    for record in transaction.records[:-1]:
        resource = resource_by_id[record.record_key]
        exact = resource_reference(resource)
        resources.append(
            {
                "processing_order": record.processing_order,
                "resource_kind": exact.resource_kind.value,
                "resource_id": exact.resource_id,
                "resource_digest": exact.resource_digest,
                "storage_id": record.storage_id,
                "material_hash": record.material_hash,
                "as_of": _iso(exact.as_of),
                "available_at": _iso(exact.available_at),
            }
        )
    attention = admission.attention_receipt
    attention_record = transaction.records[-1]
    return {
        "pack": {
            "compiled_pack_id": pack.compiled_pack_id,
            "pack_digest": pack.pack_digest,
            "source_mapping_module_id": source_mapping.module_id,
            "source_mapping_module_digest": source_mapping.module_digest,
            "source_mapping_id": source_mapping.mapping_id,
            "source_mapping_digest": source_mapping.mapping_digest,
        },
        "overlay": {
            "compiled_overlay_id": overlay.compiled_overlay_id,
            "overlay_digest": overlay.overlay_digest,
        },
        "activation": {
            "activation_id": activation.activation_id,
            "spec_id": spec.spec_id,
            "spec_hash": spec.spec_hash,
            "revision_id": activation.revision_id,
            "revision_digest": activation.revision_digest,
            "core_commit_receipt_id": activation_commit.receipt_id,
            "core_commit_receipt_hash": activation_commit.receipt_hash,
            "authority_stage": binding.authority_stage,
            "live_authority": binding.live_authority,
        },
        "batch": {
            "derivation_key": batch.derivation_key,
            "batch_id": batch.batch_id,
            "batch_digest": batch.batch_digest,
            "attention_evaluated_at": _iso(batch.attention_evaluated_at),
            "processing_order": [reference.resource_id for reference in batch.processing_order],
        },
        "transaction": {
            "transaction_id": transaction.transaction_id,
            "request_hash": transaction.request_hash,
            "receipt_id": transaction.receipt_id,
            "receipt_hash": transaction.receipt_hash,
            "record_count": len(transaction.records),
            "committed_at": _iso(transaction.committed_at),
        },
        "resources": resources,
        "attention": {
            "receipt_id": attention.receipt_id,
            "receipt_digest": attention.receipt_digest,
            "storage_id": attention_record.storage_id,
            "material_hash": attention_record.material_hash,
            "disposition": attention.disposition.value,
            "routing_rule_id": attention.routing_rule_id,
            "persona_ids": list(attention.persona_ids),
            "brief_template_id": attention.brief_template_id,
            "evaluated_at": _iso(attention.evaluated_at),
            "delivery_authority": attention.delivery_authority,
        },
        "historical_isolation": historical,
    }


async def _read_historical(service, *, product_id: str) -> dict[str, Any]:
    cutoff = _parse_time(HISTORICAL_CUTOFF)
    result: dict[str, list[str]] = {}
    for kind in P1C_RECORD_KINDS:
        values = await service.read_as_of(
            product_id=product_id,
            mode=IntelligenceResourceMode.PREPARED,
            kind=kind,
            available_at=cutoff,
        )
        result[kind.value] = [
            str(getattr(item, "resource_id", getattr(item, "receipt_id", None))) for item in values
        ]
    return {"available_at_cutoff": HISTORICAL_CUTOFF, "record_ids": result}


@pytest.mark.asyncio
async def test_durable_prepared_price_move_matches_pinned_expected_artifact() -> None:
    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    prepared, binding, _ = await _committed_binding(compiled, fixture, boundary)
    derivation = _prepared_derivation(
        binding=prepared,
        compiled=compiled,
        fixture=fixture,
    )
    batch = _batch(binding, derivation)
    store = InMemoryImmutableRecordStore()
    first_service = PreparedIntelligenceLedgerService(binding=binding, store=store)
    restarted_service = PreparedIntelligenceLedgerService(binding=binding, store=store)

    conformance = await exercise_prepared_ledger_restart(
        first_service=first_service,
        restarted_service=restarted_service,
        batch=batch,
    )
    admission = conformance.first
    assert conformance.first == conformance.exact_replay
    assert conformance.first == conformance.restarted_replay
    assert admission.mode is IntelligenceResourceMode.PREPARED
    assert admission.authority_stage == "committed"
    assert admission.live_authority is False
    assert all(
        resource.mode is IntelligenceResourceMode.PREPARED for resource in admission.resources
    )
    assert admission.attention_receipt.mode is IntelligenceResourceMode.PREPARED
    assert admission.attention_receipt.delivery_authority is False
    assert len(store.records) == 8
    assert len(store.receipts) == 1

    expected_ids = fixture["expected_resource_ids"]
    assert derivation["shift"].resource_id == expected_ids["shift"]["resource_id"]
    assert derivation["signal"].resource_id == expected_ids["signal"]["resource_id"]
    assert derivation["brief"].resource_id == expected_ids["brief"]["resource_id"]

    historical = await _read_historical(
        restarted_service,
        product_id=fixture["scenario"]["product_id"],
    )
    expected = _load_json(DURABLE_EXPECTED_PATH)
    assert expected["platform_dependency"]["ace_core_wheel_sha256"] == (EXACT_CORE_WHEEL_SHA256)
    assert _identity_projection(batch, admission, binding, historical) == expected["expected"]


@pytest.mark.asyncio
async def test_current_pack_closes_direction_handoff_outcome_as_proposal_only() -> None:
    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    prepared, binding, state_store = await _committed_binding(
        compiled,
        fixture,
        boundary,
    )
    derivation = _prepared_derivation(
        binding=prepared,
        compiled=compiled,
        fixture=fixture,
    )
    store = InMemoryImmutableRecordStore()
    admission = await PreparedIntelligenceLedgerService(
        binding=binding,
        store=store,
    ).admit(_batch(binding, derivation))
    brief = derivation["brief"]
    brief_record = next(
        record
        for record in store.records.values()
        if record.record_kind == IntelligenceRecordKind.BRIEF.value
        and record.record_key == brief.resource_id
    )
    assert brief_record.reference() in admission.transaction_receipt.records

    product_id = fixture["scenario"]["product_id"]
    authenticated_at = brief_record.available_at - timedelta(minutes=1)
    auth = AuthenticatedRuntimeContextV1Alpha1(
        product_id=product_id,
        actor_ref=OUTCOME_ACTOR,
        authentication_receipt_ref="authentication:market-v1-outcome-loop",
        authentication_receipt_digest="sha256:" + "9" * 64,
        authenticated_at=authenticated_at,
        expires_at=authenticated_at + timedelta(hours=1),
    )
    decision_at = brief_record.available_at + timedelta(minutes=1)
    operation_artifact = CapabilityArtifactIdentityV1Alpha1(
        capability="governed_prepared_feedback",
        contract="ace.core.governed-action-authorizer/v1alpha1",
        implementation_id="provider-free-market-v1-acceptance",
        implementation_version="1.0.0",
        artifact_digest="sha256:" + "6" * 64,
    )
    operation_configuration = _governed_head(
        product_id=product_id,
        state_kind="governed_operation_configuration",
        state_id="governed_operation_configuration:market-outcome-loop",
        updated_at=authenticated_at,
    )
    capability_head = _governed_head(
        product_id=product_id,
        state_kind="capability_state",
        state_id="capability_state:market-outcome-loop",
        updated_at=authenticated_at,
    )
    authority_head = _governed_head(
        product_id=product_id,
        state_kind="authority_grant",
        state_id="authority_grant:market-outcome-loop",
        updated_at=authenticated_at,
    )
    activation_head = state_store.heads[
        (
            binding.commit_receipt.state_kind,
            product_id,
            binding.commit_receipt.state_id,
        )
    ]
    for head in (activation_head, operation_configuration, capability_head, authority_head):
        store.set_governed_state_head(head)
    authorizer = _ProposalOnlyActionAuthorizer(
        current_heads=(operation_configuration, capability_head, authority_head),
    )
    feedback = PreparedDecisionFeedbackService(
        binding=binding,
        record_store=store,
        governed_store=state_store,
        authority=_ExactMarketAuthority(),
        authorizer=authorizer,
        operation_binding=GovernedOperationBindingV1Alpha1(
            product_id=product_id,
            artifact=operation_artifact,
            configuration_ref=operation_configuration.state_id,
            authority="govern_prepared_feedback",
            grant_ref=authority_head.state_id,
            state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(
                operation_configuration
            ),
        ),
        clock=lambda: decision_at,
    )
    decision = await feedback.record_decision(
        DecisionIntentV1Alpha1(
            product_id=product_id,
            authenticated_context=auth,
            subject=brief_record.reference(),
            actor_role_ref="competitive_intelligence_analyst",
            decision_type="competitive_response",
            disposition=DecisionDisposition.ACCEPT,
            action_disposition=DecisionActionDisposition.NO_ACTION,
            rationale="Use the cited Brief as the exact subject of a bounded positioning direction.",
            decided_at=decision_at,
        ),
        policy_id=OUTCOME_POLICY_ID,
    )

    observation = derivation["observations"][1]
    package_at = decision.authorization.authorized_at + timedelta(minutes=1)
    direction = MarketDirectionPackageV1Alpha1(
        product_id=product_id,
        source_brief=ExactArtifactReferenceV1Alpha1(
            artifact_id=str(brief.resource_id),
            artifact_digest=str(brief.resource_digest),
            artifact_contract=brief.contract,
        ),
        decision=ExactArtifactReferenceV1Alpha1(
            artifact_id=str(decision.decision.decision_id),
            artifact_digest=str(decision.decision.decision_digest),
            artifact_contract=decision.decision.contract,
        ),
        objective="Prepare a cited page-story direction for the accepted Terra price response.",
        audience=("AI platform evaluation leaders",),
        story_architecture=(
            "Lead with the verified recorded price move",
            "Explain the buyer implication",
            "Close with evidence and limits",
        ),
        content_hierarchy=("Hero", "Price comparison", "Implications", "Evidence"),
        approved_claims=(
            ApprovedMarketClaimV1Alpha1(
                claim_id="claim:recorded-terra-input-price-move",
                statement=brief.claims[0].statement,
                citations=(
                    ExactArtifactReferenceV1Alpha1(
                        artifact_id=str(observation.resource_id),
                        artifact_digest=str(observation.resource_digest),
                        artifact_contract=observation.contract,
                    ),
                ),
                approval_ref="approval:market-v1-recorded-claim",
                limitations=(
                    "Recorded publication evidence; current network pricing remains unverified.",
                ),
            ),
        ),
        constraints=(
            "Do not imply independent corroboration",
            "Keep every numeric claim cited",
        ),
        open_questions=("Which customer proof may be added after separate review?",),
        required_assets=("Approved product marks", "Accessible price comparison component"),
        prepared_at=package_at,
    )
    prepared_delivery = prepare_market_direction_delivery(
        direction,
        source_manifest=ExactArtifactReferenceV1Alpha1(
            artifact_id="stage_manifest:market-v1-direction",
            artifact_digest="sha256:" + "7" * 64,
            artifact_contract="ace.core.stage-run-manifest/v1alpha1",
        ),
        target_ref="ac5_delivery_gate:market-v1-direction",
        prepared_at=package_at,
    )
    destination_definition = DestinationDefinitionV1Alpha1(
        product_id=product_id,
        destination_key="reference-direction-mailbox",
        adapter_contract="ace.core.external-destination-adapter/v1alpha1",
        protocol_refs=("protocol:digest-mailbox-v1",),
        capability_refs=("delivery",),
        recipient_binding_kind="opaque_recipient_ref",
    )
    destination = DestinationRevisionV1Alpha1(
        definition=exact_external_reference(destination_definition),
        sequence=1,
        lifecycle=DestinationLifecycle.ACTIVE,
        policies=tuple(
            DestinationPolicyCoordinateV1Alpha1(
                kind=kind,
                policy_ref=f"policy:market-direction:{kind.value}",
                state_id=f"destination_policy:market-direction:{kind.value}",
                material_digest="sha256:" + f"{index + 1:x}" * 64,
            )
            for index, kind in enumerate(DestinationPolicyKind)
        ),
        revised_at=package_at,
    )
    delivery_at = package_at + timedelta(minutes=1)
    adapter = ReferenceExternalDestinationAdapter(clock=lambda: delivery_at)
    delivery_authority = _ExactPackageDestinationAuthority(
        adapter=adapter,
        store=store,
        product_id=product_id,
        updated_at=package_at,
    )
    delivery_intent = DestinationDeliveryIntentV1Alpha1(
        product_id=product_id,
        authenticated_context=auth,
        prepared_handoff=ExactArtifactReferenceV1Alpha1(
            artifact_id=str(prepared_delivery.package_id),
            artifact_digest=str(prepared_delivery.package_digest),
            artifact_contract=prepared_delivery.contract,
        ),
        destination_revision=exact_external_reference(destination),
        recipient_ref="recipient:reference-market-direction-mailbox",
        payload_artifacts=prepared_delivery.artifacts,
        payload_digest=delivery_payload_digest(prepared_delivery.artifacts),
        idempotency_key="delivery:market-v1-direction",
        retry_policy_ref="retry:lookup-first",
        cancellation_ref="cancel:market-v1-direction",
        requested_at=delivery_at,
        expires_at=delivery_at + timedelta(minutes=10),
    )
    delivered = await GovernedDestinationDeliveryService(
        store=store,
        authority=delivery_authority,
        adapter=adapter,
        destination=destination,
        clock=lambda: delivery_at,
    ).deliver(prepared=prepared_delivery, intent=delivery_intent)
    assert delivered.result.state is DeliveryState.ACKNOWLEDGED
    assert delivered.result.acknowledgment is not None
    assert delivered.result.acknowledgment.truth_proven is False
    assert delivered.result.acknowledgment.downstream_execution_proven is False
    assert len(delivery_authority.calls) == 2

    outcome_observed_at = delivery_at + timedelta(minutes=1)
    outcome_recorded_at = outcome_observed_at + timedelta(minutes=1)
    outcome = await feedback.record_outcome(
        OutcomeIntentV1Alpha1(
            product_id=product_id,
            authenticated_context=auth,
            decision=decision.record,
            outcome_type="decision_usefulness",
            measure_id="analyst_usefulness",
            value_json='"useful"',
            observed_at=outcome_observed_at,
            recorded_at=outcome_recorded_at,
        ),
        policy_id=OUTCOME_POLICY_ID,
    )
    proposal = await feedback.propose_feedback(
        outcome.record,
        policy_id=OUTCOME_POLICY_ID,
        proposed_at=outcome_recorded_at + timedelta(minutes=1),
    )
    effective = await feedback.effective_policy(OUTCOME_POLICY_ID)
    assert proposal.proposal.intent.proposed_value == 0.55
    assert proposal.live_effect is False
    assert effective.value == 0.5
    assert effective.state is None
    assert effective.commit_receipt is None

    projection_time = proposal.authorization.authorized_at
    projected = await DecisionOutcomeFeedbackResourceProjectionReader(
        store=store,
        degrade_unsupported=False,
    ).read(
        query=IntelligenceResourceQueryV1Alpha1(
            authenticated_context=auth,
            product_id=product_id,
            authority_grant_ref="authority_grant:market-v1-resource-read",
            resource_kinds=(
                IntelligenceResourceKind.DECISION,
                IntelligenceResourceKind.OUTCOME,
                IntelligenceResourceKind.FEEDBACK,
            ),
            subject_refs=(),
            as_of=projection_time,
            available_at=projection_time,
            page_size=20,
        ),
        after=None,
        limit=20,
    )
    assert {item.reference.resource_kind for item in projected.records} == {
        IntelligenceResourceKind.DECISION,
        IntelligenceResourceKind.OUTCOME,
        IntelligenceResourceKind.FEEDBACK,
    }
    assert not projected.degraded_reason_refs
    assert direction.source_brief.artifact_id == brief.resource_id
    assert direction.decision.artifact_id == decision.decision.decision_id
    assert prepared_delivery.external_send_occurred is False
    assert delivered.result.result_id is not None
    assert delivered.result.result_digest is not None
    assert outcome.outcome.intent.decision == decision.record
    assert proposal.proposal.intent.outcome == outcome.record


@pytest.mark.asyncio
@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda case: case["case_id"])
async def test_declared_negative_vectors_leave_no_durable_residue(
    case: dict[str, Any],
) -> None:
    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    prepared, binding, _ = await _committed_binding(compiled, fixture, boundary)
    mutated = _apply_negative_case(fixture, case)
    store = InMemoryImmutableRecordStore()
    service = PreparedIntelligenceLedgerService(binding=binding, store=store)

    with pytest.raises(ValueError, match=case["expected_error_pattern"]):
        derivation = _prepared_derivation(
            binding=prepared,
            compiled=compiled,
            fixture=mutated,
        )
        await service.admit(_batch(binding, derivation))

    assert store.records == {}
    assert store.receipts == {}


@pytest.mark.asyncio
async def test_interrupted_atomic_admission_leaves_no_durable_residue() -> None:
    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    prepared, binding, _ = await _committed_binding(compiled, fixture, boundary)
    batch = _batch(
        binding,
        _prepared_derivation(
            binding=prepared,
            compiled=compiled,
            fixture=fixture,
        ),
    )
    store = InMemoryImmutableRecordStore(fail_after_records=4)

    with pytest.raises(ImmutableRecordPersistenceError, match="simulated interruption"):
        await PreparedIntelligenceLedgerService(binding=binding, store=store).admit(batch)

    assert store.records == {}
    assert store.receipts == {}


def _foreign_compiled_pack():
    manifest = deepcopy(_load_json(MANIFEST_PATH))
    manifest["metadata"]["version"] = "0.3.1-foreign"
    from ace.intelligence.packs import compile_pack_document

    return compile_pack_document(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
        {
            resource["path"]: (PACK_ROOT / resource["path"]).read_bytes()
            for resource in manifest["resources"]
        },
    )


def _lineage_mismatched_batch(batch):
    original = batch.signal.lineage[0]
    mismatched = LineageReferenceV1Alpha1.model_validate(
        {
            **original.model_dump(mode="python"),
            "resource_as_of": original.resource_as_of - timedelta(seconds=1),
        }
    )
    signal_payload = batch.signal.model_dump(
        mode="python", exclude={"resource_id", "resource_digest"}
    )
    signal_payload["lineage"] = (mismatched,)
    changed_signal = SignalV1Alpha1.model_validate(signal_payload)
    resources = (
        *batch.observations,
        *batch.entity_snapshots,
        batch.shift,
        changed_signal,
        batch.brief,
    )
    payload = batch.model_dump(mode="python", exclude={"batch_id", "batch_digest"})
    payload["signal"] = changed_signal
    payload["processing_order"] = deterministic_resource_order(resources)
    return PreparedResourceAdmissionV1Alpha1.model_validate(payload)


@pytest.mark.asyncio
async def test_host_boundary_negatives_fail_closed_without_new_residue() -> None:
    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    prepared, binding, _ = await _committed_binding(compiled, fixture, boundary)
    batch = _batch(
        binding,
        _prepared_derivation(
            binding=prepared,
            compiled=compiled,
            fixture=fixture,
        ),
    )

    foreign_activation_fixture = deepcopy(fixture)
    foreign_activation_fixture["scenario"]["activation_key"] = "market_intelligence_foreign"
    foreign_activation = _prepared_binding(compiled, foreign_activation_fixture, boundary).reference
    foreign_pack = _prepared_binding(_foreign_compiled_pack(), fixture, boundary).revision.spec.pack

    foreign_pack_payload = batch.model_dump(mode="python", exclude={"batch_id", "batch_digest"})
    foreign_pack_payload["pack"] = foreign_pack

    rejected_batches = (
        batch.model_copy(update={"activation_revision": foreign_activation}),
        PreparedResourceAdmissionV1Alpha1.model_validate(foreign_pack_payload),
        _lineage_mismatched_batch(batch),
    )
    expected_patterns = (
        "resource-admission batch failed exact revalidation",
        "exact committed Pack IR",
        "lineage target identity, digest, as-of, or availability does not match",
    )
    for rejected, pattern in zip(rejected_batches, expected_patterns, strict=True):
        store = InMemoryImmutableRecordStore()
        service = PreparedIntelligenceLedgerService(binding=binding, store=store)
        with pytest.raises(PreparedIntelligenceAdmissionError, match=pattern):
            await service.admit(rejected)
        assert store.records == {}
        assert store.receipts == {}

    store = InMemoryImmutableRecordStore()
    service = PreparedIntelligenceLedgerService(binding=binding, store=store)
    first = await service.admit(batch)
    before_records = dict(store.records)
    before_receipts = dict(store.receipts)

    with pytest.raises(PreparedIntelligenceAdmissionError, match="product scope"):
        await service.read_as_of(
            product_id="product:foreign-market-conformance",
            mode=IntelligenceResourceMode.PREPARED,
            kind=IntelligenceRecordKind.OBSERVATION,
            available_at=batch.attention_evaluated_at,
        )

    divergent_payload = batch.model_dump(mode="python", exclude={"batch_id", "batch_digest"})
    divergent_payload["attention_evaluated_at"] = batch.attention_evaluated_at + timedelta(
        seconds=1
    )
    divergent = PreparedResourceAdmissionV1Alpha1.model_validate(divergent_payload)
    with pytest.raises(ImmutableRecordReplayConflict, match="different material"):
        await service.admit(divergent)

    for kind in IntelligenceRecordKind:
        assert (
            await service.read_as_of(
                product_id=batch.product_id,
                mode=IntelligenceResourceMode.LIVE,
                kind=kind,
                available_at=batch.attention_evaluated_at,
            )
            == ()
        )
        assert (
            await service.count_as_of(
                product_id=batch.product_id,
                mode=IntelligenceResourceMode.LIVE,
                kind=kind,
                available_at=batch.attention_evaluated_at,
            )
            == 0
        )

    assert first.live_authority is False
    assert first.attention_receipt.delivery_authority is False
    assert store.records == before_records
    assert store.receipts == before_receipts


def test_durable_expected_artifact_is_declared_by_the_negative_fixture() -> None:
    negative = _load_json(NEGATIVE_CASES_PATH)
    expected = _load_json(DURABLE_EXPECTED_PATH)
    assert negative["fixture_id"] == "p1_price_move_negative_cases"
    assert expected["artifact_scope"] == "durable_prepared_conformance_expected"
    assert expected["platform_dependency"]["production_adapter_evidence_owner"] == ("ACE Platform")
