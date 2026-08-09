from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import runpy
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from ace.application import (
    LiveSourceIngressError,
    LiveSourceIngressReplayConflict,
    PreparedIntelligenceLedgerService,
    bind_committed_activation,
)
from ace.core import (
    AuthenticatedRuntimeContextV1Alpha1,
    CanonicalSourceSnapshotV1Alpha1,
    CapabilityArtifactIdentityV1Alpha1,
    GovernedStateHeadPreconditionV1Alpha1,
    GovernedStateHeadV1,
    ImmutableRecordPersistenceError,
    SourceAcquisitionMode,
)
from ace.intelligence import (
    IntelligenceResourceMode,
    LiveSourceIngressRequestV1Alpha1,
    LiveSourceMappingError,
    ResolvedSubjectBindingV1Alpha1,
    interpret_live_source_mapping,
)
from ace.intelligence.packs import prepare_activation_revision
from ace.testing import InMemoryImmutableRecordStore

# The public product source adapter is a separately installed executable artifact with its own
# review and trust boundary. It is deliberately not a dependency of the inert Domain Pack, so its
# absence is a supported state rather than a broken checkout. Skip this module with an actionable
# reason instead of aborting collection for the entire suite. The harness loaded below imports the
# adapter too, so this guard must precede it.
pytest.importorskip(
    "ace_market_public_product_source",
    reason=(
        "ace_market_public_product_source is not installed. It is a separately installed adapter "
        "artifact, not part of the Domain Pack. Install it, or add "
        "adapters/public_product_source/src to PYTHONPATH, to run the LIVE source conformance "
        "suite."
    ),
)

from ace_market_public_product_source import (  # noqa: E402  (guarded by importorskip above)
    PublicProductSourceAdapterError,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "domain_packs" / "market_intelligence"
CONFORMANCE_ROOT = PACK_ROOT / "conformance"
HARNESS = runpy.run_path(
    str(REPO_ROOT / "scripts" / "p1c2_live_public_source_acceptance.py"),
    run_name="market_p1c2_live_harness",
)
build_environment = HARNESS["build_environment"]
load_fixture = HARNESS["load_fixture"]
run_acceptance = HARNESS["run_acceptance"]
SequenceClock = HARNESS["SequenceClock"]
ExactAdapterRegistry = HARNESS["ExactAdapterRegistry"]
INPUT_NAME = HARNESS["INPUT_NAME"]


def exercises_negative_cases(*case_ids: str):
    """Bind declared negative IDs to the test function that exercises them."""

    def decorate(test):
        test.p1c2_negative_case_ids = frozenset(case_ids)
        return test

    return decorate


def _time(value: str):
    return HARNESS["_time"](value)


def _advanced(head: GovernedStateHeadV1, suffix: str) -> GovernedStateHeadV1:
    return GovernedStateHeadV1(
        state_kind=head.state_kind,
        product_id=head.product_id,
        state_id=head.state_id,
        sequence=head.sequence + 1,
        revision_id=f"{head.revision_id}-{suffix}",
        commit_receipt_id=f"{head.commit_receipt_id}-{suffix}",
        updated_at=head.updated_at + timedelta(seconds=1),
    )


def _new_request(
    environment, *, actor_ref=None, product_id=None, source_definition_ref=None
):
    original = environment.request
    selected_product = product_id or original.product_id
    context = AuthenticatedRuntimeContextV1Alpha1(
        product_id=selected_product,
        actor_ref=actor_ref or original.authenticated_context.actor_ref,
        authentication_receipt_ref=original.authenticated_context.authentication_receipt_ref,
        authentication_receipt_digest=original.authenticated_context.authentication_receipt_digest,
        authenticated_at=original.authenticated_context.authenticated_at,
        expires_at=original.authenticated_context.expires_at,
    )
    return LiveSourceIngressRequestV1Alpha1(
        product_id=selected_product,
        authenticated_context=context,
        idempotency_key=original.idempotency_key,
        activation_key=original.activation_key,
        mapping_id=original.mapping_id,
        source_definition_ref=source_definition_ref or original.source_definition_ref,
        compiled_pack_id=original.compiled_pack_id,
        pack_digest=original.pack_digest,
        requested_at=original.requested_at,
    )


def _assert_no_live_residue(environment) -> None:
    assert environment.immutable_store.records == {}
    assert environment.immutable_store.receipts == {}


@pytest.mark.asyncio
async def test_exact_golden_replay_and_later_state_independent_historical_replay() -> (
    None
):
    projection, (environment, conformance) = await run_acceptance()

    assert projection == load_fixture("p1c2_live_expected.json")["expected"]
    assert conformance.first.replayed is False
    assert conformance.exact_replay.replayed is True
    assert conformance.restarted_replay.replayed is True
    assert environment.adapter.capture_calls == environment.transport.calls == 1
    assert (
        conformance.first.acquisition_receipt.locator
        == conformance.first.source_snapshot.locator
        == "json-pointer:/listed_price"
    )

    before_records = dict(environment.immutable_store.records)
    before_receipts = dict(environment.immutable_store.receipts)
    environment.runtime_use.revoked = True
    environment.runtime_use.capability_head = _advanced(
        environment.runtime_use.capability_head, "later"
    )
    environment.runtime_use.grant_head = _advanced(
        environment.runtime_use.grant_head, "later"
    )
    environment.activation_store.heads.clear()
    environment.source_definitions.definition = (
        environment.source_definitions.definition.model_copy(
            update={"configuration_digest": "sha256:" + "f" * 64}
        )
    )

    replay = await environment.service(
        clock=SequenceClock(_time(environment.fixture["scenario"]["admitted_at"]))
    ).replay(request=environment.request)

    assert replay is not None and replay.replayed is True
    assert replace(replay, replayed=False) == conformance.first
    assert environment.adapter.capture_calls == environment.transport.calls == 1
    assert environment.immutable_store.records == before_records
    assert environment.immutable_store.receipts == before_receipts


@exercises_negative_cases(
    "activation_changed_during_capture",
    "capability_changed_during_capture",
    "grant_changed_during_capture",
    "source_definition_changed_during_capture",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed", ["activation", "capability", "grant", "source_definition"]
)
async def test_governed_head_change_during_capture_is_atomic(changed: str) -> None:
    environment = await build_environment()

    async def mutate() -> None:
        if changed == "activation":
            current = environment.committed_activation.revision
            next_revision = prepare_activation_revision(
                spec=current.spec,
                state=current.state,
                actor_ref=current.actor_ref,
                approval_receipt_ref=current.approval_receipt_ref,
                occurred_at=_time(environment.fixture["scenario"]["captured_at"]),
                prior_revision=current,
            )
            await environment.activation_service.admit(
                next_revision,
                expected_head_revision_id=current.revision_id,
                committed_at=_time(environment.fixture["scenario"]["captured_at"]),
            )
        elif changed == "capability":
            new_head = _advanced(environment.runtime_use.capability_head, "capture")
            environment.runtime_use.capability_head = new_head
            environment.immutable_store.set_governed_state_head(new_head)
        elif changed == "grant":
            new_head = _advanced(environment.runtime_use.grant_head, "capture")
            environment.runtime_use.grant_head = new_head
            environment.immutable_store.set_governed_state_head(new_head)
        else:
            old = environment.source_definitions.definition
            old_head = old.state_head_precondition
            new_head = GovernedStateHeadV1(
                state_kind=old_head.state_kind,
                product_id=old_head.product_id,
                state_id=old_head.state_id,
                sequence=old_head.sequence + 1,
                revision_id=f"{old_head.revision_id}-capture",
                commit_receipt_id=f"{old_head.commit_receipt_id}-capture",
                updated_at=_time(environment.fixture["scenario"]["captured_at"]),
            )
            environment.source_definitions.definition = old.model_copy(
                update={
                    "state_head_precondition": GovernedStateHeadPreconditionV1Alpha1.from_head(
                        new_head
                    )
                }
            )
            environment.immutable_store.set_governed_state_head(new_head)

    environment.transport.on_retrieve = mutate
    with pytest.raises(
        LiveSourceIngressError, match="governed runtime material changed"
    ):
        await environment.service().admit(
            request=environment.request,
            pack=environment.pack,
        )
    _assert_no_live_residue(environment)


@exercises_negative_cases(
    "registry_artifact_id_mismatch",
    "registry_artifact_version_mismatch",
    "registry_artifact_digest_mismatch",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("implementation_id", "different_market_public_product_source"),
        ("implementation_version", "0.1.2"),
        ("artifact_digest", "sha256:" + "e" * 64),
    ],
)
async def test_registry_artifact_mismatch_rejects_before_invocation(
    field, value
) -> None:
    environment = await build_environment()
    expected = environment.adapter.artifact_identity
    payload = expected.model_dump(mode="python")
    payload[field] = value
    different = CapabilityArtifactIdentityV1Alpha1(**payload)

    class NeverInvoked:
        artifact_identity = different
        calls = 0

        async def capture(self, request):
            self.calls += 1
            raise AssertionError("mismatched adapter was invoked")

    candidate = NeverInvoked()
    environment.registry = ExactAdapterRegistry(
        artifact=expected,
        adapter=candidate,
        return_unconditionally=True,
    )
    with pytest.raises(
        LiveSourceIngressError, match="different source adapter artifact"
    ):
        await environment.service().admit(
            request=environment.request, pack=environment.pack
        )
    assert candidate.calls == 0
    _assert_no_live_residue(environment)


@exercises_negative_cases(
    "wrong_actor",
    "wrong_product",
    "wrong_source_definition",
    "wrong_configuration",
    "wrong_grant",
    "expired_grant",
    "revoked_grant",
    "unrelated_capability_head",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "wrong_actor",
        "wrong_product",
        "wrong_source_definition",
        "wrong_configuration",
        "wrong_grant",
        "expired_grant",
        "revoked_grant",
        "unrelated_capability_head",
    ],
)
async def test_actor_product_source_configuration_and_runtime_grant_fail_closed(
    case,
) -> None:
    environment = await build_environment()
    request = environment.request
    if case == "wrong_actor":
        request = _new_request(environment, actor_ref="actor:other-market-analyst")
    elif case == "wrong_product":
        request = _new_request(environment, product_id="product:other-market")
    elif case == "wrong_source_definition":
        request = _new_request(
            environment,
            source_definition_ref="source_definition:other-public-product",
        )
    elif case == "wrong_configuration":
        environment.source_definitions.definition = (
            environment.source_definitions.definition.model_copy(
                update={"configuration_ref": "config:other-public-product"}
            )
        )
    elif case == "wrong_grant":
        environment.runtime_use.grant_ref = "authority_grant:other-source-read"
    elif case == "expired_grant":
        environment.runtime_use.grant_expires_at = _time(
            environment.fixture["scenario"]["capture_started_at"]
        )
    elif case == "revoked_grant":
        environment.runtime_use.revoked = True
    else:
        original = environment.runtime_use.capability_head
        environment.runtime_use.capability_head = GovernedStateHeadV1(
            state_kind="capability_state",
            product_id=original.product_id,
            state_id="capability_state:unrelated-same-kind-head",
            sequence=original.sequence,
            revision_id=original.revision_id,
            commit_receipt_id=original.commit_receipt_id,
            updated_at=original.updated_at,
        )

    with pytest.raises((LiveSourceIngressError, ValueError)):
        await environment.service().admit(request=request, pack=environment.pack)
    assert environment.adapter.capture_calls == 0
    _assert_no_live_residue(environment)


@exercises_negative_cases(
    "http_uri",
    "uri_userinfo",
    "uri_fragment",
    "local_hostname",
    "private_ip_literal",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "uri",
    [
        "http://public.example.test/products/edge-x1",
        "https://user@public.example.test/products/edge-x1",
        "https://public.example.test/products/edge-x1#fragment",
        "https://localhost/products/edge-x1",
        "https://10.0.0.8/products/edge-x1",
    ],
)
async def test_closed_uri_policy_rejects_before_capture(uri: str) -> None:
    fixture = deepcopy(load_fixture(INPUT_NAME))
    fixture["transport_fixture"]["requested_uri"] = uri
    fixture["transport_fixture"]["effective_uri"] = uri
    with pytest.raises(ValueError):
        await build_environment(fixture=fixture)


@exercises_negative_cases(
    "non_global_ip_attestation",
    "redirect",
    "source_type_mismatch",
    "effective_uri_mismatch",
    "missing_dns_protection",
    "wrong_locator",
    "malformed_payload",
    "oversized_payload",
    "ambiguous_payload",
    "missing_payload_field",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "pattern"),
    [
        ({"resolved_ip_addresses": ("127.0.0.1",)}, "globally routable"),
        ({"redirect_chain": ("https://public.example.test/redirect",)}, "empty tuple"),
        ({"source_type_ref": "other_source"}, "source type"),
        (
            {"effective_uri": "https://public.example.test/products/other"},
            "URI scope",
        ),
        ({"dns_rebinding_protection_applied": False}, "DNS-rebinding"),
        ({"locator": "json-pointer:/product_name"}, "exact extraction locator"),
        ({"response_body": "not-json"}, "unambiguous bounded JSON"),
        ({"response_body": "x" * 4_097}, "character bound"),
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
            {"response_body": ('{"product_name":"Edge X1","listed_price":"1080.00"}')},
            "canonical three fields",
        ),
    ],
)
async def test_untrusted_transport_result_fails_closed_without_residue(
    changes, pattern
) -> None:
    environment = await build_environment()
    environment.transport.result = replace(environment.transport.result, **changes)
    with pytest.raises(
        LiveSourceIngressError, match="source adapter capture failed closed"
    ) as exc:
        await environment.service().admit(
            request=environment.request, pack=environment.pack
        )
    assert isinstance(exc.value.__cause__, PublicProductSourceAdapterError)
    assert pattern in str(exc.value.__cause__)
    _assert_no_live_residue(environment)


@exercises_negative_cases(
    "observed_before_capture_start",
    "captured_before_observed",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "case_id"),
    [
        (
            {"observed_at": _time("2026-08-06T12:01:00Z")},
            "observed_before_capture_start",
        ),
        (
            {"captured_at": _time("2026-08-06T12:01:01Z")},
            "captured_before_observed",
        ),
    ],
)
async def test_impossible_capture_ordering_fails_closed_without_residue(
    changes, case_id
) -> None:
    del case_id
    environment = await build_environment()
    environment.transport.result = replace(environment.transport.result, **changes)
    with pytest.raises(
        LiveSourceIngressError, match="source adapter capture failed closed"
    ) as exc:
        await environment.service().admit(
            request=environment.request, pack=environment.pack
        )
    assert isinstance(exc.value.__cause__, PublicProductSourceAdapterError)
    assert "observation/capture times" in str(exc.value.__cause__)
    _assert_no_live_residue(environment)


@exercises_negative_cases("grant_expires_during_capture")
@pytest.mark.asyncio
async def test_grant_expiring_during_capture_fails_before_recheck_without_residue() -> (
    None
):
    environment = await build_environment()
    environment.runtime_use.grant_expires_at = _time(
        environment.fixture["scenario"]["rechecked_at"]
    )
    with pytest.raises(
        LiveSourceIngressError,
        match="authority grant expired before source admission recheck",
    ):
        await environment.service().admit(
            request=environment.request, pack=environment.pack
        )
    assert environment.adapter.capture_calls == environment.transport.calls == 1
    _assert_no_live_residue(environment)


@exercises_negative_cases("unfaithful_payload")
@pytest.mark.asyncio
async def test_unfaithful_decimal_text_fails_in_live_mapping_without_residue() -> None:
    environment = await build_environment()
    environment.transport.result = replace(
        environment.transport.result,
        response_body=(
            '{"product_name":"Edge X1","listed_price":"9007199254740993",'
            '"currency":"USD"}'
        ),
    )
    with pytest.raises(
        LiveSourceMappingError, match="LIVE source mapping validation failed closed"
    ) as exc:
        await environment.service().admit(
            request=environment.request, pack=environment.pack
        )
    assert "not faithfully representable as a JSON number" in str(exc.value.__cause__)
    assert environment.adapter.capture_calls == environment.transport.calls == 1
    _assert_no_live_residue(environment)


@exercises_negative_cases("forged_request", "forged_result")
@pytest.mark.asyncio
async def test_forged_request_and_forged_result_fail_closed() -> None:
    environment = await build_environment()
    forged_request = environment.request.model_copy(
        update={"request_digest": "sha256:" + "e" * 64}
    )
    with pytest.raises(LiveSourceIngressError, match="revalidation"):
        await environment.service().admit(request=forged_request, pack=environment.pack)
    assert environment.adapter.capture_calls == 0
    _assert_no_live_residue(environment)

    real_adapter = environment.adapter

    class ForgedResultAdapter:
        artifact_identity = real_adapter.artifact_identity

        async def capture(self, request):
            captured = await real_adapter.capture(request)
            return captured.model_copy(
                update={"capture_request_digest": "sha256:" + "f" * 64}
            )

    environment.registry.adapter = ForgedResultAdapter()
    with pytest.raises(
        LiveSourceIngressError, match="result failed exact revalidation"
    ):
        await environment.service().admit(
            request=environment.request, pack=environment.pack
        )
    _assert_no_live_residue(environment)


@exercises_negative_cases("forged_receipt")
@pytest.mark.asyncio
async def test_forged_persisted_receipt_fails_replay_validation() -> None:
    environment = await build_environment()
    service = environment.service()
    admission = await service.admit(request=environment.request, pack=environment.pack)
    last_ref = admission.transaction_receipt.records[-1]
    stored = environment.immutable_store.records[last_ref.storage_id]
    payload = dict(stored.payload)
    payload["receipt_digest"] = "sha256:" + "f" * 64
    environment.immutable_store.records[last_ref.storage_id] = stored.model_copy(
        update={"payload": payload}
    )

    with pytest.raises((LiveSourceIngressError, ValueError)):
        await environment.service().replay(request=environment.request)


@exercises_negative_cases("prepared_relabel_live")
@pytest.mark.asyncio
async def test_prepared_snapshot_is_rejected_by_live_mapper() -> None:
    environment = await build_environment()
    binding = bind_committed_activation(
        pack=environment.pack,
        committed=environment.committed_activation,
    ).prepared_binding
    fixture = environment.fixture
    payload_json = json.dumps(
        {"product_name": "Edge X1", "listed_price": "1080.00", "currency": "USD"},
        sort_keys=True,
        separators=(",", ":"),
    )
    snapshot = CanonicalSourceSnapshotV1Alpha1(
        source_definition_ref=fixture["scenario"]["source_definition_ref"],
        source_type_ref=fixture["scenario"]["source_type_ref"],
        source_uri=fixture["transport_fixture"]["requested_uri"],
        captured_payload_json=payload_json,
        captured_payload_digest="sha256:"
        + hashlib.sha256(payload_json.encode()).hexdigest(),
        observed_at=_time(fixture["scenario"]["observed_at"]),
        ingested_at=_time(fixture["scenario"]["rechecked_at"]),
        acquisition_mode=SourceAcquisitionMode.PREPARED_FIXTURE,
        acquisition_receipt_ref="receipt:prepared-only",
        acquisition_receipt_digest="sha256:" + "a" * 64,
    )
    subject = ResolvedSubjectBindingV1Alpha1(
        product_id=fixture["scenario"]["product_id"],
        mode=IntelligenceResourceMode.LIVE,
        activation_revision=binding.reference,
        subject_binding_id=fixture["scenario"]["subject_binding_id"],
        entity_type_id=fixture["scenario"]["entity_type_id"],
        entity_ref=fixture["scenario"]["entity_ref"],
    )
    with pytest.raises(LiveSourceMappingError, match="LIVE source mapping requires"):
        interpret_live_source_mapping(
            binding=binding,
            mapping_id=fixture["scenario"]["mapping_id"],
            source_snapshot=snapshot,
            subject_binding=subject,
        )
    _assert_no_live_residue(environment)


@exercises_negative_cases(
    "changed_intent_same_idempotency_key",
    "cross_product_replay",
)
@pytest.mark.asyncio
async def test_changed_intent_conflicts_and_cross_product_replay_is_denied() -> None:
    environment = await build_environment()
    service = environment.service()
    first = await service.admit(request=environment.request, pack=environment.pack)
    changed = LiveSourceIngressRequestV1Alpha1(
        **environment.request.model_dump(
            mode="python", exclude={"request_id", "request_digest", "requested_at"}
        ),
        requested_at=environment.request.requested_at + timedelta(seconds=1),
    )
    with pytest.raises(LiveSourceIngressReplayConflict):
        await service.admit(request=changed, pack=environment.pack)
    assert environment.adapter.capture_calls == 1

    foreign = _new_request(environment, product_id="product:other-market")
    assert await environment.service().replay(request=foreign) is None
    first_record = first.transaction_receipt.records[0]
    assert (
        await environment.immutable_store.load_record(
            first_record.storage_id,
            product_id=foreign.product_id,
            record_space="live",
            record_kind=first_record.record_kind,
        )
        is None
    )


@exercises_negative_cases("persistence_interruption")
@pytest.mark.asyncio
async def test_persistence_interruption_leaves_no_records_or_receipt() -> None:
    environment = await build_environment(fail_after_records=3)
    with pytest.raises(ImmutableRecordPersistenceError, match="simulated interruption"):
        await environment.service().admit(
            request=environment.request, pack=environment.pack
        )
    _assert_no_live_residue(environment)


@pytest.mark.asyncio
async def test_prepared_and_live_record_spaces_and_counts_remain_isolated() -> None:
    p1c1 = runpy.run_path(
        str(
            REPO_ROOT
            / "domain_packs"
            / "tests"
            / "test_market_intelligence_durable_conformance.py"
        ),
        run_name="market_p1c1_durable_harness",
    )
    compiled = p1c1["_compiled_pack"]()
    prepared_fixture = p1c1["_load_json"](p1c1["PRICE_MOVE_FIXTURE_PATH"])
    boundary = p1c1["_load_json"](p1c1["PUBLIC_SOURCE_BOUNDARY_PATH"])
    prepared, binding, _ = await p1c1["_committed_binding"](
        compiled, prepared_fixture, boundary
    )
    derivation = p1c1["_prepared_derivation"](
        binding=prepared,
        compiled=compiled,
        fixture=prepared_fixture,
    )
    batch = p1c1["_batch"](binding, derivation)
    shared = InMemoryImmutableRecordStore()
    await PreparedIntelligenceLedgerService(binding=binding, store=shared).admit(batch)
    environment = await build_environment(immutable_store=shared)
    await environment.service().admit(
        request=environment.request, pack=environment.pack
    )

    prepared_records = [
        r for r in shared.records.values() if r.record_space == "prepared"
    ]
    live_records = [r for r in shared.records.values() if r.record_space == "live"]
    assert len(prepared_records) == 8
    assert len(live_records) == 5
    assert {r.record_kind for r in live_records} == {
        "source_acquisition",
        "source_snapshot",
        "observation",
        "entity_snapshot",
        "source_admission",
    }
    assert not ({"signal", "shift", "brief"} & {r.record_kind for r in live_records})


def test_artifact_bound_cli_verifies_clean_install_and_rejects_tampered_record_member(
    tmp_path: Path,
) -> None:
    variable_names = {
        "core": "ACE_P1C2_CORE_WHEEL",
        "adapter": "ACE_P1C2_ADAPTER_WHEEL",
        "market": "ACE_P1C2_MARKET_WHEEL",
        "market_sha256": "ACE_P1C2_MARKET_WHEEL_SHA256",
    }
    configured = {key: os.environ.get(name) for key, name in variable_names.items()}
    if (
        any(value is None for value in configured.values())
        or os.environ.get("ACE_P1C2_DISPOSABLE_INSTALL") != "1"
    ):
        pytest.skip(
            "exact-wheel test requires the disposable installed-wheel bootstrap"
        )

    command = [
        sys.executable,
        "-I",
        str(REPO_ROOT / "scripts" / "p1c2_live_public_source_acceptance.py"),
        "--core-wheel",
        configured["core"],
        "--adapter-wheel",
        configured["adapter"],
        "--market-wheel",
        configured["market"],
        "--market-wheel-sha256",
        configured["market_sha256"],
    ]
    accepted = subprocess.run(
        command,
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert accepted.returncode == 0, accepted.stderr
    verification = json.loads(accepted.stdout)["artifact_verification"]
    assert verification["core"]["wheel_sha256"] == HARNESS["EXACT_CORE_WHEEL_SHA256"]
    assert (
        verification["adapter"]["wheel_sha256"] == HARNESS["EXACT_ADAPTER_WHEEL_SHA256"]
    )
    for artifact in verification.values():
        assert artifact["installed_archive_sha256"] == artifact["wheel_sha256"]

    distribution = importlib.metadata.distribution("ace-market-public-product-source")
    owned = next(
        item
        for item in distribution.files or ()
        if str(item) == "ace_market_public_product_source/__init__.py"
    )
    installed_member = Path(distribution.locate_file(owned)).resolve()
    original = installed_member.read_bytes()
    try:
        installed_member.write_bytes(
            original + b"\n# deliberate installed-byte tamper\n"
        )
        rejected = subprocess.run(
            command,
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        installed_member.write_bytes(original)
    assert rejected.returncode != 0
    assert "installed bytes do not match the RECORD hash" in rejected.stderr


def test_frozen_p1c1_bytes_and_live_conformance_inventory_are_exact() -> None:
    frozen = {
        "manifest.json": "82719602adf0ddd47ab1d7e80e9806c94c9c329705acc61c283796d79bcbd46d",
        "modules/source_mapping.json": "acebb1a048ca284c9d7d902e4c1a3af9ea02567f13836685382a02047e7ee293",
        "conformance/manifest.json": "bf65b0d44622c33411bc2911bd765095e20c38db3aa3564652391aedf0889ced",
        "conformance/public_product_price_boundary.json": "dfc0a63eaaebca857c46da62080ae14f5d46793d808fe0296d66c951c55bdff5",
        "conformance/p1_price_move_golden.json": "5d04afed27b785f35cbd29083d566bb84770a2fbdf4a44837ea196e432dd1cdf",
        "conformance/p1_price_move_negative_cases.json": "39003bb393dc94bf2737b7568993577a0e9b55a4efc7981922270350a2e8095c",
        "conformance/p1c_durable_price_move_expected.json": "735fe7aa0dc1678daa3dec3d052317452314b075c45ef24b88d8d409d131b6b7",
    }
    for relative, expected in frozen.items():
        assert (
            hashlib.sha256((PACK_ROOT / relative).read_bytes()).hexdigest() == expected
        )

    live_manifest = load_fixture("p1c2_live_manifest.json")
    expected_live_files = {
        "p1c2_live_manifest.json",
        "p1c2_live_source_input.json",
        "p1c2_live_source_negative_cases.json",
        "p1c2_live_expected.json",
    }
    assert {
        path.name for path in CONFORMANCE_ROOT.glob("p1c2_live_*.json")
    } == expected_live_files
    assert {item["path"] for item in live_manifest["artifacts"]} == {
        path for path in expected_live_files if path != "p1c2_live_manifest.json"
    }
    for item in live_manifest["artifacts"]:
        actual = hashlib.sha256(
            (CONFORMANCE_ROOT / item["path"]).read_bytes()
        ).hexdigest()
        assert item["digest"] == f"sha256:{actual}"
    negative = load_fixture("p1c2_live_source_negative_cases.json")
    assert live_manifest["negative_case_count"] == negative["case_count"]
    assert negative["case_count"] == len(negative["cases"]) == 41


def test_declared_negative_case_inventory_exactly_matches_exercised_gates() -> None:
    negative = load_fixture("p1c2_live_source_negative_cases.json")
    declared = [item["case_id"] for item in negative["cases"]]
    exercised = set().union(
        *(
            value.p1c2_negative_case_ids
            for value in globals().values()
            if callable(value) and hasattr(value, "p1c2_negative_case_ids")
        )
    )
    assert len(declared) == len(set(declared))
    assert set(declared) == exercised
