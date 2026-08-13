"""Market Intelligence 0.8 public resource-plane acceptance.

This composes the existing PREPARED competitive-intelligence journey and reads
it through the same domain-neutral resource plane used by World Intelligence.
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from p1d1_prepared_brief_acceptance import _time
from p1e_governed_feedback_acceptance import run_positive

from ace.application import (
    CompositeIntelligenceResourceProjectionReader,
    DecisionOutcomeFeedbackResourceProjectionReader,
    IntelligenceLedgerResourceProjectionReader,
    IntelligenceResourcePlaneService,
)
from ace.core import (
    AppendOnlyTransactionRequestV1,
    GovernedActionAuthorizationRequestV1Alpha1,
    GovernedStateHeadPreconditionV1Alpha1,
    ImmutableRecordV1,
    canonical_hash,
)
from ace.core.runtime_use import AuthorityUseReceiptV1Alpha1
from ace.intelligence import (
    BriefV1Alpha1,
    CaseV1Alpha1,
    IntelligenceRecordKind,
    IntelligenceResourceKind,
    IntelligenceResourceMode,
    IntelligenceResourceQueryV1Alpha1,
    LineageReferenceV1Alpha1,
    LineageRelation,
    LineageResourceKind,
    ShiftV1Alpha1,
    SignalV1Alpha1,
)

READ_GRANT = "authority_grant:market-intelligence-os-read"
READ_KINDS = (
    IntelligenceResourceKind.ENTITY,
    IntelligenceResourceKind.OBSERVATION,
    IntelligenceResourceKind.SIGNAL,
    IntelligenceResourceKind.SHIFT,
    IntelligenceResourceKind.CASE,
    IntelligenceResourceKind.BRIEF,
    IntelligenceResourceKind.DECISION,
    IntelligenceResourceKind.OUTCOME,
    IntelligenceResourceKind.FEEDBACK,
)
REQUIRED_KINDS = set(READ_KINDS)


class ExactReadAuthority:
    async def resolve_authority_use(self, **request) -> AuthorityUseReceiptV1Alpha1:
        if (
            request["operation"] != "query_intelligence_resources"
            or request["authority"] != "observe_read"
            or request["grant_ref"] != READ_GRANT
        ):
            raise ValueError("Market resource query crossed the exact read boundary")
        context = request["context"]
        return AuthorityUseReceiptV1Alpha1(
            product_id=context.product_id,
            actor_ref=context.actor_ref,
            authenticated_context=context,
            use_subject_ref=request["use_subject_ref"],
            use_subject_digest=request["use_subject_digest"],
            operation=request["operation"],
            authority=request["authority"],
            grant_ref=READ_GRANT,
            grant_hash="9" * 64,
            evaluated_at=request["evaluated_at"],
            expires_at=context.expires_at,
            state_head_precondition=GovernedStateHeadPreconditionV1Alpha1(
                state_kind="authority_grant",
                product_id=context.product_id,
                state_id=READ_GRANT,
                sequence=1,
                revision_id="authority_revision:market-intelligence-os-read",
                commit_receipt_id="authority_receipt:market-intelligence-os-read",
            ),
        )


def _reader(store):
    return CompositeIntelligenceResourceProjectionReader(
        IntelligenceLedgerResourceProjectionReader(store=store, degrade_unsupported=False),
        DecisionOutcomeFeedbackResourceProjectionReader(store=store, degrade_unsupported=False),
    )


def _lineage(record: ImmutableRecordV1, value) -> LineageReferenceV1Alpha1:
    return LineageReferenceV1Alpha1(
        resource_kind=LineageResourceKind(record.record_kind),
        relation=LineageRelation.DERIVED_FROM,
        resource_id=str(value.resource_id),
        resource_digest=str(value.resource_digest),
        resource_as_of=value.as_of,
        resource_available_at=record.available_at,
    )


async def _assemble_case(result) -> CaseV1Alpha1:
    env = result.environment
    store = env.p1d1.environment.store
    brief = BriefV1Alpha1.model_validate(env.brief_record.payload)
    direct_ids = {
        item.resource_id
        for item in brief.lineage
        if item.resource_kind in {LineageResourceKind.SHIFT, LineageResourceKind.SIGNAL}
    }
    records = [record for record in store.records.values() if record.record_key in direct_ids]
    values = []
    for record in records:
        model = {
            IntelligenceRecordKind.SHIFT.value: ShiftV1Alpha1,
            IntelligenceRecordKind.SIGNAL.value: SignalV1Alpha1,
        }.get(record.record_kind)
        if model is None:
            continue
        values.append((record, model.model_validate(record.payload)))
    if {record.record_kind for record, _ in values} != {
        IntelligenceRecordKind.SHIFT.value,
        IntelligenceRecordKind.SIGNAL.value,
    }:
        raise AssertionError(
            "Market 0.8 Case lost the exact Shift/Signal closure of its reviewed Brief"
        )

    product_id = env.auth.product_id
    requested_at = _time("2026-08-06T15:36:00Z")
    closure_digest = "sha256:" + canonical_hash(
        sorted(record.material_hash for record, _ in values)
    )
    activation_head = store.governed_state_heads[
        (
            env.rev4.commit_receipt.state_kind,
            product_id,
            env.rev4.commit_receipt.state_id,
        )
    ]
    authorization = await env.authorizer.authorize_action(
        GovernedActionAuthorizationRequestV1Alpha1(
            authorization_key="case:market-intelligence-os:competitive-price-move",
            product_id=product_id,
            authenticated_context=env.auth,
            execution_binding=env.p1d1.environment.append_binding,
            operation="append_immutable_records",
            subject_ref="case_closure:competitive-price-move",
            subject_digest=closure_digest,
            requested_at=requested_at,
            required_state_preconditions=(
                GovernedStateHeadPreconditionV1Alpha1.from_head(activation_head),
                env.p1d1.environment.append_binding.state_head_precondition,
            ),
        )
    )
    signal = next(value for _, value in values if isinstance(value, SignalV1Alpha1))
    case = CaseV1Alpha1(
        product_id=product_id,
        mode=IntelligenceResourceMode.PREPARED,
        activation_revision=brief.activation_revision,
        as_of=max(value.as_of for _, value in values),
        lineage=tuple(_lineage(record, value) for record, value in values),
        case_type_ref="case_type:competitive_price_move",
        title="Northstar Edge X1 competitive price move",
        purpose="Orient the exact competitive change before analyst disposition and measurement.",
        subject_refs=signal.subject_refs,
        assembled_at=authorization.authorized_at,
    )
    record = ImmutableRecordV1(
        product_id=product_id,
        record_space=case.mode.value,
        record_kind=IntelligenceRecordKind.CASE.value,
        record_key=str(case.resource_id),
        payload_contract=case.contract,
        payload=case.model_dump(mode="python"),
        as_of=case.as_of,
        available_at=case.assembled_at,
        processing_order=0,
    )
    append = AppendOnlyTransactionRequestV1(
        product_id=product_id,
        record_space=case.mode.value,
        transaction_key=f"market-intelligence-os-case:{case.resource_id}",
        records=(record,),
        submitted_at=case.assembled_at,
        governed_state_preconditions=authorization.state_preconditions,
    )
    receipt = await store.append(append)
    if receipt != append.receipt():
        raise AssertionError("Market 0.8 Case append returned divergent receipt material")
    return case


def _identity(item) -> tuple[str, str, int, str]:
    ref = item.reference
    return ref.resource_kind.value, ref.resource_id, ref.revision, ref.resource_digest


async def run_acceptance(*, core_candidate_commit: str = "working-tree") -> dict:
    result = await run_positive()
    case = await _assemble_case(result)
    env = result.environment
    store = env.p1d1.environment.store
    records = tuple(store.records.values())
    request = IntelligenceResourceQueryV1Alpha1(
        authenticated_context=env.auth,
        product_id=env.auth.product_id,
        authority_grant_ref=READ_GRANT,
        resource_kinds=READ_KINDS,
        subject_refs=(),
        as_of=max(record.as_of for record in records),
        available_at=max(record.available_at for record in records),
        page_size=200,
    )
    evaluated_at = _time("2026-08-06T15:40:00Z")
    authority = ExactReadAuthority()
    first = await IntelligenceResourcePlaneService(
        reader=_reader(store), authority=authority
    ).query(request, evaluated_at=evaluated_at)
    reopened = await IntelligenceResourcePlaneService(
        reader=_reader(store), authority=authority
    ).query(request, evaluated_at=evaluated_at + timedelta(seconds=1))
    if first.next_cursor is not None or reopened.next_cursor is not None:
        raise AssertionError("Market 0.8 proof exceeded its bounded single-page acceptance")
    if first.query_id != reopened.query_id or tuple(map(_identity, first.items)) != tuple(
        map(_identity, reopened.items)
    ):
        raise AssertionError("Market resource plane did not reopen exact projected identities")
    kinds = {item.reference.resource_kind for item in first.items}
    missing = sorted(kind.value for kind in REQUIRED_KINDS - kinds)
    if missing:
        raise AssertionError(
            f"Market 0.8 loop is missing {missing}; present={sorted(kind.value for kind in kinds)}; "
            f"degraded={first.degraded_reason_refs}"
        )
    if first.degraded_reason_refs:
        raise AssertionError(
            f"Market resource page degraded unexpectedly: {first.degraded_reason_refs}"
        )
    if any(item.reference.product_id != env.auth.product_id for item in first.items):
        raise AssertionError("Market resource page crossed product scope")
    counts = {
        kind.value: sum(item.reference.resource_kind is kind for item in first.items)
        for kind in sorted(kinds, key=lambda item: item.value)
    }
    return {
        "contract": "ace.market-intelligence.intelligence-os-acceptance/v1alpha1",
        "core_candidate_commit": core_candidate_commit,
        "domain": "market_intelligence",
        "product_id": env.auth.product_id,
        "query": {
            "query_id": first.query_id,
            "page_state": first.state.value,
            "resource_count": len(first.items),
            "resource_counts": counts,
            "exact_restart_reopen": True,
            "single_page": True,
            "authority": first.authority_use.authority,
        },
        "loop": {
            "required_kinds": sorted(kind.value for kind in REQUIRED_KINDS),
            "all_present": True,
            "case_id": str(case.resource_id),
            "decision_disposition": result.decision.decision.intent.disposition.value,
            "action_disposition": result.decision.decision.intent.action_disposition.value,
            "feedback_live_effect": result.proposal.live_effect,
        },
        "limitations": {
            "prepared_fixture": True,
            "external_action": False,
            "delivery_authority": False,
            "beneficial_impact_claimed": False,
        },
    }


def main() -> None:
    print(json.dumps(asyncio.run(run_acceptance()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
