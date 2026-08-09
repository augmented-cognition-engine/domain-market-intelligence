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
        DomainActivationAdmissionService,
        PreparedIntelligenceAdmissionError,
        PreparedIntelligenceLedgerService,
        bind_committed_activation,
    )
    from ace.core import (
        GovernedStateCommitRequestV1,
        GovernedStateHeadV1,
        ImmutableRecordPersistenceError,
        ImmutableRecordReplayConflict,
        ResolvedApprovalReceiptV1,
        ResolvedAuthorityGrantV1,
    )
    from ace.intelligence import (
        BriefV1Alpha1,
        CitationV1Alpha1,
        GroundedClaimV1Alpha1,
        IntelligenceRecordKind,
        IntelligenceResourceMode,
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
except ModuleNotFoundError as exc:
    if exc.name is not None and (
        exc.name == "ace" or exc.name.startswith(("ace.", "pydantic"))
    ):
        pytest.skip(
            "the exact ACE Core P1C1 wheel is required for Market consumer conformance",
            allow_module_level=True,
        )
    raise


DURABLE_EXPECTED_PATH = (
    PACK_ROOT / "conformance" / "p1c_durable_price_move_expected.json"
)
DERIVATION_KEY = "derivation:market-intelligence:p1c:prepared-price-move:v1"
ATTENTION_EVALUATED_AT = "2026-02-15T12:04:00Z"
HISTORICAL_CUTOFF = "2026-02-15T12:00:59Z"
EXACT_CORE_WHEEL_SHA256 = (
    "07f5134488f7de16800aae290bb05284fdffe8fb679353b0b3f9771630ad302c"
)
P1C_RECORD_KINDS = (
    IntelligenceRecordKind.OBSERVATION,
    IntelligenceRecordKind.ENTITY_SNAPSHOT,
    IntelligenceRecordKind.SHIFT,
    IntelligenceRecordKind.SIGNAL,
    IntelligenceRecordKind.BRIEF,
    IntelligenceRecordKind.ATTENTION_DISPOSITION,
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


async def _committed_binding(
    compiled, fixture: dict[str, Any], boundary: dict[str, Any]
):
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
    snapshots = context["entity_snapshots"]
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
        as_of=snapshots[1].as_of,
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
    resource_by_id = {
        str(resource.resource_id): resource for resource in admission.resources
    }
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
            "processing_order": [
                reference.resource_id for reference in batch.processing_order
            ],
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
            str(getattr(item, "resource_id", getattr(item, "receipt_id", None)))
            for item in values
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
        resource.mode is IntelligenceResourceMode.PREPARED
        for resource in admission.resources
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
    assert expected["platform_dependency"]["ace_core_wheel_sha256"] == (
        EXACT_CORE_WHEEL_SHA256
    )
    assert (
        _identity_projection(batch, admission, binding, historical)
        == expected["expected"]
    )


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
        await PreparedIntelligenceLedgerService(binding=binding, store=store).admit(
            batch
        )

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
    foreign_activation_fixture["scenario"]["activation_key"] = (
        "market_intelligence_foreign"
    )
    foreign_activation = _prepared_binding(
        compiled, foreign_activation_fixture, boundary
    ).reference
    foreign_pack = _prepared_binding(
        _foreign_compiled_pack(), fixture, boundary
    ).revision.spec.pack

    foreign_pack_payload = batch.model_dump(
        mode="python", exclude={"batch_id", "batch_digest"}
    )
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

    divergent_payload = batch.model_dump(
        mode="python", exclude={"batch_id", "batch_digest"}
    )
    divergent_payload["attention_evaluated_at"] = (
        batch.attention_evaluated_at + timedelta(seconds=1)
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
    assert expected["platform_dependency"]["production_adapter_evidence_owner"] == (
        "ACE Platform"
    )
