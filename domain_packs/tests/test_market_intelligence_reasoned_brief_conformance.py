from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

try:
    from ace.intelligence.packs import compile_pack_document
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "ace" or exc.name.startswith(("ace.", "pydantic"))):
        pytest.skip(
            "the exact ACE Core P1D1 wheel is required for Market conformance",
            allow_module_level=True,
        )
    raise


pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "domain_packs" / "market_intelligence"
HISTORICAL_ROOT = PACK_ROOT / "releases" / "v0_3_0"
RELEASE_ROOT = PACK_ROOT / "releases" / "v0_4_0"
CONFORMANCE_ROOT = RELEASE_ROOT / "conformance"
COMPATIBILITY_ROOT = PACK_ROOT / "conformance" / "compatibility" / "core_0_8_3"
ACCEPTANCE_PATH = REPO_ROOT / "scripts" / "p1d1_prepared_brief_acceptance.py"
CORE_WHEEL_SHA256 = "a7c5be2f8025937fb6e3b7b06ac2f7c67a806110034e610adcd4a88e1b1d1cab"
LEGACY_CORE_WHEEL_SHA256 = "267cfed8ec3057439abf2a55e4f595e34c92f3b10f4e37c21a2e253a80b9dc4d"

FROZEN_0_3_0_SHA256 = {
    "manifest.json": "82719602adf0ddd47ab1d7e80e9806c94c9c329705acc61c283796d79bcbd46d",
    "modules/detection.json": "a2a3a25b39d8bce53d6b5d22439d319912d445c7a51921e0c2c83417bc39cb47",
    "modules/ontology.json": "c99ad5b44b5ddb2077fc292e44adc51eea90425ae4de37ada81bf8c363a721f6",
    "modules/personas.json": "ed1c0da8c45867504c5894085d10944389f954890d62cfb33d10ca7caff8a83d",
    "modules/source_mapping.json": "acebb1a048ca284c9d7d902e4c1a3af9ea02567f13836685382a02047e7ee293",
    "modules/synthesis.json": "35741d5581beb701821df3236e7353e380e0043673ead7e6a87f2a3e118716bb",
    "conformance/manifest.json": "bf65b0d44622c33411bc2911bd765095e20c38db3aa3564652391aedf0889ced",
    "conformance/p1_price_move_golden.json": "5d04afed27b785f35cbd29083d566bb84770a2fbdf4a44837ea196e432dd1cdf",
    "conformance/p1_price_move_negative_cases.json": "39003bb393dc94bf2737b7568993577a0e9b55a4efc7981922270350a2e8095c",
    "conformance/p1c_durable_price_move_expected.json": "735fe7aa0dc1678daa3dec3d052317452314b075c45ef24b88d8d409d131b6b7",
    "conformance/public_product_price_boundary.json": "dfc0a63eaaebca857c46da62080ae14f5d46793d808fe0296d66c951c55bdff5",
    "conformance/p1c2_live_source_input.json": "555b7a2e41c5864038a357edcafebeb73187339dbb1fdeff5c8c03da93a659e2",
    "conformance/p1c2_live_expected.json": "3d44cf54294b3fb53b1d14503730894050d38e124fdf5422412d9010254ca254",
    "conformance/p1c2_live_source_negative_cases.json": "bbd89f833094605821a164b56da0cf1a97663d9ea26e4b09a9c73d91bd5e820f",
    "conformance/p1c2_live_manifest.json": "b3ab83ab4d32df2c1211802a126d39e3165fc2545e0c4e7e7112adf95ce94722",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _acceptance_module():
    module_name = "market_p1d1_acceptance"
    spec = importlib.util.spec_from_file_location(module_name, ACCEPTANCE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _compile(root: Path):
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    return compile_pack_document(
        manifest_bytes,
        {item["path"]: (root / item["path"]).read_bytes() for item in manifest["resources"]},
    )


def test_historical_0_3_0_archive_is_byte_frozen() -> None:
    historical_inventory = {
        path.relative_to(HISTORICAL_ROOT).as_posix()
        for path in HISTORICAL_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.relative_to(HISTORICAL_ROOT).parts
    }
    assert historical_inventory == set(FROZEN_0_3_0_SHA256)
    assert {
        relative: _sha256(HISTORICAL_ROOT / relative) for relative in FROZEN_0_3_0_SHA256
    } == FROZEN_0_3_0_SHA256
    compiled = _compile(HISTORICAL_ROOT)
    assert compiled.compiled_pack_id == "pack_ir:19de6d59b28095f7bd7600364c3b4de7"
    assert compiled.pack_digest == (
        "sha256:19de6d59b28095f7bd7600364c3b4de787cce0365764cf54ab9f282f3412c2dd"
    )
    synthesis = next(item for item in compiled.modules if item.module_id == "market_synthesis")
    assert synthesis.module_digest == (
        "sha256:99ccea5e5fe93cd2ad22c20e9a36d30ce61506f8f998bc30da1a0432947495c0"
    )


def test_0_4_0_is_an_additive_ordered_synthesis_release() -> None:
    for name in (
        "ontology.json",
        "source_mapping.json",
        "detection.json",
        "personas.json",
    ):
        assert (RELEASE_ROOT / "modules" / name).read_bytes() == (
            HISTORICAL_ROOT / "modules" / name
        ).read_bytes()

    old_synthesis = _load(HISTORICAL_ROOT / "modules" / "synthesis.json")
    expected_synthesis = dict(old_synthesis)
    expected_synthesis["contract"] = "ace.intelligence.synthesis/v1alpha2"
    assert _load(RELEASE_ROOT / "modules" / "synthesis.json") == expected_synthesis

    template = expected_synthesis["brief_templates"][0]
    assert template["template_id"] == "competitive_price_move_brief"
    assert template["required_sections"] == [
        "what_changed",
        "why_it_matters",
        "recommendation",
        "limitations",
    ]
    assert template["recommendation_required"] is True

    compiled = _compile(RELEASE_ROOT)
    assert compiled.metadata.pack_id == "market_intelligence"
    assert compiled.metadata.version == "0.4.0"
    assert compiled.compiled_pack_id == "pack_ir:c87b61600105da2a72d6d7a9fa7cb7dd"
    assert compiled.pack_digest == (
        "sha256:c87b61600105da2a72d6d7a9fa7cb7dde2fd6edbc0e63327c541b80a96dcd66c"
    )
    synthesis = next(item for item in compiled.modules if item.module_id == "market_synthesis")
    assert synthesis.module_digest == (
        "sha256:fa6346a4173b7bbae1cd62a06a51b1a184f8408160deebfd95b71b0dfe3f0512"
    )


def test_p1d1_manifest_pins_its_separate_inert_packet() -> None:
    manifest = _load(CONFORMANCE_ROOT / "p1d1_prepared_brief_manifest.json")
    assert manifest["platform_dependency"]["sha256"] == LEGACY_CORE_WHEEL_SHA256
    assert manifest["negative_case_count"] == 18
    assert manifest["scope"] == {
        "mode": "prepared",
        "delivery": False,
        "live_promotion": False,
        "provider_or_connector_in_pack": False,
        "semantic_entailment_validation_claimed": False,
    }
    assert {item["path"] for item in manifest["artifacts"]} == {
        "p1d1_prepared_brief_input.json",
        "p1d1_prepared_brief_expected.json",
        "p1d1_prepared_brief_negative_cases.json",
    }
    for artifact in manifest["artifacts"]:
        assert _sha256(CONFORMANCE_ROOT / artifact["path"]) == artifact["sha256"]

    release_files = sorted(RELEASE_ROOT.rglob("*"))
    assert all(path.suffix == ".json" for path in release_files if path.is_file())
    for path in release_files:
        if path.is_file():
            json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_governed_routed_reasoned_brief_matches_exact_expected() -> None:
    acceptance = _acceptance_module()
    result = await acceptance.run_positive()
    projection = await acceptance.positive_projection(result)
    acceptance.assert_positive(result, projection)
    expected = _load(COMPATIBILITY_ROOT / "p1d1_prepared_brief_expected.json")
    assert projection == expected["expected"]

    brief = projection["brief"]
    rendered = json.dumps(brief, sort_keys=True)
    assert "Northstar" not in rendered
    assert all(citation["locator"] is None for citation in brief["citations"])
    assert brief["title"] == "Competitive Price Move Brief"
    assert brief["body_markdown"].count("## Recommendation") == 1
    assert {claim["statement"] for claim in brief["claims"]} >= {
        "The listed Edge X1 price changed from USD 1,200 to USD 1,080.",
        "Ownership, motive, and market effect are not established.",
    }

    receipt = projection["synthesis_receipt"]
    assert receipt["template_id"] == "competitive_price_move_brief"
    assert receipt["persona_ids"] == ["competitive_intelligence_analyst"]
    assert (
        receipt["required_section_ids"]
        == receipt["actual_section_ids"]
        == [
            "what_changed",
            "why_it_matters",
            "recommendation",
            "limitations",
        ]
    )
    assert len(receipt["selected_context"]) == 6
    assert len(receipt["claim_supports"]) == 4
    assert receipt["reasoning_request_id"].startswith("governed_reasoning_request:")
    assert receipt["reasoning_result_id"].startswith("structured_final_result:")
    assert receipt["reasoning_terminal"]["receipt_id"].startswith("reasoning_terminal:")
    assert len(projection["atomic_append_transaction"]["records"]) == 2

    lifecycle = projection["activation_lifecycle"]
    revisions = [
        lifecycle[name]["revision"] for name in ("revision_1", "revision_2", "revision_3_rollback")
    ]
    assert [item["revision"] for item in revisions] == [1, 2, 3]
    assert len({item["activation_id"] for item in revisions}) == 1
    assert revisions[1]["prior_revision_id"] == revisions[0]["revision_id"]
    assert revisions[2]["prior_revision_id"] == revisions[1]["revision_id"]
    assert revisions[2]["rollback_of_revision_id"] == revisions[0]["revision_id"]
    assert (
        lifecycle["revision_3_rollback"]["revision"]["spec"]
        == (lifecycle["revision_1"]["revision"]["spec"])
    )

    assert projection["replay"] == {
        "same_service_equal": True,
        "rollback_fresh_service_equal": True,
        "provider_calls": 1,
        "forbidden_replay_provider_calls": 0,
    }
    assert projection["historical_manual_p1b"]["brief"] == {
        "as_of": "2026-02-15T12:02:30Z",
        "available_at": "2026-02-15T12:03:00Z",
        "contract": "ace.intelligence.intelligence-record-reference/v1alpha1",
        "mode": "prepared",
        "product_id": "product:market-intelligence-conformance",
        "resource_contract": "ace.intelligence.brief/v1alpha1",
        "resource_id": "brief:407d8ba23fe08b3adcd6deb6216ccf19",
        "resource_digest": (
            "sha256:407d8ba23fe08b3adcd6deb6216ccf19b54350a95882ca9f888a78d0e9685b00"
        ),
        "resource_kind": "brief",
    }
    assert not any(projection["persistence"]["live_counts"].values())
    assert projection["persistence"]["delivery_authority"] is False


@pytest.mark.asyncio
async def test_negative_inventory_is_exact_and_leaves_no_downstream_residue() -> None:
    acceptance = _acceptance_module()
    observed = await acceptance.run_negative_inventory()
    expected = _load(COMPATIBILITY_ROOT / "p1d1_prepared_brief_negative_cases.json")
    assert observed == expected["cases"]
    assert len(observed) == 18
    assert len({item["case_id"] for item in observed}) == 18
    assert all(item["brief_residue_delta"] == 0 for item in observed)
    assert all(item["synthesis_receipt_residue_delta"] == 0 for item in observed)
    assert all(item["prepared_synthesis_transaction_residue_delta"] == 0 for item in observed)


def test_harness_uses_only_public_ace_surfaces_and_golden_is_path_portable() -> None:
    tree = ast.parse(ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        name == "core.engine"
        or name.startswith("core.engine.")
        or name == "ace.core.engine"
        or name.startswith("ace.core.engine.")
        for name in imported
    )
    assert imported >= {"ace.application", "ace.core", "ace.intelligence"}
    expected = _load(COMPATIBILITY_ROOT / "p1d1_prepared_brief_expected.json")
    assert "ace_origin" not in expected["expected"]["platform_dependency"]
    assert expected["expected"]["platform_dependency"] == {
        "ace_core_wheel_sha256": CORE_WHEEL_SHA256
    }


def test_semantic_claim_is_narrow_and_honest() -> None:
    manifest = _load(COMPATIBILITY_ROOT / "manifest.json")
    assert manifest["scope"]["semantic_entailment_validation_claimed"] is False
    expected = _load(COMPATIBILITY_ROOT / "p1d1_prepared_brief_expected.json")["expected"]
    assert "Ownership, motive, and market effect are not established." in {
        item["statement"] for item in expected["brief"]["claims"]
    }
    # Platform enforcement validates structure and declared support attribution.
    # This fixture's bounded prose policy is an explicit positive constraint, not
    # a claim of generalized semantic-entailment or hallucination detection.
