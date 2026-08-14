from __future__ import annotations

import hashlib
import json
import tomllib
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

PACK_ROOT = Path(__file__).resolve().parents[1] / "market_intelligence"
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PACK_ROOT / "manifest.json"
ONTOLOGY_PATH = PACK_ROOT / "modules" / "ontology.json"
SOURCE_MAPPING_PATH = PACK_ROOT / "modules" / "source_mapping.json"
DETECTION_PATH = PACK_ROOT / "modules" / "detection.json"
SYNTHESIS_PATH = PACK_ROOT / "modules" / "synthesis.json"
PERSONAS_PATH = PACK_ROOT / "modules" / "personas.json"
CONFORMANCE_MANIFEST_PATH = PACK_ROOT / "conformance" / "manifest.json"
PUBLIC_SOURCE_BOUNDARY_PATH = (
    PACK_ROOT / "conformance" / "public_product_price_boundary.json"
)
PRICE_MOVE_FIXTURE_PATH = PACK_ROOT / "conformance" / "p1_price_move_golden.json"
NEGATIVE_CASES_PATH = PACK_ROOT / "conformance" / "p1_price_move_negative_cases.json"
DURABLE_EXPECTED_PATH = (
    PACK_ROOT / "conformance" / "p1c_durable_price_move_expected.json"
)
ACTIVATION_FIXTURE_PATH = (
    PACK_ROOT / "conformance" / "activation_golden_fixture.json"
)
RECORDED_SOURCES_PATH = (
    PACK_ROOT / "conformance" / "openai_terra_price_recorded_sources.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _core_compiler():
    try:
        from ace.intelligence.packs import compile_pack_document
    except ModuleNotFoundError as exc:
        if exc.name in {"ace", "ace.intelligence"}:
            pytest.skip(
                "ACE Core is installed alongside this extension, not declared in its local lockfile"
            )
        raise
    return compile_pack_document


def _compiled_pack():
    compile_pack_document = _core_compiler()
    manifest = _load_json(MANIFEST_PATH)
    return compile_pack_document(
        MANIFEST_PATH.read_bytes(),
        {
            resource["path"]: (PACK_ROOT / resource["path"]).read_bytes()
            for resource in manifest["resources"]
        },
    )


def _attributes_by_entity(
    ontology: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        entity["entity_type_id"]: {
            attribute["attribute_id"]: attribute
            for attribute in entity.get("attributes", [])
        }
        for entity in ontology["entity_types"]
    }


def _matches_value_type(value: Any, value_type: str) -> bool:
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise AssertionError(
        f"fixture test does not yet support ontology value type: {value_type}"
    )


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None and parsed.utcoffset() is not None
    return parsed


def _activation_bindings(boundary: dict[str, Any]):
    from ace.intelligence import AuthorityBindingV1, CapabilityBindingV1

    capability_payload = dict(boundary["prepared_binding"]["capability"])
    identity_material = capability_payload.pop("artifact_identity_material")
    assert capability_payload["artifact_digest"] == (
        f"sha256:{hashlib.sha256(identity_material.encode()).hexdigest()}"
    )
    return (
        CapabilityBindingV1(**capability_payload),
        AuthorityBindingV1(**boundary["prepared_binding"]["authority"]),
    )


def _prepared_binding(compiled, fixture: dict[str, Any], boundary: dict[str, Any]):
    from ace.intelligence import ActivationState, OrganizationOverlayV1
    from ace.intelligence.packs import (
        bind_prepared_activation,
        compile_overlay,
        prepare_activation_revision,
        prepare_domain_activation,
    )

    scenario = fixture["scenario"]
    capability_binding, authority_binding = _activation_bindings(boundary)
    overlay = compile_overlay(
        compiled,
        OrganizationOverlayV1(
            overlay_id="market_intelligence_conformance",
            version=fixture["fixture_version"],
            pack_id=compiled.metadata.pack_id,
            pack_version=compiled.metadata.version,
            pack_digest=compiled.pack_digest,
        ),
    )
    activation_spec = prepare_domain_activation(
        product_id=scenario["product_id"],
        activation_key=scenario["activation_key"],
        pack=compiled,
        overlay=overlay,
        compilation_receipt_ref=scenario["compilation_receipt_ref"],
        conformance_receipt_refs=(scenario["conformance_receipt_ref"],),
        capability_bindings=(capability_binding,),
        authority_bindings=(authority_binding,),
    )
    revision = prepare_activation_revision(
        spec=activation_spec,
        state=ActivationState.ACTIVE,
        actor_ref=scenario["actor_ref"],
        approval_receipt_ref=scenario["approval_receipt_ref"],
        occurred_at=_parse_time(scenario["activation_occurred_at"]),
    )
    return bind_prepared_activation(pack=compiled, revision=revision)


def _prepared_observations_and_snapshots(
    *,
    binding,
    fixture: dict[str, Any],
):
    from ace.core import (
        CanonicalSourceSnapshotV1Alpha1,
        SourceAcquisitionMode,
        canonical_json,
    )
    from ace.intelligence import (
        ResolvedSubjectBindingV1Alpha1,
        interpret_prepared_source_mapping,
    )

    observations = []
    snapshots = []
    for item in fixture["snapshots"]:
        source = item["source"]
        payload_json = canonical_json(source["captured_payload"])
        source_snapshot = CanonicalSourceSnapshotV1Alpha1(
            source_definition_ref=source["source_definition_ref"],
            source_type_ref=source["source_type_ref"],
            source_uri=source["source_uri"],
            captured_payload_json=payload_json,
            captured_payload_digest=source["captured_payload_digest"],
            source_published_at=(
                None
                if source["source_published_at"] is None
                else _parse_time(source["source_published_at"])
            ),
            event_effective_at=(
                None
                if source["event_effective_at"] is None
                else _parse_time(source["event_effective_at"])
            ),
            observed_at=_parse_time(source["observed_at"]),
            ingested_at=_parse_time(source["ingested_at"]),
            locator=source["locator"],
            acquisition_mode=SourceAcquisitionMode(source["acquisition_mode"]),
            acquisition_receipt_ref=source["acquisition_receipt_ref"],
            acquisition_receipt_digest=source["acquisition_receipt_digest"],
        )
        subject = item["resolved_subject"]
        subject_binding = ResolvedSubjectBindingV1Alpha1(
            product_id=fixture["scenario"]["product_id"],
            activation_revision=binding.reference,
            subject_binding_id=subject["subject_binding_id"],
            entity_type_id=subject["entity_type_id"],
            entity_ref=subject["entity_ref"],
        )
        result = interpret_prepared_source_mapping(
            binding=binding,
            mapping_id=fixture["pack"]["source_mapping_id"],
            source_snapshot=source_snapshot,
            subject_binding=subject_binding,
        )
        observations.append(result.observation)
        snapshots.append(result.entity_snapshot)
    return observations, snapshots


def _apply_negative_case(
    fixture: dict[str, Any], case: dict[str, Any]
) -> dict[str, Any]:
    mutated = deepcopy(fixture)
    for operation in case["operations"]:
        assert operation["op"] == "replace"
        tokens = [
            token.replace("~1", "/").replace("~0", "~")
            for token in operation["path"].split("/")[1:]
        ]
        parent: Any = mutated
        for token in tokens[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        key = tokens[-1]
        if isinstance(parent, list):
            parent[int(key)] = operation["value"]
        else:
            assert key in parent
            parent[key] = operation["value"]
    return mutated


def test_inert_pack_files_and_price_move_fixture_are_self_consistent() -> None:
    manifest = _load_json(MANIFEST_PATH)
    ontology = _load_json(ONTOLOGY_PATH)
    source_mapping = _load_json(SOURCE_MAPPING_PATH)
    detection = _load_json(DETECTION_PATH)
    synthesis = _load_json(SYNTHESIS_PATH)
    personas = _load_json(PERSONAS_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)

    artifact_files = sorted(path for path in PACK_ROOT.rglob("*") if path.is_file())
    assert artifact_files
    assert {path.suffix for path in artifact_files} == {".json"}

    resources = {resource["path"]: resource for resource in manifest["resources"]}
    assert set(resources) == {
        "modules/ontology.json",
        "modules/source_mapping.json",
        "modules/detection.json",
        "modules/synthesis.json",
        "modules/personas.json",
    }
    for relative_path, resource in resources.items():
        payload = (PACK_ROOT / relative_path).read_bytes()
        assert resource["digest"] == f"sha256:{hashlib.sha256(payload).hexdigest()}"
    assert manifest["modules"] == [
        {
            "module_id": "market_ontology",
            "contract": "ace.intelligence.ontology/v1alpha1",
            "resource_id": "market_ontology",
            "depends_on": [],
        },
        {
            "module_id": "market_source_mapping",
            "contract": "ace.intelligence.source-mapping/v1alpha1",
            "resource_id": "market_source_mapping",
            "depends_on": ["market_ontology"],
        },
        {
            "module_id": "market_detection",
            "contract": "ace.intelligence.detection/v1alpha1",
            "resource_id": "market_detection",
            "depends_on": ["market_ontology"],
        },
        {
            "module_id": "market_synthesis",
            "contract": "ace.intelligence.synthesis/v1alpha1",
            "resource_id": "market_synthesis",
            "depends_on": [],
        },
        {
            "module_id": "market_personas",
            "contract": "ace.intelligence.personas/v1alpha1",
            "resource_id": "market_personas",
            "depends_on": ["market_detection", "market_synthesis"],
        },
    ]
    assert manifest["capability_requirements"] == [
        {
            "requirement_id": "public_product_snapshot",
            "capability": "source_snapshot",
            "contract": "ace.source.snapshot/v1alpha1",
        }
    ]
    assert manifest["authority_requests"] == [
        {
            "request_id": "read_public_product_source",
            "authority": "source_read",
        }
    ]
    assert boundary["pack_requirements"] == {
        "capability_requirement_id": "public_product_snapshot",
        "capability": "source_snapshot",
        "capability_contract": "ace.source.snapshot/v1alpha1",
        "authority_request_id": "read_public_product_source",
        "authority": "source_read",
    }
    assert boundary["runtime_status"] == "compiled_prepared_only"
    assert boundary["prepared_binding"]["capability"]["secret_ref"] is None
    assert boundary["source_mapping"] == {
        "contract": source_mapping["contract"],
        "module_id": source_mapping["module_id"],
        "mapping_id": source_mapping["mappings"][0]["mapping_id"],
        "subject_binding_id": source_mapping["mappings"][0]["subject_binding_id"],
        "entity_type_id": source_mapping["mappings"][0]["entity_type_id"],
    }
    assert "normalization_mappings" not in boundary
    assert fixture["fixture_scope"] == "prepared_conformance_input"
    assert fixture["scenario"]["resource_mode"] == "prepared"
    assert fixture["scenario"]["live_admission"] == "forbidden"
    assert fixture["public_source_boundary"] == {
        "path": PUBLIC_SOURCE_BOUNDARY_PATH.name,
        "boundary_id": boundary["boundary_id"],
        "boundary_version": boundary["boundary_version"],
    }

    assert fixture["pack"] == {
        "pack_id": manifest["metadata"]["pack_id"],
        "pack_version": manifest["metadata"]["version"],
        "ontology_module_id": ontology["module_id"],
        "source_mapping_module_id": source_mapping["module_id"],
        "source_mapping_id": source_mapping["mappings"][0]["mapping_id"],
        "subject_binding_id": source_mapping["mappings"][0]["subject_binding_id"],
        "detection_module_id": detection["module_id"],
        "detector_id": detection["numeric_delta_rules"][0]["detector_id"],
        "synthesis_module_id": synthesis["module_id"],
        "brief_template_id": synthesis["brief_templates"][0]["template_id"],
        "personas_module_id": personas["module_id"],
        "routed_persona_id": personas["personas"][0]["persona_id"],
    }

    entity_attributes = _attributes_by_entity(ontology)
    assert set(entity_attributes) == {"competitor", "product"}
    assert {
        attribute_id: declaration["value_type"]
        for attribute_id, declaration in entity_attributes["product"].items()
    } == {
        "name": "string",
        "price": "number",
        "currency": "string",
    }
    assert ontology["relation_types"] == [
        {
            "relation_type_id": "makes",
            "source_entity_types": ["competitor"],
            "target_entity_types": ["product"],
        }
    ]

    snapshots = fixture["snapshots"]
    assert len(snapshots) == 2
    assert [snapshot["source"]["observed_at"] for snapshot in snapshots] == sorted(
        snapshot["source"]["observed_at"] for snapshot in snapshots
    )
    assert all(_parse_time(snapshot["source"]["observed_at"]) for snapshot in snapshots)
    context = fixture["comparison_context"]
    assert context["competitor"]["entity_key"] == "competitor:openai"
    assert context["relation"]["target_entity_key"] == "product:gpt-5-6-terra-input-tokens"
    assert (
        len({snapshot["resolved_subject"]["entity_ref"] for snapshot in snapshots}) == 1
    )
    assert (
        len({snapshot["source"]["source_definition_ref"] for snapshot in snapshots})
        == 1
    )
    assert {snapshot["source"]["source_uri"] for snapshot in snapshots} == {
        "https://openai.com/index/gpt-5-6/",
        "https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/",
    }
    assert {snapshot["source"]["source_definition_ref"] for snapshot in snapshots} == {
        "source_definition:openai-gpt-5-6-terra-pricing"
    }

    for snapshot in snapshots:
        source = snapshot["source"]
        assert set(boundary["required_source_snapshot_fields"]) <= set(source)
        assert source["boundary_id"] == boundary["boundary_id"]
        assert (
            source["source_type_ref"] == boundary["source_semantics"]["source_type_ref"]
        )
        assert source["acquisition_mode"] == "prepared_fixture"
        assert "source_snapshot_ref" not in source
        assert "source_snapshot_digest" not in source
        assert "source_digest" not in source
        assert "acquisition_receipt" not in source
        subject = snapshot["resolved_subject"]
        assert subject == {
            "subject_binding_id": source_mapping["mappings"][0]["subject_binding_id"],
            "entity_type_id": source_mapping["mappings"][0]["entity_type_id"],
            "entity_ref": "product:gpt-5-6-terra-input-tokens",
        }
        values = snapshot["expected_mapped_product_attributes"]
        declarations = entity_attributes[subject["entity_type_id"]]
        assert set(values) == set(declarations)
        assert all(
            _matches_value_type(
                values[attribute_id], declarations[attribute_id]["value_type"]
            )
            for attribute_id in values
        )

    expected = fixture["expected_price_delta"]
    baseline = snapshots[0]["expected_mapped_product_attributes"]["price"]
    current = snapshots[1]["expected_mapped_product_attributes"]["price"]
    absolute_change = current - baseline
    percent_change = absolute_change / baseline * 100
    assert baseline == expected["baseline_value"]
    assert current == expected["current_value"]
    assert absolute_change == expected["absolute_change"]
    assert percent_change == expected["percent_change"]
    assert expected["direction"] == "decrease"
    rule = detection["numeric_delta_rules"][0]
    assert rule == {
        "detector_id": "product_price_move",
        "entity_type_id": "product",
        "attribute_id": "price",
        "baseline": "prior_snapshot",
        "context_attribute_ids": ["currency"],
        "metric": "percent_change",
        "threshold": expected["materiality_threshold_percent"],
        "direction": "any",
        "shift_type": "price_move",
        "signal_type": "competitive_price_move",
    }
    assert expected["is_material"] is (abs(percent_change) >= rule["threshold"])
    assert (
        synthesis["brief_templates"][0]["claim_policy"]
        == "citation_or_explicit_inference"
    )
    route = personas["signal_routing_rules"][0]
    assert route["signal_type"] == rule["signal_type"]
    assert route["brief_template_id"] == synthesis["brief_templates"][0]["template_id"]
    assert route["persona_ids"] == [personas["personas"][0]["persona_id"]]


def test_pack_compiles_through_the_shared_ace_intelligence_compiler() -> None:
    from ace.intelligence import SourceMappingModuleV1

    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    source_mapping = _load_json(SOURCE_MAPPING_PATH)

    assert compiled.contract == "ace.intelligence.compiled-domain-pack/v1alpha1"
    assert compiled.metadata.pack_id == "market_intelligence"
    assert compiled.metadata.version == "0.8.0"
    assert [
        item.model_dump(mode="json") for item in compiled.capability_requirements
    ] == [
        {
            "requirement_id": "public_product_snapshot",
            "capability": "source_snapshot",
            "contract": "ace.source.snapshot/v1alpha1",
        }
    ]
    assert [item.model_dump(mode="json") for item in compiled.authority_requests] == [
        {
            "request_id": "read_public_product_source",
            "authority": "source_read",
        }
    ]
    assert [(module.module_id, module.contract) for module in compiled.modules] == [
        ("market_detection", "ace.intelligence.detection/v1alpha1"),
        ("market_ontology", "ace.intelligence.ontology/v1alpha1"),
        ("market_personas", "ace.intelligence.personas/v1alpha1"),
        ("market_source_mapping", "ace.intelligence.source-mapping/v1alpha1"),
        ("market_synthesis", "ace.intelligence.synthesis/v1alpha1"),
    ]
    expected = fixture["expected_compilation"]
    assert compiled.compiled_pack_id == expected["compiled_pack_id"]
    assert compiled.pack_digest == expected["pack_digest"]
    mapping_ir = next(
        module
        for module in compiled.modules
        if module.module_id == "market_source_mapping"
    )
    assert mapping_ir.module_digest == expected["source_mapping_module_digest"]
    assert SourceMappingModuleV1.model_validate_json(
        mapping_ir.canonical_payload
    ) == SourceMappingModuleV1.model_validate(source_mapping)


def test_pack_passes_fixed_activation_fixture_for_recorded_terra_price_move() -> None:
    from ace.intelligence.conformance import run_domain_pack_conformance

    manifest = _load_json(MANIFEST_PATH)
    fixture = _load_json(ACTIVATION_FIXTURE_PATH)
    (case,) = fixture["observations"]

    assert json.loads(case["baseline_attributes_json"])["price"] == 2.5
    assert json.loads(case["current_attributes_json"])["price"] == 2.0
    assert _parse_time(case["baseline_as_of"]) < _parse_time(case["current_as_of"])

    receipt = run_domain_pack_conformance(
        manifest_document=MANIFEST_PATH.read_bytes(),
        resources={
            item["path"]: (PACK_ROOT / item["path"]).read_bytes()
            for item in manifest["resources"]
        },
        fixture_document=ACTIVATION_FIXTURE_PATH.read_bytes(),
    )

    assert receipt.pack_id == "market_intelligence"
    assert receipt.pack_version == "0.8.0"
    assert receipt.fixture_id == "market_intelligence_activation"
    assert receipt.expected_digest == receipt.actual_digest
    assert receipt.passed is True
    assert receipt.diagnostics == ()


def test_recorded_terra_sources_pin_exact_payloads_and_disclaim_freshness() -> None:
    from ace.core import canonical_json

    inventory = _load_json(RECORDED_SOURCES_PATH)

    assert inventory["source_group_id"] == "competitor_public_evidence"
    assert inventory["source_definition_ref"] == (
        "source_definition:openai-gpt-5-6-terra-pricing"
    )
    assert inventory["subject_binding"] == {
        "subject_binding_id": "listed_product",
        "entity_type_id": "product",
        "entity_ref": "product:gpt-5-6-terra-input-tokens",
    }
    assert [item["source_uri"] for item in inventory["materials"]] == [
        "https://openai.com/index/gpt-5-6/",
        "https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/",
    ]
    assert [item["source_published_at"] for item in inventory["materials"]] == [
        "2026-07-09T00:00:00Z",
        "2026-07-30T00:00:00Z",
    ]
    for material in inventory["materials"]:
        payload = json.loads(material["captured_payload_json"])
        assert canonical_json(payload) == material["captured_payload_json"]
        assert material["captured_payload_digest"] == (
            f"sha256:{hashlib.sha256(material['captured_payload_json'].encode()).hexdigest()}"
        )
    assert any("not proof" in item for item in inventory["limitations"])
    assert any("does not capture or extract" in item for item in inventory["limitations"])


def test_prepared_conformance_inventory_pins_every_market_fixture() -> None:
    pack_manifest = _load_json(MANIFEST_PATH)
    conformance_manifest = _load_json(CONFORMANCE_MANIFEST_PATH)
    negative_cases = _load_json(NEGATIVE_CASES_PATH)

    assert conformance_manifest["pack_id"] == pack_manifest["metadata"]["pack_id"]
    assert conformance_manifest["pack_version"] == pack_manifest["metadata"]["version"]
    assert conformance_manifest["artifact_scope"] == "prepared_only"
    artifacts = {item["path"]: item for item in conformance_manifest["artifacts"]}
    assert set(artifacts) == {
        PUBLIC_SOURCE_BOUNDARY_PATH.name,
        PRICE_MOVE_FIXTURE_PATH.name,
        NEGATIVE_CASES_PATH.name,
        DURABLE_EXPECTED_PATH.name,
        "activation_golden_fixture.json",
        "openai_terra_price_recorded_sources.json",
    }
    assert {
        path.name
        for path in CONFORMANCE_MANIFEST_PATH.parent.glob("*.json")
        if not path.name.startswith("p1c2_live_")
    } == {
        CONFORMANCE_MANIFEST_PATH.name,
        *artifacts,
    }
    for relative_path, artifact in artifacts.items():
        payload = (CONFORMANCE_MANIFEST_PATH.parent / relative_path).read_bytes()
        assert artifact["digest"] == f"sha256:{hashlib.sha256(payload).hexdigest()}"
    assert negative_cases["base_fixture_path"] == PRICE_MOVE_FIXTURE_PATH.name
    assert (
        negative_cases["base_fixture_digest"]
        == artifacts[PRICE_MOVE_FIXTURE_PATH.name]["digest"]
    )
    assert negative_cases["operation_contract"] == "rfc6902-replace-only"
    assert len({case["case_id"] for case in negative_cases["cases"]}) == len(
        negative_cases["cases"]
    )


def test_distribution_configuration_ships_the_inert_market_pack() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_find = project["tool"]["setuptools"]["packages"]["find"]
    package_data = project["tool"]["setuptools"]["package-data"]
    manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    assert "domain_packs.market_intelligence*" in package_find["include"]
    assert "domain_packs.tests*" in package_find["exclude"]
    assert set(package_data["domain_packs.market_intelligence"]) == {
        "*.json",
        "modules/*.json",
        "conformance/*.json",
        "releases/*/*.json",
        "releases/*/modules/*.json",
        "releases/*/conformance/*.json",
    }
    assert "recursive-include domain_packs/market_intelligence *.json" in manifest


def test_price_move_rule_runs_through_shared_intelligence_resources() -> None:
    try:
        from ace.intelligence import (
            BriefV1Alpha1,
            CitationV1Alpha1,
            GroundedClaimV1Alpha1,
            IntelligenceResourceMode,
            LineageReferenceV1Alpha1,
            LineageRelation,
            LineageResourceKind,
            SynthesisModuleV1,
            detect_numeric_shift,
            eligible_signal_routes,
            route_shift_as_signal,
        )
    except ModuleNotFoundError as exc:
        if exc.name in {"ace", "ace.intelligence"}:
            pytest.skip(
                "ACE Core is installed alongside this solution, not declared in its local lockfile"
            )
        raise

    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    synthesis_ir = next(
        module
        for module in compiled.modules
        if module.contract == "ace.intelligence.synthesis/v1alpha1"
    )
    synthesis = SynthesisModuleV1.model_validate_json(synthesis_ir.canonical_payload)
    binding = _prepared_binding(compiled, fixture, boundary)
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
    assert shift.shift_type_ref == "price_move"
    assert (
        shift.delta.parsed_value()["metric_value"]
        == fixture["expected_price_delta"]["percent_change"]
    )
    assert (
        shift.delta.parsed_value()["threshold"]
        == fixture["expected_price_delta"]["materiality_threshold_percent"]
    )
    assert shift.delta.parsed_value()["comparison_context"] == {"currency": "USD"}

    signal = route_shift_as_signal(
        binding=binding,
        detector_id=fixture["pack"]["detector_id"],
        shift=shift,
        detected_at=_parse_time(fixture["scenario"]["signal_detected_at"]),
    )
    assert signal.signal_type_ref == "competitive_price_move"
    assert signal.subject_refs == ("product:gpt-5-6-terra-input-tokens",)
    assert signal.lineage[0].resource_id == shift.resource_id

    routes = eligible_signal_routes(signal=signal, binding=binding)
    assert len(routes) == 1
    assert routes[0].persona_ids == ("competitive_intelligence_analyst",)
    assert routes[0].brief_template_id == synthesis.brief_templates[0].template_id

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
    assert brief.brief_type_ref == "competitive_intelligence"
    assert binding.revision.spec.pack.compiled_pack_id == compiled.compiled_pack_id
    assert binding.revision.spec.capability_bindings[0].secret_ref is None
    assert binding.revision.spec.capability_bindings[0].implementation_id == (
        "prepared_public_product_snapshot_fixture"
    )
    assert binding.revision.spec.authority_bindings[0].grant_ref == (
        "authority_grant:prepared-public-product-source-read"
    )
    expected_binding = fixture["expected_binding"]
    assert (
        binding.revision.spec.overlay.compiled_overlay_id
        == expected_binding["compiled_overlay_id"]
    )
    assert (
        binding.revision.spec.overlay.overlay_digest
        == expected_binding["overlay_digest"]
    )
    assert binding.revision.activation_id == expected_binding["activation_id"]
    assert binding.revision.spec.spec_id == expected_binding["spec_id"]
    assert binding.revision.spec.spec_hash == expected_binding["spec_hash"]
    assert binding.reference.revision_id == expected_binding["revision_id"]
    assert binding.reference.revision_digest == expected_binding["revision_digest"]
    assert [item.lineage[0].resource_id for item in snapshots] == [
        item.resource_id for item in observations
    ]
    assert [item.as_of for item in observations] == [
        _parse_time(item["source"]["source_published_at"])
        for item in fixture["snapshots"]
    ]
    assert all(item.observed_at < item.ingested_at for item in observations)
    assert all(
        snapshot.lineage[0].resource_available_at == observation.ingested_at
        for snapshot, observation in zip(snapshots, observations, strict=True)
    )
    assert [snapshot.attributes.parsed_value() for snapshot in snapshots] == [
        item["expected_mapped_product_attributes"] for item in fixture["snapshots"]
    ]
    assert all(snapshot.entity_type_ref == "product" for snapshot in snapshots)
    assert all(
        snapshot.entity_ref == item["resolved_subject"]["entity_ref"]
        for snapshot, item in zip(snapshots, fixture["snapshots"], strict=True)
    )
    assert all(observation.source_mapping is not None for observation in observations)
    assert all(
        observation.source_mapping.activation_revision == binding.reference
        for observation in observations
    )
    assert {
        (
            observation.source_mapping.module_id,
            observation.source_mapping.mapping_id,
            observation.source_mapping.compiled_pack_id,
            observation.source_mapping.pack_digest,
        )
        for observation in observations
    } == {
        (
            "market_source_mapping",
            "product_price_snapshot",
            compiled.compiled_pack_id,
            compiled.pack_digest,
        )
    }
    assert {
        observation.source_mapping.mapping_digest for observation in observations
    } == {fixture["expected_compilation"]["source_mapping_digest"]}
    assert {
        observation.source_mapping.module_digest for observation in observations
    } == {fixture["expected_compilation"]["source_mapping_module_digest"]}
    assert "competitor" not in snapshots[0].attributes.parsed_value()
    assert {item.resource_kind for item in brief.lineage} == {
        LineageResourceKind.SIGNAL,
        LineageResourceKind.SHIFT,
    }
    assert set(brief.claims[0].citation_ids) == {
        citation.citation_id for citation in citations
    }
    expected_ids = fixture["expected_resource_ids"]
    assert [
        {"source_ref": item.source_ref, "source_digest": item.source_digest}
        for item in observations
    ] == expected_ids["source_snapshots"]
    assert [
        {"resource_id": item.resource_id, "resource_digest": item.resource_digest}
        for item in observations
    ] == expected_ids["observations"]
    assert [
        {"resource_id": item.resource_id, "resource_digest": item.resource_digest}
        for item in snapshots
    ] == expected_ids["entity_snapshots"]
    assert {
        "resource_id": shift.resource_id,
        "resource_digest": shift.resource_digest,
    } == (expected_ids["shift"])
    assert {
        "resource_id": signal.resource_id,
        "resource_digest": signal.resource_digest,
    } == (expected_ids["signal"])
    assert {
        "resource_id": brief.resource_id,
        "resource_digest": brief.resource_digest,
    } == (expected_ids["brief"])


def test_public_source_activation_requires_exact_capability_and_authority_bindings() -> (
    None
):
    try:
        from ace.intelligence import OrganizationOverlayV1
        from ace.intelligence.packs import compile_overlay, prepare_domain_activation
    except ModuleNotFoundError as exc:
        if exc.name in {"ace", "ace.intelligence"}:
            pytest.skip(
                "ACE Core is installed alongside this solution, not declared in its local lockfile"
            )
        raise

    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    capability_binding, authority_binding = _activation_bindings(boundary)
    overlay = compile_overlay(
        compiled,
        OrganizationOverlayV1(
            overlay_id="market_intelligence_binding_pressure",
            version=fixture["fixture_version"],
            pack_id=compiled.metadata.pack_id,
            pack_version=compiled.metadata.version,
            pack_digest=compiled.pack_digest,
        ),
    )
    common = {
        "product_id": fixture["scenario"]["product_id"],
        "activation_key": fixture["scenario"]["activation_key"],
        "pack": compiled,
        "overlay": overlay,
        "compilation_receipt_ref": fixture["scenario"]["compilation_receipt_ref"],
        "conformance_receipt_refs": (fixture["scenario"]["conformance_receipt_ref"],),
    }

    with pytest.raises(ValueError, match="capability binding mismatch"):
        prepare_domain_activation(**common)
    with pytest.raises(ValueError, match="authority binding mismatch"):
        prepare_domain_activation(**common, capability_bindings=(capability_binding,))
    with pytest.raises(ValueError, match="does not satisfy the declared contract"):
        prepare_domain_activation(
            **common,
            capability_bindings=(
                capability_binding.model_copy(
                    update={"contract": "ace.source.snapshot/v2alpha1"}
                ),
            ),
            authority_bindings=(authority_binding,),
        )


@pytest.mark.asyncio
async def test_market_pack_commits_and_reloads_through_core_without_live_authority() -> (
    None
):
    try:
        from ace.application.domain_activation import (
            DomainActivationAdmissionService,
            bind_committed_activation,
        )
        from ace.core import (
            GovernedStateCommitRequestV1,
            GovernedStateHeadV1,
            ResolvedApprovalReceiptV1,
            ResolvedAuthorityGrantV1,
        )
    except ModuleNotFoundError as exc:
        if exc.name in {"ace", "ace.application", "ace.core"}:
            pytest.skip(
                "ACE Core is installed alongside this solution, not declared in its local lockfile"
            )
        raise

    class MemoryGovernedStateStore:
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
            head = GovernedStateHeadV1(
                state_kind=revision.state_kind,
                product_id=revision.product_id,
                state_id=revision.state_id,
                sequence=revision.sequence,
                revision_id=revision.revision_id,
                commit_receipt_id=str(receipt.receipt_id),
                updated_at=request.committed_at,
            )
            self.revisions[(revision.product_id, revision.revision_id)] = revision
            self.receipts[(revision.product_id, str(receipt.receipt_id))] = receipt
            self.heads[key] = head
            return receipt

        async def load_head(self, *, state_kind: str, product_id: str, state_id: str):
            return self.heads.get((state_kind, product_id, state_id))

        async def load_revision(self, revision_id: str, *, product_id: str):
            return self.revisions.get((product_id, revision_id))

        async def load_receipt(self, receipt_id: str, *, product_id: str):
            return self.receipts.get((product_id, receipt_id))

    class ExactMarketAuthority:
        def __init__(self) -> None:
            self.approval_requests: list[dict[str, Any]] = []
            self.grant_requests: list[dict[str, Any]] = []

        async def resolve_approval(self, **request):
            self.approval_requests.append(request)
            return ResolvedApprovalReceiptV1(
                receipt_ref=request["receipt_ref"],
                product_id=request["product_id"],
                subject_ref=request["subject_ref"],
                actor_ref=request["actor_ref"],
                receipt_hash="a" * 64,
                approved_at=request["effective_at"] - timedelta(seconds=1),
            )

        async def resolve_grant(self, **request):
            self.grant_requests.append(request)
            return ResolvedAuthorityGrantV1(
                grant_ref=request["grant_ref"],
                product_id=request["product_id"],
                authority=request["authority"],
                grant_hash="b" * 64,
                effective_at=request["effective_at"],
            )

    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    prepared = _prepared_binding(compiled, fixture, boundary)
    store = MemoryGovernedStateStore()
    authority = ExactMarketAuthority()
    service = DomainActivationAdmissionService(store=store, authority=authority)

    committed = await service.admit(
        prepared.revision,
        expected_head_revision_id=None,
        committed_at=prepared.revision.occurred_at + timedelta(seconds=1),
    )
    reloaded = await DomainActivationAdmissionService(
        store=store,
        authority=ExactMarketAuthority(),
    ).reload(
        product_id=prepared.revision.spec.product_id,
        activation_key=prepared.revision.spec.activation_key,
    )

    assert reloaded is not None
    assert reloaded == committed
    assert committed.authority_stage == "committed"
    assert committed.live_authority is False
    assert authority.approval_requests == [
        {
            "receipt_ref": fixture["scenario"]["approval_receipt_ref"],
            "product_id": prepared.revision.spec.product_id,
            "subject_ref": prepared.revision.spec.spec_id,
            "actor_ref": fixture["scenario"]["actor_ref"],
            "effective_at": prepared.revision.occurred_at,
        }
    ]
    assert authority.grant_requests == [
        {
            "grant_ref": boundary["prepared_binding"]["authority"]["grant_ref"],
            "product_id": prepared.revision.spec.product_id,
            "authority": "source_read",
            "effective_at": prepared.revision.occurred_at,
        }
    ]
    assert committed.commit_receipt.product_id == prepared.revision.spec.product_id
    assert committed.commit_receipt.revision_id == prepared.revision.revision_id
    assert (
        committed.commit_receipt.approval.receipt_ref
        == fixture["scenario"]["approval_receipt_ref"]
    )
    assert [grant.grant_ref for grant in committed.commit_receipt.authority_grants] == [
        boundary["prepared_binding"]["authority"]["grant_ref"]
    ]
    committed_binding = bind_committed_activation(
        pack=compiled,
        committed=reloaded,
    )
    assert committed_binding.prepared_binding.pack == compiled
    assert committed_binding.prepared_binding.reference == prepared.reference
    assert committed_binding.commit_receipt == committed.commit_receipt
    assert committed_binding.authority_stage == "committed"
    assert committed_binding.live_authority is False


NEGATIVE_CASES = _load_json(NEGATIVE_CASES_PATH)["cases"]


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda case: case["case_id"])
def test_market_price_move_negative_conformance_cases_fail_closed(
    case: dict[str, Any],
) -> None:
    try:
        from ace.intelligence import detect_numeric_shift
    except ModuleNotFoundError as exc:
        if exc.name in {"ace", "ace.intelligence"}:
            pytest.skip(
                "ACE Core is installed alongside this solution, not declared in its local lockfile"
            )
        raise

    compiled = _compiled_pack()
    fixture = _load_json(PRICE_MOVE_FIXTURE_PATH)
    boundary = _load_json(PUBLIC_SOURCE_BOUNDARY_PATH)
    binding = _prepared_binding(compiled, fixture, boundary)
    mutated = _apply_negative_case(fixture, case)

    with pytest.raises(ValueError, match=case["expected_error_pattern"]):
        _, snapshots = _prepared_observations_and_snapshots(
            binding=binding,
            fixture=mutated,
        )
        detect_numeric_shift(
            binding=binding,
            detector_id=mutated["pack"]["detector_id"],
            baseline=snapshots[0],
            current=snapshots[1],
            detected_at=_parse_time(mutated["scenario"]["shift_detected_at"]),
        )
