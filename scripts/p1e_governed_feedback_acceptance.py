#!/usr/bin/env python3
"""P1E Decision/no-action -> Outcome -> governed PREPARED feedback acceptance."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from p1d1_prepared_brief_acceptance import (
    ExactActivationAuthority,
    ForbiddenProvider,
    SequenceClock,
    _activation_spec,
    _load_historical_fixture,
    _pack_file,
    _time,
    compile_market_pack,
)
from p1d1_prepared_brief_acceptance import (
    run_positive as run_p1d1_positive,
)

from ace.application import (
    PreparedDecisionFeedbackError,
    PreparedDecisionFeedbackService,
    bind_committed_activation,
)
from ace.core import (
    AuthenticatedRuntimeContextV1Alpha1,
    DecisionActionDisposition,
    DecisionDisposition,
    DecisionIntentV1Alpha1,
    GovernedReasoningService,
    OutcomeIntentV1Alpha1,
    ResolvedApprovalReceiptV1,
    immutable_record_storage_id,
)
from ace.intelligence import (
    ActivationState,
    IntelligenceResourceMode,
)
from ace.intelligence.packs import prepare_activation_revision

INPUT_NAME = "p1e_governed_feedback_input.json"
EXPECTED_NAME = "p1e_governed_feedback_expected.json"
NEGATIVE_NAME = "p1e_governed_feedback_negative_cases.json"


def _release_file(name: str) -> bytes:
    return _pack_file(f"releases/v0_5_0/conformance/{name}")


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads(_release_file(name))


def _reference_projection(value) -> dict[str, Any]:
    return value.model_dump(mode="json")


def _record_kind_counts(store) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in store.records.values():
        counts[record.record_kind] = counts.get(record.record_kind, 0) + 1
    return dict(sorted(counts.items()))


@dataclass(slots=True)
class Environment:
    fixture: dict[str, Any]
    p1d1: Any
    pack_v0_5_0: Any
    rev4: Any
    rev4_binding: Any
    auth: AuthenticatedRuntimeContextV1Alpha1
    service: PreparedDecisionFeedbackService
    authorizer: GovernedReasoningService
    forbidden_provider: ForbiddenProvider
    brief_record: Any


@dataclass(frozen=True, slots=True)
class PositiveResult:
    environment: Environment
    decision: Any
    decision_replay: Any
    outcome: Any
    outcome_replay: Any
    proposal: Any
    proposal_replay: Any
    feedback_commit: Any
    feedback_commit_replay: Any
    fresh_effective: Any


async def build_environment() -> Environment:
    fixture = load_fixture(INPUT_NAME)
    p1d1 = await run_p1d1_positive()
    env = p1d1.environment
    pack_v0_5_0 = compile_market_pack(release="v0_5_0")
    boundary = _load_historical_fixture("public_product_price_boundary.json")
    activation = fixture["activation"]
    spec4 = _activation_spec(
        pack=pack_v0_5_0,
        version=fixture["fixture_version"],
        product_id=env.fixture["activation"]["product_id"],
        activation_key=env.fixture["activation"]["activation_key"],
        compilation_receipt_ref=activation["revision_4_compilation_receipt_ref"],
        conformance_receipt_ref=activation["revision_4_conformance_receipt_ref"],
        boundary=boundary,
    )
    revision4 = prepare_activation_revision(
        spec=spec4,
        state=ActivationState.ACTIVE,
        actor_ref=activation["actor_ref"],
        approval_receipt_ref=activation["revision_4_approval_receipt_ref"],
        occurred_at=_time(activation["revision_4_occurred_at"]),
        prior_revision=p1d1.rev3.revision,
    )
    rev4 = await env.activation_service.admit(
        revision4,
        expected_head_revision_id=str(p1d1.rev3.revision.revision_id),
        committed_at=_time(activation["revision_4_committed_at"]),
    )
    rev4_binding = bind_committed_activation(pack=pack_v0_5_0, committed=rev4)
    activation_head = env.activation_store.heads[
        (
            rev4.commit_receipt.state_kind,
            rev4.commit_receipt.product_id,
            rev4.commit_receipt.state_id,
        )
    ]
    env.store.set_governed_state_head(activation_head)

    brief = p1d1.first.brief
    brief_storage_id = immutable_record_storage_id(
        product_id=brief.product_id,
        record_space="prepared",
        record_kind="brief",
        record_key=str(brief.resource_id),
    )
    brief_record = await env.store.load_record(
        brief_storage_id,
        product_id=brief.product_id,
        record_space="prepared",
        record_kind="brief",
    )
    if brief_record is None:
        raise AssertionError("P1E source Brief is missing from exact P1D1 persistence")
    expected_brief = fixture["source_brief"]
    if (
        brief.resource_id != expected_brief["brief_id"]
        or brief.resource_digest != expected_brief["brief_digest"]
    ):
        raise AssertionError("P1E source Brief changed from the pinned P1D1 identity")

    auth_fixture = fixture["authentication"]
    auth = AuthenticatedRuntimeContextV1Alpha1(
        product_id=brief.product_id,
        actor_ref=auth_fixture["actor_ref"],
        authentication_receipt_ref=auth_fixture["receipt_ref"],
        authentication_receipt_digest=auth_fixture["receipt_digest"],
        authenticated_at=_time(auth_fixture["authenticated_at"]),
        expires_at=_time(auth_fixture["expires_at"]),
    )
    decision_at = _time(fixture["decision"]["decided_at"])
    outcome_at = _time(fixture["outcome"]["recorded_at"])
    proposal_at = _time(fixture["feedback"]["proposed_at"])
    forbidden = ForbiddenProvider(env.execution_binding.artifact)
    authorizer = GovernedReasoningService(
        store=env.store,
        runtime_use=env.runtime,
        provider=forbidden,
        clock=SequenceClock(
            decision_at + timedelta(seconds=1),
            decision_at + timedelta(seconds=2),
            outcome_at + timedelta(seconds=1),
            outcome_at + timedelta(seconds=2),
            proposal_at + timedelta(seconds=1),
            proposal_at + timedelta(seconds=2),
        ),
    )
    service = PreparedDecisionFeedbackService(
        binding=rev4_binding,
        record_store=env.store,
        governed_store=env.activation_store,
        authority=ExactActivationAuthority(),
        authorizer=authorizer,
        operation_binding=env.append_binding,
        clock=SequenceClock(_time(fixture["feedback"]["committed_at"])),
    )
    return Environment(
        fixture=fixture,
        p1d1=p1d1,
        pack_v0_5_0=pack_v0_5_0,
        rev4=rev4,
        rev4_binding=rev4_binding,
        auth=auth,
        service=service,
        authorizer=authorizer,
        forbidden_provider=forbidden,
        brief_record=brief_record,
    )


async def run_positive() -> PositiveResult:
    env = await build_environment()
    fixture = env.fixture
    decision_fixture = fixture["decision"]
    decision_intent = DecisionIntentV1Alpha1(
        product_id=env.auth.product_id,
        authenticated_context=env.auth,
        subject=env.brief_record.reference(),
        actor_role_ref=fixture["policy"]["persona_id"],
        decision_type=decision_fixture["decision_type"],
        disposition=DecisionDisposition(decision_fixture["disposition"]),
        action_disposition=DecisionActionDisposition(
            decision_fixture["action_disposition"]
        ),
        action_type=decision_fixture["action_type"],
        rationale=decision_fixture["rationale"],
        decided_at=_time(decision_fixture["decided_at"]),
    )
    policy_id = fixture["policy"]["policy_id"]
    decision = await env.service.record_decision(decision_intent, policy_id=policy_id)
    decision_replay = await env.service.record_decision(
        decision_intent,
        policy_id=policy_id,
    )

    outcome_fixture = fixture["outcome"]
    outcome_intent = OutcomeIntentV1Alpha1(
        product_id=env.auth.product_id,
        authenticated_context=env.auth,
        decision=decision.record,
        outcome_type=outcome_fixture["outcome_type"],
        measure_id=outcome_fixture["measure_id"],
        value_json=outcome_fixture["value_json"],
        observed_at=_time(outcome_fixture["observed_at"]),
        recorded_at=_time(outcome_fixture["recorded_at"]),
    )
    outcome = await env.service.record_outcome(outcome_intent, policy_id=policy_id)
    outcome_replay = await env.service.record_outcome(outcome_intent, policy_id=policy_id)

    proposal = await env.service.propose_feedback(
        outcome.record,
        policy_id=policy_id,
        proposed_at=_time(fixture["feedback"]["proposed_at"]),
    )
    proposal_replay = await env.service.propose_feedback(
        outcome.record,
        policy_id=policy_id,
        proposed_at=_time(fixture["feedback"]["proposed_at"]),
    )
    feedback_commit = await env.service.commit_feedback(
        proposal.record,
        actor_ref=fixture["feedback"]["approved_by"],
        approval_receipt_ref=fixture["feedback"]["approval_receipt_ref"],
        committed_at=_time(fixture["feedback"]["committed_at"]),
    )
    feedback_commit_replay = await env.service.commit_feedback(
        proposal.record,
        actor_ref=fixture["feedback"]["approved_by"],
        approval_receipt_ref=fixture["feedback"]["approval_receipt_ref"],
        committed_at=_time(fixture["feedback"]["committed_at"]),
    )
    fresh = PreparedDecisionFeedbackService(
        binding=env.rev4_binding,
        record_store=env.p1d1.environment.store,
        governed_store=env.p1d1.environment.activation_store,
        authority=ExactActivationAuthority(),
        authorizer=env.authorizer,
        operation_binding=env.p1d1.environment.append_binding,
        clock=SequenceClock(_time(fixture["feedback"]["committed_at"])),
    )
    fresh_effective = await fresh.effective_policy(policy_id)
    return PositiveResult(
        environment=env,
        decision=decision,
        decision_replay=decision_replay,
        outcome=outcome,
        outcome_replay=outcome_replay,
        proposal=proposal,
        proposal_replay=proposal_replay,
        feedback_commit=feedback_commit,
        feedback_commit_replay=feedback_commit_replay,
        fresh_effective=fresh_effective,
    )


async def positive_projection(result: PositiveResult) -> dict[str, Any]:
    env = result.environment
    p1d1 = env.p1d1
    shared_modules = {}
    for name in ("ontology", "source_mapping", "detection", "synthesis", "personas"):
        before = _pack_file(f"releases/v0_4_0/modules/{name}.json")
        after = _pack_file(f"releases/v0_5_0/modules/{name}.json")
        shared_modules[name] = {
            "byte_identical": before == after,
            "sha256": hashlib.sha256(after).hexdigest(),
        }
    live_counts = {
        kind: sum(
            record.record_space == "live" and record.record_kind == kind
            for record in p1d1.environment.store.records.values()
        )
        for kind in ("decision", "outcome", "feedback_proposal")
    }
    return {
        "pack": {
            "compiled_pack_id": env.pack_v0_5_0.compiled_pack_id,
            "pack_digest": env.pack_v0_5_0.pack_digest,
            "decision_outcomes_module_digest": next(
                item.module_digest
                for item in env.pack_v0_5_0.modules
                if item.module_id == "market_decision_outcomes"
            ),
            "shared_v0_4_0_modules": shared_modules,
        },
        "activation_revision_4": {
            "activation_id": env.rev4.revision.activation_id,
            "revision_id": env.rev4.revision.revision_id,
            "revision_hash": env.rev4.revision.revision_hash,
            "prior_revision_id": env.rev4.revision.prior_revision_id,
            "commit_receipt_id": env.rev4.commit_receipt.receipt_id,
            "commit_receipt_hash": env.rev4.commit_receipt.receipt_hash,
        },
        "source_brief": {
            "resource_id": p1d1.first.brief.resource_id,
            "resource_digest": p1d1.first.brief.resource_digest,
            "record_storage_id": env.brief_record.storage_id,
            "record_material_hash": env.brief_record.material_hash,
        },
        "decision": {
            "decision_id": result.decision.decision.decision_id,
            "decision_digest": result.decision.decision.decision_digest,
            "intent_id": result.decision.decision.intent.intent_id,
            "authorization_receipt_id": (
                result.decision.authorization.authorization_ref.receipt_id
            ),
            "record_storage_id": result.decision.record.storage_id,
            "record_material_hash": result.decision.record.material_hash,
            "transaction_id": result.decision.transaction_receipt.transaction_id,
            "transaction_receipt_id": result.decision.transaction_receipt.receipt_id,
            "exact_replay": result.decision == result.decision_replay,
            "explicit_no_action": (
                result.decision.decision.intent.action_disposition.value == "no_action"
                and result.decision.decision.intent.action_type is None
            ),
        },
        "outcome": {
            "outcome_id": result.outcome.outcome.outcome_id,
            "outcome_digest": result.outcome.outcome.outcome_digest,
            "intent_id": result.outcome.outcome.intent.intent_id,
            "authorization_receipt_id": (
                result.outcome.authorization.authorization_ref.receipt_id
            ),
            "record_storage_id": result.outcome.record.storage_id,
            "record_material_hash": result.outcome.record.material_hash,
            "transaction_id": result.outcome.transaction_receipt.transaction_id,
            "transaction_receipt_id": result.outcome.transaction_receipt.receipt_id,
            "exact_replay": result.outcome == result.outcome_replay,
        },
        "feedback_proposal": {
            "proposal_id": result.proposal.proposal.proposal_id,
            "proposal_digest": result.proposal.proposal.proposal_digest,
            "intent_id": result.proposal.proposal.intent.intent_id,
            "policy_id": result.proposal.proposal.intent.policy_id,
            "policy_digest": result.proposal.proposal.intent.policy_digest,
            "prior_value": result.proposal.proposal.intent.prior_value,
            "adjustment": result.proposal.proposal.intent.adjustment,
            "proposed_value": result.proposal.proposal.intent.proposed_value,
            "authorization_receipt_id": (
                result.proposal.authorization.authorization_ref.receipt_id
            ),
            "record_storage_id": result.proposal.record.storage_id,
            "record_material_hash": result.proposal.record.material_hash,
            "transaction_id": result.proposal.transaction_receipt.transaction_id,
            "transaction_receipt_id": result.proposal.transaction_receipt.receipt_id,
            "exact_replay": result.proposal == result.proposal_replay,
        },
        "governed_feedback": {
            "state_id": result.feedback_commit.state.state_id,
            "revision_id": result.feedback_commit.state.revision_id,
            "revision_digest": result.feedback_commit.state.revision_digest,
            "sequence": result.feedback_commit.state.sequence,
            "value": result.feedback_commit.state.value,
            "source_proposal_storage_id": (
                result.feedback_commit.state.source_proposal.storage_id
            ),
            "commit_receipt_id": result.feedback_commit.commit_receipt.receipt_id,
            "commit_receipt_hash": result.feedback_commit.commit_receipt.receipt_hash,
            "approval_subject_ref": (
                result.feedback_commit.commit_receipt.approval.subject_ref
            ),
            "exact_replay": result.feedback_commit == result.feedback_commit_replay,
            "fresh_service_value": result.fresh_effective.value,
            "fresh_service_revision_id": result.fresh_effective.state.revision_id,
            "fresh_service_live_effect": result.fresh_effective.live_effect,
        },
        "invariants": {
            "provider_calls": env.forbidden_provider.calls,
            "external_action_executed": False,
            "delivery_authority": False,
            "live_counts": live_counts,
            "prepared_record_kind_counts": _record_kind_counts(
                p1d1.environment.store
            ),
            "historical_p1d1_brief_unchanged": (
                p1d1.first.brief.resource_id
                == env.fixture["source_brief"]["brief_id"]
                and p1d1.first.brief.resource_digest
                == env.fixture["source_brief"]["brief_digest"]
            ),
            "prepared_feedback_only": (
                result.feedback_commit.state.mode
                is IntelligenceResourceMode.PREPARED
                and result.feedback_commit.live_effect is False
            ),
        },
    }


def assert_positive(result: PositiveResult, projection: dict[str, Any]) -> None:
    fixture = result.environment.fixture
    if not all(
        item["byte_identical"]
        for item in projection["pack"]["shared_v0_4_0_modules"].values()
    ):
        raise AssertionError("0.5.0 changed a frozen 0.4.0 module")
    if not projection["decision"]["explicit_no_action"]:
        raise AssertionError("P1E did not preserve explicit Decision/no-action separation")
    if projection["invariants"]["provider_calls"] != 0:
        raise AssertionError("P1E action authorization invoked a reasoning provider")
    if any(projection["invariants"]["live_counts"].values()):
        raise AssertionError("P1E fixture-derived material entered LIVE records")
    if projection["governed_feedback"]["fresh_service_value"] != fixture["policy"][
        "expected_value"
    ]:
        raise AssertionError("fresh service did not resolve the exact approved prepared value")
    if projection["governed_feedback"]["fresh_service_live_effect"]:
        raise AssertionError("prepared feedback claimed a LIVE effect")
    if not all(
        (
            projection["decision"]["exact_replay"],
            projection["outcome"]["exact_replay"],
            projection["feedback_proposal"]["exact_replay"],
            projection["governed_feedback"]["exact_replay"],
            projection["invariants"]["historical_p1d1_brief_unchanged"],
            projection["invariants"]["prepared_feedback_only"],
        )
    ):
        raise AssertionError("P1E replay or historical immutability invariant failed")


def _decision_intent(env: Environment, **updates) -> DecisionIntentV1Alpha1:
    fixture = env.fixture["decision"]
    payload = {
        "product_id": env.auth.product_id,
        "authenticated_context": env.auth,
        "subject": env.brief_record.reference(),
        "actor_role_ref": env.fixture["policy"]["persona_id"],
        "decision_type": fixture["decision_type"],
        "disposition": DecisionDisposition(fixture["disposition"]),
        "action_disposition": DecisionActionDisposition(fixture["action_disposition"]),
        "action_type": fixture["action_type"],
        "rationale": fixture["rationale"],
        "decided_at": _time(fixture["decided_at"]),
    }
    payload.update(updates)
    return DecisionIntentV1Alpha1(**payload)


def _outcome_intent(env: Environment, decision_record, **updates) -> OutcomeIntentV1Alpha1:
    fixture = env.fixture["outcome"]
    payload = {
        "product_id": env.auth.product_id,
        "authenticated_context": env.auth,
        "decision": decision_record,
        "outcome_type": fixture["outcome_type"],
        "measure_id": fixture["measure_id"],
        "value_json": fixture["value_json"],
        "observed_at": _time(fixture["observed_at"]),
        "recorded_at": _time(fixture["recorded_at"]),
    }
    payload.update(updates)
    return OutcomeIntentV1Alpha1(**payload)


def _p1e_counts(env: Environment) -> dict[str, int]:
    values = {
        kind: sum(
            record.record_kind == kind
            for record in env.p1d1.environment.store.records.values()
        )
        for kind in ("decision", "outcome", "feedback_proposal", "action_authorization")
    }
    values["feedback_state"] = sum(
        revision.state_kind == "prepared_feedback_policy"
        for revision in env.p1d1.environment.activation_store.revisions.values()
    )
    return values


async def _failed_case(case_id: str, env: Environment, operation) -> dict[str, Any]:
    before = _p1e_counts(env)
    try:
        await operation()
    except (PreparedDecisionFeedbackError, TypeError, ValueError) as exc:
        after = _p1e_counts(env)
        return {
            "case_id": case_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "residue_delta": {key: after[key] - before[key] for key in before},
        }
    raise AssertionError(f"negative case unexpectedly succeeded: {case_id}")


class _DenyAuthorizer:
    async def authorize_action(self, request):
        del request
        raise PermissionError("decision feedback authority denied")


class _WrongApprovalAuthority(ExactActivationAuthority):
    async def resolve_approval(self, **request):
        return ResolvedApprovalReceiptV1(
            receipt_ref=request["receipt_ref"],
            product_id=request["product_id"],
            subject_ref="feedback_proposal:wrong-subject",
            actor_ref=request["actor_ref"],
            receipt_hash="a" * 64,
            approved_at=request["effective_at"] - timedelta(seconds=1),
        )


def _service_with(env: Environment, *, authorizer=None, authority=None):
    return PreparedDecisionFeedbackService(
        binding=env.rev4_binding,
        record_store=env.p1d1.environment.store,
        governed_store=env.p1d1.environment.activation_store,
        authority=authority or ExactActivationAuthority(),
        authorizer=authorizer or env.authorizer,
        operation_binding=env.p1d1.environment.append_binding,
        clock=SequenceClock(_time(env.fixture["feedback"]["committed_at"])),
    )


async def run_negative_inventory() -> list[dict[str, Any]]:
    policy_id = "competitive_price_move_usefulness"
    observed: list[dict[str, Any]] = []

    env = await build_environment()
    observed.append(
        await _failed_case(
            "unknown_feedback_policy",
            env,
            lambda: env.service.record_decision(
                _decision_intent(env), policy_id="unknown_policy"
            ),
        )
    )

    env = await build_environment()
    observed.append(
        await _failed_case(
            "wrong_persona",
            env,
            lambda: env.service.record_decision(
                _decision_intent(env, actor_role_ref="product_marketer"),
                policy_id=policy_id,
            ),
        )
    )

    env = await build_environment()
    denied = _service_with(env, authorizer=_DenyAuthorizer())
    observed.append(
        await _failed_case(
            "decision_authority_denied",
            env,
            lambda: denied.record_decision(_decision_intent(env), policy_id=policy_id),
        )
    )

    env = await build_environment()
    decision = await env.service.record_decision(_decision_intent(env), policy_id=policy_id)
    observed.append(
        await _failed_case(
            "wrong_outcome_measure",
            env,
            lambda: env.service.record_outcome(
                _outcome_intent(env, decision.record, measure_id="revenue_impact"),
                policy_id=policy_id,
            ),
        )
    )

    env = await build_environment()
    decision = await env.service.record_decision(_decision_intent(env), policy_id=policy_id)
    observed.append(
        await _failed_case(
            "outcome_before_decision",
            env,
            lambda: env.service.record_outcome(
                _outcome_intent(
                    env,
                    decision.record,
                    observed_at=_time("2026-08-06T15:29:59Z"),
                ),
                policy_id=policy_id,
            ),
        )
    )

    env = await build_environment()
    decision = await env.service.record_decision(_decision_intent(env), policy_id=policy_id)
    outcome = await env.service.record_outcome(
        _outcome_intent(env, decision.record, value_json='"neutral"'),
        policy_id=policy_id,
    )
    observed.append(
        await _failed_case(
            "unmapped_outcome_value",
            env,
            lambda: env.service.propose_feedback(
                outcome.record,
                policy_id=policy_id,
                proposed_at=_time(env.fixture["feedback"]["proposed_at"]),
            ),
        )
    )

    env = await build_environment()
    decision = await env.service.record_decision(_decision_intent(env), policy_id=policy_id)
    outcome = await env.service.record_outcome(
        _outcome_intent(env, decision.record), policy_id=policy_id
    )
    bad_reference = outcome.record.model_copy(
        update={"material_hash": "sha256:" + "f" * 64}
    )
    observed.append(
        await _failed_case(
            "wrong_outcome_record_digest",
            env,
            lambda: env.service.propose_feedback(
                bad_reference,
                policy_id=policy_id,
                proposed_at=_time(env.fixture["feedback"]["proposed_at"]),
            ),
        )
    )

    env = await build_environment()
    decision = await env.service.record_decision(_decision_intent(env), policy_id=policy_id)
    outcome = await env.service.record_outcome(
        _outcome_intent(env, decision.record), policy_id=policy_id
    )
    proposal = await env.service.propose_feedback(
        outcome.record,
        policy_id=policy_id,
        proposed_at=_time(env.fixture["feedback"]["proposed_at"]),
    )
    wrong_approval = _service_with(env, authority=_WrongApprovalAuthority())
    observed.append(
        await _failed_case(
            "wrong_feedback_approval_subject",
            env,
            lambda: wrong_approval.commit_feedback(
                proposal.record,
                actor_ref=env.fixture["feedback"]["approved_by"],
                approval_receipt_ref=env.fixture["feedback"]["approval_receipt_ref"],
                committed_at=_time(env.fixture["feedback"]["committed_at"]),
            ),
        )
    )

    env = await build_environment()
    decision = await env.service.record_decision(_decision_intent(env), policy_id=policy_id)
    outcome = await env.service.record_outcome(
        _outcome_intent(env, decision.record), policy_id=policy_id
    )
    first = await env.service.propose_feedback(
        outcome.record,
        policy_id=policy_id,
        proposed_at=_time(env.fixture["feedback"]["proposed_at"]),
    )
    stale = await env.service.propose_feedback(
        outcome.record,
        policy_id=policy_id,
        proposed_at=_time(env.fixture["feedback"]["proposed_at"])
        + timedelta(seconds=1),
    )
    await env.service.commit_feedback(
        first.record,
        actor_ref=env.fixture["feedback"]["approved_by"],
        approval_receipt_ref=env.fixture["feedback"]["approval_receipt_ref"],
        committed_at=_time(env.fixture["feedback"]["committed_at"]),
    )
    observed.append(
        await _failed_case(
            "stale_feedback_proposal",
            env,
            lambda: env.service.commit_feedback(
                stale.record,
                actor_ref=env.fixture["feedback"]["approved_by"],
                approval_receipt_ref="receipt:p1e-stale-feedback-approval",
                committed_at=_time(env.fixture["feedback"]["committed_at"])
                + timedelta(seconds=1),
            ),
        )
    )
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
        expected = load_fixture(EXPECTED_NAME)
        if projection != expected["expected"]:
            raise AssertionError("P1E result differs from pinned expected artifact")
    if check_negative:
        negative = load_fixture(NEGATIVE_NAME)
        if await run_negative_inventory() != negative["cases"]:
            raise AssertionError("P1E negative inventory differs from pinned artifact")
    return projection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-expected", action="store_true")
    parser.add_argument("--emit-negative-cases", action="store_true")
    args = parser.parse_args()
    if args.emit_negative_cases:
        print(
            json.dumps(
                {
                    "contract": "ace.market-intelligence.p1e-governed-feedback-negative-cases/v1",
                    "fixture_version": "0.5.0",
                    "cases": asyncio.run(run_negative_inventory()),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    projection = asyncio.run(
        run_acceptance(
            check_expected=not args.emit_expected,
            check_negative=False,
        )
    )
    payload = {
        "contract": "ace.market-intelligence.p1e-governed-feedback-expected/v1",
        "fixture_version": "0.5.0",
        "expected": projection,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
