#!/usr/bin/env python3
"""Hermetic Market P1C2 consumer acceptance through public ACE contracts only."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib.metadata
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import unquote, urlsplit

import ace
import ace_market_public_product_source as adapter_package
from ace.application import (
    DomainActivationAdmissionService,
    LiveSourceIngressService,
)
from ace.core import (
    AuthenticatedRuntimeContextV1Alpha1,
    AuthorityUseReceiptV1Alpha1,
    CapabilityArtifactIdentityV1Alpha1,
    CapabilityUseReceiptV1Alpha1,
    GovernedStateCommitRequestV1,
    GovernedStateHeadPreconditionV1Alpha1,
    GovernedStateHeadV1,
    ResolvedApprovalReceiptV1,
    ResolvedAuthorityGrantV1,
    ResolvedSourceDefinitionV1Alpha1,
    capability_state_ref_for_artifact,
)
from ace.intelligence import (
    ActivationState,
    AuthorityBindingV1,
    CapabilityBindingV1,
    LiveSourceIngressRequestV1Alpha1,
    OrganizationOverlayV1,
)
from ace.intelligence.packs import (
    compile_overlay,
    compile_pack_document,
    prepare_activation_revision,
    prepare_domain_activation,
)
from ace.testing import (
    InMemoryImmutableRecordStore,
    exercise_live_source_ingress_restart,
)
from ace_market_public_product_source import (
    PublicProductRetrievalResult,
    PublicProductSourceAdapter,
)

EXACT_CORE_WHEEL_SHA256 = (
    "902e52ffd3c5850aadd9b1b1cb69f190a8c6d0f93c288bb229d2b1c1e7077f10"
)
EXACT_ADAPTER_WHEEL_SHA256 = (
    "6e1cc3c710e7a1e9d8d464a356cadb1c41ea5663dacf57041943456594671c99"
)
INPUT_NAME = "p1c2_live_source_input.json"
EXPECTED_NAME = "p1c2_live_expected.json"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("fixture time must include a timezone")
    return parsed.astimezone(UTC)


def _pack_file(name: str) -> bytes:
    try:
        root = resources.files("domain_packs.market_intelligence")
    except ModuleNotFoundError:
        root = (
            Path(__file__).resolve().parents[1] / "domain_packs" / "market_intelligence"
        )
    return root.joinpath(name).read_bytes()


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads(_pack_file(f"releases/v0_3_0/conformance/{name}"))


def compile_market_pack():
    manifest_bytes = _pack_file("releases/v0_3_0/manifest.json")
    manifest = json.loads(manifest_bytes)
    return compile_pack_document(
        manifest_bytes,
        {
            resource["path"]: _pack_file(
                f"releases/v0_3_0/{resource['path']}"
            )
            for resource in manifest["resources"]
        },
    )


class MemoryGovernedStateStore:
    """Minimal public-protocol activation fixture; not production persistence."""

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
        self.values = values
        self.index = 0

    def __call__(self) -> datetime:
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value


class InjectedTransport:
    """Deterministic fixture transport; it performs no network access."""

    def __init__(
        self,
        result: PublicProductRetrievalResult,
        *,
        on_retrieve: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.result = result
        self.on_retrieve = on_retrieve
        self.calls = 0
        self.requests = []

    async def retrieve(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.on_retrieve is not None:
            await self.on_retrieve()
        return self.result


class ExactAdapterRegistry:
    def __init__(
        self, *, artifact, adapter, return_unconditionally: bool = False
    ) -> None:
        self.artifact = artifact
        self.adapter = adapter
        self.return_unconditionally = return_unconditionally
        self.calls = 0

    def resolve_source_adapter(self, *, artifact):
        self.calls += 1
        if self.return_unconditionally or artifact == self.artifact:
            return self.adapter
        return None


class ExactSourceDefinitionResolver:
    def __init__(self, definition: ResolvedSourceDefinitionV1Alpha1) -> None:
        self.definition = definition
        self.calls = 0

    async def resolve_source_definition(
        self, *, product_id, source_definition_ref, resolved_at
    ):
        del resolved_at
        self.calls += 1
        if (
            product_id != self.definition.product_id
            or source_definition_ref != self.definition.source_definition_ref
        ):
            raise ValueError("unknown exact source definition")
        return self.definition


class ExactRuntimeUseResolver:
    def __init__(
        self,
        *,
        context,
        artifact,
        configuration_ref,
        capability_head,
        authority,
        grant_ref,
        grant_hash,
        grant_expires_at,
        grant_head,
    ) -> None:
        self.context = context
        self.artifact = artifact
        self.configuration_ref = configuration_ref
        self.capability_head = capability_head
        self.authority = authority
        self.grant_ref = grant_ref
        self.grant_hash = grant_hash
        self.grant_expires_at = grant_expires_at
        self.grant_head = grant_head
        self.revoked = False
        self.capability_calls = 0
        self.authority_calls = 0

    async def resolve_capability_use(
        self,
        *,
        context,
        use_subject_ref,
        use_subject_digest,
        operation,
        artifact,
        capability_state_ref,
        configuration_ref,
        evaluated_at,
    ):
        self.capability_calls += 1
        if (
            context != self.context
            or artifact != self.artifact
            or capability_state_ref != capability_state_ref_for_artifact(self.artifact)
            or configuration_ref != self.configuration_ref
            or operation != "capture"
        ):
            raise ValueError("capability use crossed exact fixture scope")
        return CapabilityUseReceiptV1Alpha1(
            product_id=context.product_id,
            actor_ref=context.actor_ref,
            authenticated_context=context,
            use_subject_ref=use_subject_ref,
            use_subject_digest=use_subject_digest,
            operation=operation,
            artifact=artifact,
            capability_state_ref=capability_state_ref,
            configuration_ref=configuration_ref,
            evaluated_at=evaluated_at,
            resolved_at=evaluated_at,
            state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(
                self.capability_head
            ),
        )

    async def resolve_authority_use(
        self,
        *,
        context,
        use_subject_ref,
        use_subject_digest,
        operation,
        authority,
        grant_ref,
        evaluated_at,
    ):
        self.authority_calls += 1
        if (
            self.revoked
            or context != self.context
            or authority != self.authority
            or grant_ref != self.grant_ref
            or operation != "capture"
            or self.grant_expires_at <= evaluated_at
        ):
            raise ValueError("authority use crossed exact current grant scope")
        return AuthorityUseReceiptV1Alpha1(
            product_id=context.product_id,
            actor_ref=context.actor_ref,
            authenticated_context=context,
            use_subject_ref=use_subject_ref,
            use_subject_digest=use_subject_digest,
            operation=operation,
            authority=authority,
            grant_ref=grant_ref,
            grant_hash=self.grant_hash,
            evaluated_at=evaluated_at,
            expires_at=self.grant_expires_at,
            state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(
                self.grant_head
            ),
        )


@dataclass
class LiveConformanceEnvironment:
    fixture: dict[str, Any]
    pack: Any
    request: LiveSourceIngressRequestV1Alpha1
    activation_service: DomainActivationAdmissionService
    activation_store: MemoryGovernedStateStore
    committed_activation: Any
    immutable_store: InMemoryImmutableRecordStore
    source_definitions: ExactSourceDefinitionResolver
    runtime_use: ExactRuntimeUseResolver
    adapter: PublicProductSourceAdapter
    registry: ExactAdapterRegistry
    transport: InjectedTransport
    clock: SequenceClock

    def service(
        self, *, clock: SequenceClock | None = None
    ) -> LiveSourceIngressService:
        return LiveSourceIngressService(
            activation_service=self.activation_service,
            source_definitions=self.source_definitions,
            runtime_use=self.runtime_use,
            adapters=self.registry,
            store=self.immutable_store,
            clock=clock or self.clock,
            max_payload_chars=4_096,
        )

    def install_current_heads(self) -> None:
        activation_id = self.committed_activation.revision.activation_id
        activation_head = self.activation_store.heads[
            ("domain_activation", self.request.product_id, activation_id)
        ]
        for head in (
            activation_head,
            self.runtime_use.capability_head,
            self.runtime_use.grant_head,
            self.source_definitions.definition.state_head_precondition,
        ):
            if isinstance(head, GovernedStateHeadPreconditionV1Alpha1):
                head = GovernedStateHeadV1(
                    **head.model_dump(mode="python", exclude={"contract"}),
                    updated_at=_time(
                        self.fixture["scenario"]["activation_committed_at"]
                    ),
                )
            self.immutable_store.set_governed_state_head(head)


def _head(*, state_kind: str, product_id: str, state_id: str, material: dict[str, Any]):
    return GovernedStateHeadV1(
        state_kind=state_kind,
        product_id=product_id,
        state_id=state_id,
        sequence=material["sequence"],
        revision_id=material["revision_id"],
        commit_receipt_id=material["commit_receipt_id"],
        updated_at=_time(material["updated_at"]),
    )


async def build_environment(
    *,
    fixture: dict[str, Any] | None = None,
    immutable_store: InMemoryImmutableRecordStore | None = None,
    fail_after_records: int | None = None,
    transport_result: PublicProductRetrievalResult | None = None,
    on_retrieve: Callable[[], Awaitable[None]] | None = None,
) -> LiveConformanceEnvironment:
    fixture = fixture or load_fixture(INPUT_NAME)
    scenario = fixture["scenario"]
    artifact_data = fixture["adapter_artifact"]
    pack = compile_market_pack()
    artifact = CapabilityArtifactIdentityV1Alpha1(
        capability=artifact_data["capability"],
        contract=artifact_data["contract"],
        implementation_id=artifact_data["implementation_id"],
        implementation_version=artifact_data["implementation_version"],
        artifact_digest=artifact_data["artifact_digest"],
    )
    overlay = compile_overlay(
        pack,
        OrganizationOverlayV1(
            overlay_id=fixture["activation_binding"]["overlay_id"],
            version=fixture["activation_binding"]["overlay_version"],
            pack_id=pack.metadata.pack_id,
            pack_version=pack.metadata.version,
            pack_digest=pack.pack_digest,
        ),
    )
    capability = CapabilityBindingV1(
        requirement_id=fixture["activation_binding"]["capability_requirement_id"],
        capability=artifact.capability,
        contract=artifact.contract,
        implementation_id=artifact.implementation_id,
        implementation_version=artifact.implementation_version,
        artifact_digest=artifact.artifact_digest,
        configuration_ref=scenario["configuration_ref"],
        secret_ref=None,
    )
    authority = AuthorityBindingV1(
        request_id=fixture["activation_binding"]["authority_request_id"],
        authority=scenario["authority"],
        grant_ref=scenario["grant_ref"],
    )
    spec = prepare_domain_activation(
        product_id=scenario["product_id"],
        activation_key=scenario["activation_key"],
        pack=pack,
        overlay=overlay,
        compilation_receipt_ref=scenario["compilation_receipt_ref"],
        conformance_receipt_refs=(scenario["conformance_receipt_ref"],),
        capability_bindings=(capability,),
        authority_bindings=(authority,),
    )
    revision = prepare_activation_revision(
        spec=spec,
        state=ActivationState.ACTIVE,
        actor_ref=scenario["actor_ref"],
        approval_receipt_ref=scenario["approval_receipt_ref"],
        occurred_at=_time(scenario["activation_occurred_at"]),
    )
    activation_store = MemoryGovernedStateStore()
    activation_service = DomainActivationAdmissionService(
        store=activation_store,
        authority=ExactActivationAuthority(),
    )
    committed = await activation_service.admit(
        revision,
        expected_head_revision_id=None,
        committed_at=_time(scenario["activation_committed_at"]),
    )
    if committed.live_authority is not False:
        raise AssertionError("committed activation unexpectedly granted live authority")

    context = AuthenticatedRuntimeContextV1Alpha1(
        product_id=scenario["product_id"],
        actor_ref=scenario["actor_ref"],
        authentication_receipt_ref=scenario["authentication_receipt_ref"],
        authentication_receipt_digest=scenario["authentication_receipt_digest"],
        authenticated_at=_time(scenario["authenticated_at"]),
        expires_at=_time(scenario["authentication_expires_at"]),
    )
    request = LiveSourceIngressRequestV1Alpha1(
        product_id=scenario["product_id"],
        authenticated_context=context,
        idempotency_key=scenario["idempotency_key"],
        activation_key=scenario["activation_key"],
        mapping_id=scenario["mapping_id"],
        source_definition_ref=scenario["source_definition_ref"],
        compiled_pack_id=pack.compiled_pack_id,
        pack_digest=pack.pack_digest,
        requested_at=_time(scenario["requested_at"]),
    )

    capability_head = _head(
        state_kind="capability_state",
        product_id=scenario["product_id"],
        state_id=capability_state_ref_for_artifact(artifact),
        material=fixture["governed_heads"]["capability"],
    )
    grant_head = _head(
        state_kind="authority_grant",
        product_id=scenario["product_id"],
        state_id=scenario["grant_ref"],
        material=fixture["governed_heads"]["grant"],
    )
    source_head = _head(
        state_kind="source_definition",
        product_id=scenario["product_id"],
        state_id=scenario["source_definition_ref"],
        material=fixture["governed_heads"]["source_definition"],
    )
    definition = ResolvedSourceDefinitionV1Alpha1(
        product_id=scenario["product_id"],
        source_definition_ref=scenario["source_definition_ref"],
        source_type_ref=scenario["source_type_ref"],
        configuration_ref=scenario["configuration_ref"],
        configuration_digest=scenario["configuration_digest"],
        authorized_uri=fixture["transport_fixture"]["requested_uri"],
        subject_binding_id=scenario["subject_binding_id"],
        entity_type_id=scenario["entity_type_id"],
        entity_ref=scenario["entity_ref"],
        state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(
            source_head
        ),
    )
    runtime_use = ExactRuntimeUseResolver(
        context=context,
        artifact=artifact,
        configuration_ref=scenario["configuration_ref"],
        capability_head=capability_head,
        authority=scenario["authority"],
        grant_ref=scenario["grant_ref"],
        grant_hash=scenario["grant_hash"],
        grant_expires_at=_time(scenario["grant_expires_at"]),
        grant_head=grant_head,
    )
    transport_fixture = fixture["transport_fixture"]
    if transport_result is None:
        transport_result = PublicProductRetrievalResult(
            source_type_ref=scenario["source_type_ref"],
            requested_uri=transport_fixture["requested_uri"],
            effective_uri=transport_fixture["effective_uri"],
            status_code=transport_fixture["status_code"],
            media_type=transport_fixture["media_type"],
            response_body=transport_fixture["response_body"],
            redirect_chain=tuple(transport_fixture["redirect_chain"]),
            resolved_ip_addresses=tuple(transport_fixture["resolved_ip_addresses"]),
            connected_ip_addresses=tuple(transport_fixture["connected_ip_addresses"]),
            dns_rebinding_protection_applied=transport_fixture[
                "dns_rebinding_protection_applied"
            ],
            credentials_used=transport_fixture["credentials_used"],
            locator=transport_fixture["locator"],
            observed_at=_time(scenario["observed_at"]),
            captured_at=_time(scenario["captured_at"]),
            source_published_at=None,
            event_effective_at=None,
        )
    transport = InjectedTransport(transport_result, on_retrieve=on_retrieve)
    adapter = PublicProductSourceAdapter(
        transport=transport,
        artifact_digest=artifact.artifact_digest,
    )
    registry = ExactAdapterRegistry(artifact=artifact, adapter=adapter)
    store = immutable_store or InMemoryImmutableRecordStore(
        fail_after_records=fail_after_records
    )
    clock = SequenceClock(
        _time(scenario["capture_started_at"]),
        _time(scenario["rechecked_at"]),
        _time(scenario["admitted_at"]),
    )
    environment = LiveConformanceEnvironment(
        fixture=fixture,
        pack=pack,
        request=request,
        activation_service=activation_service,
        activation_store=activation_store,
        committed_activation=committed,
        immutable_store=store,
        source_definitions=ExactSourceDefinitionResolver(definition),
        runtime_use=runtime_use,
        adapter=adapter,
        registry=registry,
        transport=transport,
        clock=clock,
    )
    environment.install_current_heads()
    return environment


def identity_projection(
    environment: LiveConformanceEnvironment, admission
) -> dict[str, Any]:
    transaction = admission.transaction_receipt
    record_rows = [
        {
            "processing_order": item.processing_order,
            "record_kind": item.record_kind,
            "record_key": item.record_key,
            "storage_id": item.storage_id,
            "material_hash": item.material_hash,
        }
        for item in transaction.records
    ]
    observation = admission.observation
    entity = admission.entity_snapshot
    source_mapping = observation.source_mapping
    assert source_mapping is not None
    return {
        "platform": {
            "required_ace_core_wheel_sha256": EXACT_CORE_WHEEL_SHA256,
            "ace_import": str(Path(ace.__file__).resolve()),
        },
        "adapter": {
            **environment.adapter.artifact_identity.model_dump(mode="json"),
            "required_wheel_sha256": EXACT_ADAPTER_WHEEL_SHA256,
            "capture_calls": environment.adapter.capture_calls,
            "transport_calls": environment.transport.calls,
        },
        "pack": {
            "compiled_pack_id": environment.pack.compiled_pack_id,
            "pack_digest": environment.pack.pack_digest,
            "source_mapping_module_id": source_mapping.module_id,
            "source_mapping_module_digest": source_mapping.module_digest,
            "mapping_id": source_mapping.mapping_id,
            "mapping_digest": source_mapping.mapping_digest,
        },
        "activation": {
            "live_authority": environment.committed_activation.live_authority,
            "activation_id": environment.committed_activation.revision.activation_id,
            "spec_id": environment.committed_activation.revision.spec.spec_id,
            "spec_hash": environment.committed_activation.revision.spec.spec_hash,
            "revision_id": environment.committed_activation.revision.revision_id,
            "revision_digest": (
                "sha256:" + str(environment.committed_activation.revision.revision_hash)
            ),
            "commit_receipt_id": environment.committed_activation.commit_receipt.receipt_id,
            "commit_receipt_hash": environment.committed_activation.commit_receipt.receipt_hash,
        },
        "request": {
            "request_id": environment.request.request_id,
            "request_digest": environment.request.request_digest,
            "product_id": environment.request.product_id,
            "actor_ref": environment.request.authenticated_context.actor_ref,
            "operation": environment.request.operation,
            "idempotency_key": environment.request.idempotency_key,
        },
        "runtime_use": {
            "capability_use": admission.acquisition_receipt.capability_use.model_dump(
                mode="json"
            ),
            "authority_use": admission.acquisition_receipt.authority_use.model_dump(
                mode="json"
            ),
            "capability_state_ref": admission.acquisition_receipt.capability_use.capability_state_ref,
            "capability_use_receipt_id": admission.acquisition_receipt.capability_use.receipt_id,
            "capability_use_receipt_digest": admission.acquisition_receipt.capability_use.receipt_digest,
            "capability_evaluated_at": _iso(
                admission.acquisition_receipt.capability_use.evaluated_at
            ),
            "grant_ref": admission.acquisition_receipt.authority_use.grant_ref,
            "grant_hash": admission.acquisition_receipt.authority_use.grant_hash,
            "authority_use_receipt_id": admission.acquisition_receipt.authority_use.receipt_id,
            "authority_use_receipt_digest": admission.acquisition_receipt.authority_use.receipt_digest,
            "authority_evaluated_at": _iso(
                admission.acquisition_receipt.authority_use.evaluated_at
            ),
            "grant_expires_at": _iso(
                admission.acquisition_receipt.authority_use.expires_at
            ),
            "governed_heads": [
                item.model_dump(mode="json")
                for item in transaction.governed_state_preconditions
            ],
        },
        "live_records": {
            "record_space": transaction.record_space,
            "record_count": len(transaction.records),
            "records": record_rows,
            "acquisition_receipt_id": admission.acquisition_receipt.receipt_id,
            "acquisition_receipt_digest": admission.acquisition_receipt.receipt_digest,
            "acquisition_locator": admission.acquisition_receipt.locator,
            "source_snapshot_ref": admission.source_snapshot.source_snapshot_ref,
            "source_snapshot_digest": admission.source_snapshot.source_snapshot_digest,
            "source_snapshot_locator": admission.source_snapshot.locator,
            "observation_id": observation.resource_id,
            "observation_digest": observation.resource_digest,
            "entity_snapshot_id": entity.resource_id,
            "entity_snapshot_digest": entity.resource_digest,
            "admission_receipt_id": admission.admission_receipt.receipt_id,
            "admission_receipt_digest": admission.admission_receipt.receipt_digest,
            "transaction_id": transaction.transaction_id,
            "transaction_receipt_id": transaction.receipt_id,
            "transaction_receipt_digest": transaction.receipt_hash,
            "available_at": _iso(admission.admission_receipt.admitted_at),
        },
        "mapped_result": {
            "mode": observation.mode.value,
            "entity_ref": entity.entity_ref,
            "attributes": entity.attributes.parsed_value(),
            "observation_lineage": [
                item.model_dump(mode="json") for item in entity.lineage
            ],
            "source_uri": admission.source_snapshot.source_uri,
            "captured_payload_json": admission.source_snapshot.captured_payload_json,
        },
        "scope": {
            "exact_record_order": [item.record_kind for item in transaction.records],
            "prohibited_record_kinds_present": sorted(
                {
                    record.record_kind
                    for record in environment.immutable_store.records.values()
                    if record.record_kind
                    in environment.fixture["prohibited_record_kinds"]
                }
            ),
            "reusable_authority": admission.reusable_authority,
            "live_acquisition": admission.live_acquisition,
            "admission_disposition": admission.admission_disposition,
        },
    }


async def run_acceptance(*, assert_expected: bool = True) -> tuple[dict[str, Any], Any]:
    fixture = load_fixture(INPUT_NAME)
    if (
        fixture["platform_dependency"]["ace_core_wheel_sha256"]
        != EXACT_CORE_WHEEL_SHA256
    ):
        raise AssertionError("fixture does not bind the reviewed Core wheel")
    if (
        fixture["adapter_artifact"]["artifact_digest"]
        != f"sha256:{EXACT_ADAPTER_WHEEL_SHA256}"
    ):
        raise AssertionError("fixture does not bind the frozen adapter wheel")
    environment = await build_environment(fixture=fixture)
    first_service = environment.service()
    restarted_service = environment.service(
        clock=SequenceClock(_time(fixture["scenario"]["admitted_at"]))
    )
    conformance = await exercise_live_source_ingress_restart(
        first_service=first_service,
        restarted_service=restarted_service,
        request=environment.request,
        pack=environment.pack,
    )
    admission = conformance.first
    if environment.adapter.capture_calls != 1 or environment.transport.calls != 1:
        raise AssertionError("exact replay reacquired source material")
    actual_attributes = admission.entity_snapshot.attributes.parsed_value()
    if actual_attributes != fixture["expected_attributes"]:
        raise AssertionError(
            "LIVE entity attributes did not match the exact Market mapping: "
            f"{actual_attributes!r}"
        )
    if (
        len(environment.immutable_store.records) != 5
        or len(environment.immutable_store.receipts) != 1
    ):
        raise AssertionError(
            "LIVE ingress did not create exactly one atomic five-record transaction"
        )
    projection = identity_projection(environment, admission)
    projection["platform"].pop("ace_import")
    if projection["scope"]["exact_record_order"] != [
        "source_acquisition",
        "source_snapshot",
        "observation",
        "entity_snapshot",
        "source_admission",
    ]:
        raise AssertionError("Platform record order changed")
    if projection["scope"]["prohibited_record_kinds_present"]:
        raise AssertionError("out-of-scope downstream records were admitted")
    if assert_expected:
        expected = load_fixture(EXPECTED_NAME)
        if projection != expected["expected"]:
            raise AssertionError(
                "P1C2 LIVE identity projection changed from its exact pin"
            )
    return projection, (environment, conformance)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_wheel(path: Path, expected: str, *, name: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise SystemExit(f"{name} wheel SHA-256 mismatch: {actual}")


def _installed_from_exact_wheel(
    *,
    distribution_name: str,
    wheel: Path,
    import_path: Path,
    owned_relative_path: str,
) -> dict[str, str]:
    distribution = importlib.metadata.distribution(distribution_name)
    direct_url_raw = distribution.read_text("direct_url.json")
    if direct_url_raw is None:
        raise SystemExit(
            f"{distribution_name} lacks exact local-wheel installation provenance"
        )
    direct_url = json.loads(direct_url_raw)
    parsed = urlsplit(direct_url.get("url", ""))
    installed_from = (
        Path(unquote(parsed.path)).resolve() if parsed.scheme == "file" else None
    )
    if installed_from != wheel.resolve():
        raise SystemExit(
            f"{distribution_name} was not installed from the supplied exact wheel: "
            f"{installed_from}"
        )
    wheel_sha256 = _sha256(wheel)
    archive_info = direct_url.get("archive_info")
    archive_hashes = (
        archive_info.get("hashes") if isinstance(archive_info, dict) else None
    )
    installed_archive_sha256 = (
        archive_hashes.get("sha256") if isinstance(archive_hashes, dict) else None
    )
    if installed_archive_sha256 is None and isinstance(archive_info, dict):
        legacy_hash = archive_info.get("hash")
        prefix = "sha256="
        if isinstance(legacy_hash, str) and legacy_hash.startswith(prefix):
            installed_archive_sha256 = legacy_hash.removeprefix(prefix)
    if installed_archive_sha256 != wheel_sha256:
        raise SystemExit(
            f"{distribution_name} direct-url archive digest does not match the "
            "supplied exact wheel"
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
    installed_record_value = (
        base64.urlsafe_b64encode(installed_digest).decode().rstrip("=")
    )
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-wheel", type=Path, required=True)
    parser.add_argument("--adapter-wheel", type=Path, required=True)
    parser.add_argument("--market-wheel", type=Path, required=True)
    parser.add_argument("--market-wheel-sha256", required=True)
    parser.add_argument("--emit-projection", action="store_true")
    args = parser.parse_args()
    _verify_wheel(args.core_wheel, EXACT_CORE_WHEEL_SHA256, name="Core")
    _verify_wheel(args.adapter_wheel, EXACT_ADAPTER_WHEEL_SHA256, name="adapter")
    _verify_wheel(args.market_wheel, args.market_wheel_sha256, name="Market")
    market_manifest = resources.files("domain_packs.market_intelligence").joinpath(
        "manifest.json"
    )
    verification = {
        "core": _installed_from_exact_wheel(
            distribution_name="ace-core",
            wheel=args.core_wheel,
            import_path=Path(ace.__file__),
            owned_relative_path="ace/__init__.py",
        ),
        "adapter": _installed_from_exact_wheel(
            distribution_name="ace-market-public-product-source",
            wheel=args.adapter_wheel,
            import_path=Path(adapter_package.__file__),
            owned_relative_path="ace_market_public_product_source/__init__.py",
        ),
        "market": _installed_from_exact_wheel(
            distribution_name="ace-ext-b2b-marketing",
            wheel=args.market_wheel,
            import_path=Path(str(market_manifest)),
            owned_relative_path="domain_packs/market_intelligence/manifest.json",
        ),
    }
    projection, _ = asyncio.run(
        run_acceptance(assert_expected=not args.emit_projection)
    )
    projection["artifact_verification"] = verification
    print(json.dumps(projection, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
