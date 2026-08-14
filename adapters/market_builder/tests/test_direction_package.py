from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from ace.application import GovernedDestinationDeliveryService, delivery_payload_digest
from ace.core.agent_composition import ExactArtifactReferenceV1Alpha1
from ace.core.external_operations import (
    DestinationDefinitionV1Alpha1,
    DestinationDeliveryIntentV1Alpha1,
    DestinationLifecycle,
    DestinationPolicyCoordinateV1Alpha1,
    DestinationPolicyKind,
    DestinationRevisionV1Alpha1,
    exact_external_reference,
)
from ace.core.runtime_use import AuthenticatedRuntimeContextV1Alpha1
from ace_market_builder import (
    ApprovedMarketClaimV1Alpha1,
    MarketDirectionPackageV1Alpha1,
    prepare_market_direction_delivery,
)

NOW = datetime(2026, 8, 14, 19, tzinfo=UTC)
PRODUCT = "product:market-v1"


def _ref(identifier: str, contract: str, digit: str) -> ExactArtifactReferenceV1Alpha1:
    return ExactArtifactReferenceV1Alpha1(
        artifact_id=identifier,
        artifact_digest="sha256:" + digit * 64,
        artifact_contract=contract,
    )


def _package() -> MarketDirectionPackageV1Alpha1:
    citation = _ref("observation:terra-price", "ace.intelligence.observation/v1alpha1", "3")
    return MarketDirectionPackageV1Alpha1(
        product_id=PRODUCT,
        source_brief=_ref("brief:terra-price", "ace.intelligence.brief/v1alpha1", "1"),
        decision=_ref("decision:terra-positioning", "ace.core.decision/v1alpha1", "2"),
        objective="Prepare a cited page-story direction for the approved Terra pricing response.",
        audience=("AI platform evaluation leaders",),
        story_architecture=("Lead with the verified price move", "Explain buyer implications", "Close with evidence"),
        content_hierarchy=("Hero", "Price comparison", "Implications", "Evidence and limitations"),
        approved_claims=(
            ApprovedMarketClaimV1Alpha1(
                claim_id="claim:terra-price-move",
                statement="The recorded July publication changes Terra input pricing from USD 2.50 to USD 2.00.",
                citations=(citation,),
                approval_ref="approval:claim-terra-price-move",
                limitations=("Recorded publication evidence; current network pricing is unverified.",),
            ),
        ),
        constraints=("Do not imply independent corroboration", "Keep every numeric claim cited"),
        open_questions=("Which customer proof may be added after separate review?",),
        required_assets=("Approved product marks", "Accessible price comparison component"),
        prepared_at=NOW,
    )


def _destination() -> DestinationRevisionV1Alpha1:
    definition = DestinationDefinitionV1Alpha1(
        product_id=PRODUCT,
        destination_key="reference-direction-mailbox",
        adapter_contract="ace.core.external-destination-adapter/v1alpha1",
        protocol_refs=("protocol:digest-mailbox-v1",),
        capability_refs=("delivery",),
        recipient_binding_kind="opaque_recipient_ref",
    )
    return DestinationRevisionV1Alpha1(
        definition=exact_external_reference(definition),
        sequence=1,
        lifecycle=DestinationLifecycle.ACTIVE,
        policies=tuple(
            DestinationPolicyCoordinateV1Alpha1(
                kind=kind,
                policy_ref=f"policy:{kind.value}",
                state_id=f"destination_policy:{kind.value}",
                material_digest="sha256:" + f"{index + 4:x}" * 64,
            )
            for index, kind in enumerate(DestinationPolicyKind)
        ),
        revised_at=NOW,
    )


def _context() -> AuthenticatedRuntimeContextV1Alpha1:
    return AuthenticatedRuntimeContextV1Alpha1(
        product_id=PRODUCT,
        actor_ref="principal:owner",
        authentication_receipt_ref="authentication:market-direction",
        authentication_receipt_digest="sha256:" + "9" * 64,
        authenticated_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


def test_direction_package_is_content_addressed_direction_not_a_rendered_artifact() -> None:
    package = _package()
    replay = MarketDirectionPackageV1Alpha1.model_validate(package.model_dump(mode="python"))

    assert replay == package
    assert package.package_id.startswith("market_direction_package:")
    assert package.package_digest.startswith("sha256:")
    assert package.delivery_authority is False
    assert package.external_effect_occurred is False
    assert not hasattr(package, "rendered_html")
    assert not hasattr(package, "design_file")


def test_prepared_package_binds_exact_artifact_and_destination_before_ac5() -> None:
    package = _package()
    prepared = prepare_market_direction_delivery(
        package,
        source_manifest=_ref("manifest:market-direction", "ace.core.stage-run-manifest/v1alpha1", "4"),
        target_ref="ac5_delivery_gate:market-direction",
        prepared_at=NOW,
    )
    destination = _destination()
    intent = DestinationDeliveryIntentV1Alpha1(
        product_id=PRODUCT,
        authenticated_context=_context(),
        prepared_handoff=ExactArtifactReferenceV1Alpha1(
            artifact_id=str(prepared.package_id),
            artifact_digest=str(prepared.package_digest),
            artifact_contract=prepared.contract,
        ),
        destination_revision=exact_external_reference(destination),
        recipient_ref="recipient:reference-mailbox",
        payload_artifacts=prepared.artifacts,
        payload_digest=delivery_payload_digest(prepared.artifacts),
        idempotency_key="delivery:market-direction-v1",
        retry_policy_ref="retry:lookup-first",
        cancellation_ref="cancel:market-direction-v1",
        requested_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
    )

    assert GovernedDestinationDeliveryService._validate_intent(prepared, intent, destination) == intent
    assert prepared.artifacts[0].artifact_id == package.package_id
    assert prepared.external_send_occurred is False

    crossed_artifacts = (_ref("package:other", package.contract, "a"),)
    crossed = DestinationDeliveryIntentV1Alpha1(
        **{
            **intent.model_dump(mode="python", exclude={"intent_id", "intent_digest"}),
            "payload_artifacts": crossed_artifacts,
            "payload_digest": delivery_payload_digest(crossed_artifacts),
        }
    )
    with pytest.raises(Exception, match="exact prepared payload"):
        GovernedDestinationDeliveryService._validate_intent(prepared, crossed, destination)


def test_direction_package_requires_exact_brief_and_user_decision() -> None:
    package = _package()
    with pytest.raises(ValueError, match="exact user Decision"):
        MarketDirectionPackageV1Alpha1(
            **{
                **package.model_dump(mode="python", exclude={"package_id", "package_digest"}),
                "decision": _ref("proposal:not-a-decision", "ace.intelligence.brief/v1alpha1", "b"),
            }
        )
