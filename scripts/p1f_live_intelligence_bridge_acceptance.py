#!/usr/bin/env python3
"""Hermetic Market P1F LIVE source-to-Brief consumer acceptance."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

from p1c2_live_public_source_acceptance import (
    SequenceClock as IngressClock,
)
from p1c2_live_public_source_acceptance import (
    _time,
    build_environment,
)
from p1d1_prepared_brief_acceptance import (
    ExactRuntimeUse,
    FixtureProvider,
    ForbiddenProvider,
    SequenceClock,
    _head,
)
from p1d1_prepared_brief_acceptance import (
    load_fixture as load_brief_fixture,
)

from ace.application import (
    LiveBriefSynthesisError,
    LiveBriefSynthesisReplayConflict,
    LiveBriefSynthesisService,
    LiveIntelligenceBridgeError,
    LiveIntelligenceBridgeReplayConflict,
    LiveIntelligenceBridgeService,
    bind_committed_activation,
)
from ace.core import (
    CapabilityArtifactIdentityV1Alpha1,
    GovernedOperationBindingV1Alpha1,
    GovernedReasoningService,
    GovernedStateHeadPreconditionV1Alpha1,
    ReasoningExecutionBindingV1Alpha1,
    capability_state_ref_for_artifact,
)
from ace.intelligence import (
    BriefSynthesisRequestV1Alpha1,
    IntelligenceResourceMode,
    LiveDerivationRequestV1Alpha1,
    LiveSourceIngressRequestV1Alpha1,
    resource_reference,
)


def _ingress_request(environment, *, key: str, requested_at):
    material = environment.request.model_dump(
        mode="python",
        exclude={"request_id", "request_digest"},
    )
    material.update(idempotency_key=key, requested_at=requested_at)
    return LiveSourceIngressRequestV1Alpha1.model_validate(material)


def _admitted_reference(admission):
    intrinsic = resource_reference(admission.entity_snapshot)
    envelope = next(
        item
        for item in admission.transaction_receipt.records
        if item.record_kind == "entity_snapshot"
    )
    return intrinsic.model_copy(update={"available_at": envelope.available_at})


@dataclass(frozen=True, slots=True)
class P1FRun:
    source_environment: object
    bridge: LiveIntelligenceBridgeService
    derivation_request: LiveDerivationRequestV1Alpha1
    derivation: object
    brief_service: LiveBriefSynthesisService
    brief_request: BriefSynthesisRequestV1Alpha1
    brief: object


async def run_acceptance() -> tuple[dict, P1FRun]:
    environment = await build_environment()
    fixture = environment.fixture
    scenario = fixture["scenario"]
    baseline_observed = _time("2026-08-06T12:01:02Z")
    current_observed = _time("2026-08-06T12:03:02Z")

    environment.transport.result = replace(
        environment.transport.result,
        response_body=('{"product_name":"Edge X1","listed_price":"1200.00","currency":"USD"}'),
        observed_at=baseline_observed,
        captured_at=baseline_observed,
    )
    baseline_request = _ingress_request(
        environment,
        key="live-source:market-northstar:edge-x1:baseline",
        requested_at=_time("2026-08-06T12:01:00Z"),
    )
    baseline = await environment.service(
        clock=IngressClock(
            _time("2026-08-06T12:01:01Z"),
            _time("2026-08-06T12:01:03Z"),
            _time("2026-08-06T12:01:04Z"),
        )
    ).admit(request=baseline_request, pack=environment.pack)

    environment.transport.result = replace(
        environment.transport.result,
        response_body=fixture["transport_fixture"]["response_body"],
        observed_at=current_observed,
        captured_at=current_observed,
    )
    current_request = _ingress_request(
        environment,
        key="live-source:market-northstar:edge-x1:current",
        requested_at=_time("2026-08-06T12:03:00Z"),
    )
    current = await environment.service(
        clock=IngressClock(
            _time("2026-08-06T12:03:01Z"),
            _time("2026-08-06T12:03:03Z"),
            _time("2026-08-06T12:03:04Z"),
        )
    ).admit(request=current_request, pack=environment.pack)

    binding = bind_committed_activation(
        pack=environment.pack,
        committed=environment.committed_activation,
    )
    product_id = scenario["product_id"]
    reasoning_fixture = copy.deepcopy(load_brief_fixture("p1d1_prepared_brief_input.json"))
    reasoning_fixture["provider_draft"]["sections"].sort(key=lambda item: item["section_id"])
    reasoning_artifact = CapabilityArtifactIdentityV1Alpha1(
        **reasoning_fixture["reasoning"]["reasoning_artifact"]
    )
    append_artifact = CapabilityArtifactIdentityV1Alpha1(
        **reasoning_fixture["reasoning"]["append_artifact"]
    )
    updated_at = _time("2026-08-06T11:59:00Z")
    execution_head = _head(
        product_id,
        "reasoning_configuration",
        "reasoning_configuration:market-p1f",
        updated_at=updated_at,
    )
    append_head = _head(
        product_id,
        "governed_operation_configuration",
        "governed_operation_configuration:market-p1f-append",
        updated_at=updated_at,
    )
    execution_binding = ReasoningExecutionBindingV1Alpha1(
        product_id=product_id,
        artifact=reasoning_artifact,
        configuration_ref=execution_head.state_id,
        authority="reason",
        grant_ref="authority_grant:market-p1f-reason",
        state_head_precondition=GovernedStateHeadPreconditionV1Alpha1.from_head(execution_head),
    )
    append_binding = GovernedOperationBindingV1Alpha1(
        product_id=product_id,
        artifact=append_artifact,
        configuration_ref=append_head.state_id,
        authority="append_immutable_records",
        grant_ref="authority_grant:market-p1f-append",
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
        environment.immutable_store.set_governed_state_head(head)
    runtime = ExactRuntimeUse(
        execution_binding=execution_binding,
        append_binding=append_binding,
        store=environment.immutable_store,
        updated_at=updated_at,
    )
    provider = FixtureProvider(
        fixture=reasoning_fixture,
        artifact=reasoning_artifact,
    )
    governed_at = _time("2026-08-06T12:08:00Z")
    reasoning = GovernedReasoningService(
        store=environment.immutable_store,
        runtime_use=runtime,
        provider=provider,
        clock=SequenceClock(governed_at),
    )

    derivation_request = LiveDerivationRequestV1Alpha1(
        derivation_key="derivation:market-intelligence:p1f:live-price-move:v1",
        product_id=product_id,
        authenticated_context=environment.request.authenticated_context,
        activation_revision=binding.prepared_binding.reference,
        pack=binding.prepared_binding.revision.spec.pack,
        detector_id="product_price_move",
        baseline=_admitted_reference(baseline),
        current=_admitted_reference(current),
        detected_at=_time("2026-08-06T12:05:00Z"),
        attention_evaluated_at=_time("2026-08-06T12:05:01Z"),
        requested_at=_time("2026-08-06T12:05:02Z"),
    )
    bridge = LiveIntelligenceBridgeService(
        activation_service=environment.activation_service,
        pack=environment.pack,
        store=environment.immutable_store,
        authorizer=reasoning,
        operation_binding=append_binding,
    )
    derivation = await bridge.derive(derivation_request)

    brief_request = BriefSynthesisRequestV1Alpha1(
        synthesis_key="synthesis:market-intelligence:p1f:live-price-move:v1",
        reasoning_attempt_key="reasoning:market-intelligence:p1f:live-price-move:v1",
        derivation_key=derivation_request.derivation_key,
        product_id=product_id,
        mode=IntelligenceResourceMode.LIVE,
        authenticated_context=environment.request.authenticated_context,
        activation_revision=binding.prepared_binding.reference,
        pack=binding.prepared_binding.revision.spec.pack,
        attention_receipt_id=str(derivation.attention_receipt.receipt_id),
        attention_receipt_digest=str(derivation.attention_receipt.receipt_digest),
        brief_as_of=derivation.attention_receipt.evaluated_at,
        context_cutoff_at=derivation.attention_receipt.evaluated_at,
        requested_at=_time("2026-08-06T12:06:00Z"),
    )
    brief_service = LiveBriefSynthesisService(
        activation_service=environment.activation_service,
        pack=environment.pack,
        store=environment.immutable_store,
        reasoning=reasoning,
        execution_binding=execution_binding,
        append_binding=append_binding,
    )
    brief = await brief_service.synthesize(brief_request)

    replay_provider = ForbiddenProvider(reasoning_artifact)
    replay_reasoning = GovernedReasoningService(
        store=environment.immutable_store,
        runtime_use=runtime,
        provider=replay_provider,
        clock=SequenceClock(_time("2026-08-06T12:09:00Z")),
    )
    restarted_bridge = LiveIntelligenceBridgeService(
        activation_service=environment.activation_service,
        pack=environment.pack,
        store=environment.immutable_store,
        authorizer=replay_reasoning,
        operation_binding=append_binding,
    )
    restarted_brief_service = LiveBriefSynthesisService(
        activation_service=environment.activation_service,
        pack=environment.pack,
        store=environment.immutable_store,
        reasoning=replay_reasoning,
        execution_binding=execution_binding,
        append_binding=append_binding,
    )
    derivation_replay = await restarted_bridge.derive(derivation_request)
    brief_replay = await restarted_brief_service.synthesize(brief_request)

    if provider.calls != 1:
        raise AssertionError("LIVE Brief replay invoked the provider more than once")
    if replay_provider.calls != 0:
        raise AssertionError("fresh-service replay invoked the forbidden provider")
    if not derivation_replay.replayed or not brief_replay.replayed:
        raise AssertionError("LIVE bridge did not expose exact replay")
    if brief.brief.mode is not IntelligenceResourceMode.LIVE:
        raise AssertionError("P1F Brief is not explicitly LIVE")
    if brief.brief != brief_replay.brief:
        raise AssertionError("LIVE Brief replay changed canonical material")

    projection = {
        "contract": "ace.market-intelligence.p1f-live-bridge-evidence/v1alpha1",
        "mode": brief.brief.mode.value,
        "source_record_count": 10,
        "derivation_record_kinds": [
            item.record_kind for item in derivation.transaction_receipt.records
        ],
        "brief_record_kinds": [item.record_kind for item in brief.transaction_receipt.records],
        "shift_id": derivation.shift.resource_id,
        "signal_id": derivation.signal.resource_id,
        "attention_disposition": derivation.attention_receipt.disposition.value,
        "routing_rule_id": derivation.attention_receipt.routing_rule_id,
        "brief_template_id": derivation.attention_receipt.brief_template_id,
        "brief_id": brief.brief.resource_id,
        "brief_title": brief.brief.title,
        "claim_count": len(brief.brief.claims),
        "citation_count": len(brief.brief.citations),
        "provider_calls": provider.calls,
        "replay_provider_calls": replay_provider.calls,
        "derivation_replayed": derivation_replay.replayed,
        "brief_replayed": brief_replay.replayed,
        "delivery_authority": derivation.attention_receipt.delivery_authority,
        "external_actions": [],
        "observed_price_change": {"baseline": 1200.0, "current": 1080.0},
    }
    return projection, P1FRun(
        source_environment=environment,
        bridge=bridge,
        derivation_request=derivation_request,
        derivation=derivation,
        brief_service=brief_service,
        brief_request=brief_request,
        brief=brief,
    )


def _rebuild(model, **updates):
    material = model.model_dump(
        mode="python",
        exclude={"request_id", "request_digest"},
    )
    material.update(updates)
    return type(model).model_validate(material)


async def run_negative_cases() -> tuple[str, ...]:
    _, result = await run_acceptance()
    exercised = []

    divergent_derivation = _rebuild(
        result.derivation_request,
        requested_at=result.derivation_request.requested_at + timedelta(seconds=1),
    )
    try:
        await result.bridge.derive(divergent_derivation)
    except LiveIntelligenceBridgeReplayConflict:
        exercised.append("divergent_derivation_replay")
    else:
        raise AssertionError("divergent LIVE derivation replay did not fail closed")

    divergent_brief = _rebuild(
        result.brief_request,
        reasoning_attempt_key="reasoning:market-intelligence:p1f:divergent",
    )
    try:
        await result.brief_service.synthesize(divergent_brief)
    except LiveBriefSynthesisReplayConflict:
        exercised.append("divergent_brief_replay")
    else:
        raise AssertionError("divergent LIVE Brief replay did not fail closed")

    prepared_request = _rebuild(
        result.brief_request,
        synthesis_key="synthesis:market-intelligence:p1f:prepared-forgery",
        mode=IntelligenceResourceMode.PREPARED,
    )
    try:
        await result.brief_service.synthesize(prepared_request)
    except LiveBriefSynthesisError:
        exercised.append("prepared_mode_promotion")
    else:
        raise AssertionError("PREPARED request entered the LIVE Brief service")

    forged_current = result.derivation_request.current.model_copy(
        update={
            "available_at": result.derivation_request.current.available_at + timedelta(seconds=1)
        }
    )
    unadmitted = _rebuild(
        result.derivation_request,
        derivation_key="derivation:market-intelligence:p1f:unadmitted-coordinate",
        current=forged_current,
    )
    try:
        await result.bridge.derive(unadmitted)
    except LiveIntelligenceBridgeError:
        exercised.append("unadmitted_snapshot_coordinate")
    else:
        raise AssertionError("unadmitted snapshot coordinate entered LIVE derivation")

    return tuple(sorted(exercised))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    projection, _ = asyncio.run(run_acceptance())
    rendered = json.dumps(projection, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
