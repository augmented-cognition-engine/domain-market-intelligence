"""Second-domain falsification through the public ACE pack and activation contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from importlib.resources import files

from ace.intelligence import (
    ActivationState,
    AuthorityBindingV1,
    CapabilityBindingV1,
    OrganizationOverlayV1,
)
from ace.intelligence.packs import (
    bind_prepared_activation,
    compile_overlay,
    compile_pack_document,
    prepare_activation_revision,
    prepare_domain_activation,
)


def _compile(package: str):
    root = files(package)
    manifest_bytes = root.joinpath("manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    resources = {
        item["path"]: root.joinpath(item["path"]).read_bytes() for item in manifest["resources"]
    }
    return manifest, compile_pack_document(manifest_bytes, resources)


def _active_revision(manifest: dict, pack, *, product_id: str, occurred_at: datetime):
    overlay = compile_overlay(
        pack,
        OrganizationOverlayV1(
            overlay_id=f"gi2_{pack.metadata.pack_id}",
            version="1.0.0",
            pack_id=pack.metadata.pack_id,
            pack_version=pack.metadata.version,
            pack_digest=pack.pack_digest,
        ),
    )
    requirement = manifest["capability_requirements"][0]
    authority = manifest["authority_requests"][0]
    spec = prepare_domain_activation(
        product_id=product_id,
        activation_key=pack.metadata.pack_id,
        pack=pack,
        overlay=overlay,
        compilation_receipt_ref=f"receipt:gi2-{pack.metadata.pack_id}-compile",
        conformance_receipt_refs=(f"receipt:gi2-{pack.metadata.pack_id}-conformance",),
        capability_bindings=(
            CapabilityBindingV1(
                requirement_id=requirement["requirement_id"],
                capability=requirement["capability"],
                contract=requirement["contract"],
                implementation_id=f"gi2_{pack.metadata.pack_id}_fixture_source",
                implementation_version="1.0.0",
                artifact_digest="sha256:"
                + ("a" if pack.metadata.pack_id == "market_intelligence" else "b") * 64,
            ),
        ),
        authority_bindings=(
            AuthorityBindingV1(
                request_id=authority["request_id"],
                authority=authority["authority"],
                grant_ref=f"authority_grant:gi2-{pack.metadata.pack_id}-read",
            ),
        ),
    )
    return prepare_activation_revision(
        spec=spec,
        state=ActivationState.ACTIVE,
        actor_ref="principal:gi2-reviewer",
        approval_receipt_ref=f"receipt:gi2-{pack.metadata.pack_id}-approval",
        occurred_at=occurred_at,
    )


def test_market_and_world_compile_and_bind_without_domain_leakage() -> None:
    market_manifest, market_pack = _compile("domain_packs.market_intelligence")
    world_manifest, world_pack = _compile("domain_packs.world_intelligence")

    assert market_pack.metadata.pack_id == "market_intelligence"
    assert world_pack.metadata.pack_id == "world_intelligence"
    assert market_pack.pack_digest != world_pack.pack_digest
    assert market_manifest["compatibility"] == world_manifest["compatibility"]

    market_entities = {
        item["entity_type_id"]
        for item in json.loads(
            files("domain_packs.market_intelligence")
            .joinpath("modules/ontology.json")
            .read_text(encoding="utf-8")
        )["entity_types"]
    }
    world_entities = {
        item["entity_type_id"]
        for item in json.loads(
            files("domain_packs.world_intelligence")
            .joinpath("modules/ontology.json")
            .read_text(encoding="utf-8")
        )["entity_types"]
    }
    assert market_entities == {"competitor", "product"}
    assert "actor" in world_entities and "claim" in world_entities
    assert market_entities.isdisjoint(world_entities)

    now = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    product_id = "product:gi2-cross-domain"
    market_active = _active_revision(
        market_manifest, market_pack, product_id=product_id, occurred_at=now
    )
    world_active = _active_revision(
        world_manifest, world_pack, product_id=product_id, occurred_at=now
    )

    market_binding = bind_prepared_activation(pack=market_pack, revision=market_active)
    world_binding = bind_prepared_activation(pack=world_pack, revision=world_active)

    assert market_binding.revision.activation_id != world_binding.revision.activation_id
    assert market_binding.pack.metadata.pack_id == "market_intelligence"
    assert world_binding.pack.metadata.pack_id == "world_intelligence"

    market_retired = prepare_activation_revision(
        spec=market_active.spec,
        state=ActivationState.RETIRED,
        actor_ref="principal:gi2-reviewer",
        approval_receipt_ref="receipt:gi2-market-retirement",
        occurred_at=now + timedelta(minutes=1),
        prior_revision=market_active,
    )
    assert market_retired.activation_id == market_active.activation_id
    assert market_retired.state is ActivationState.RETIRED

    # Retiring Market appends only to Market's activation history. The exact
    # World binding remains valid and byte-identical.
    world_rebound = bind_prepared_activation(pack=world_pack, revision=world_active)
    assert world_rebound == world_binding
    assert world_rebound.revision.state is ActivationState.ACTIVE
