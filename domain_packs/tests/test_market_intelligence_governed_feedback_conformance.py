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
            "the exact ACE Core P1E wheel is required for Market conformance",
            allow_module_level=True,
        )
    raise


pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "domain_packs" / "market_intelligence"
PREVIOUS_ROOT = PACK_ROOT / "releases" / "v0_4_0"
RELEASE_ROOT = PACK_ROOT / "releases" / "v0_5_0"
CONFORMANCE_ROOT = RELEASE_ROOT / "conformance"
COMPATIBILITY_ROOT = PACK_ROOT / "conformance" / "compatibility" / "core_0_8_3"
ACCEPTANCE_PATH = REPO_ROOT / "scripts" / "p1e_governed_feedback_acceptance.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compile(root: Path):
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    return compile_pack_document(
        manifest_bytes,
        {item["path"]: (root / item["path"]).read_bytes() for item in manifest["resources"]},
    )


def _acceptance_module():
    module_name = "market_p1e_acceptance"
    script_root = str(ACCEPTANCE_PATH.parent)
    inserted = script_root not in sys.path
    if inserted:
        sys.path.insert(0, script_root)
    try:
        spec = importlib.util.spec_from_file_location(module_name, ACCEPTANCE_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            sys.path.remove(script_root)


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _keys(child)}
    return set()


def test_0_5_0_is_additive_and_compiles_to_exact_ir() -> None:
    for name in (
        "ontology.json",
        "source_mapping.json",
        "detection.json",
        "synthesis.json",
        "personas.json",
    ):
        assert (RELEASE_ROOT / "modules" / name).read_bytes() == (
            PREVIOUS_ROOT / "modules" / name
        ).read_bytes()

    compiled = _compile(RELEASE_ROOT)
    assert compiled.metadata.pack_id == "market_intelligence"
    assert compiled.metadata.version == "0.5.0"
    assert compiled.compiled_pack_id == "pack_ir:0d967de698cd10fc06b91d2a4559ec9f"
    assert compiled.pack_digest == (
        "sha256:0d967de698cd10fc06b91d2a4559ec9fea80bb421d6a8e79c9766635ccbd8b05"
    )
    feedback = next(
        item for item in compiled.modules if item.module_id == "market_decision_outcomes"
    )
    assert feedback.module_digest == (
        "sha256:02653650c8cface55656a16bdec94788ffab5d8cbf33f661273256bcf55e7918"
    )


def test_feedback_module_is_inert_declarative_policy() -> None:
    module = _load(RELEASE_ROOT / "modules" / "decision_outcomes.json")
    policy = module["feedback_policies"][0]
    assert policy == {
        "policy_id": "competitive_price_move_usefulness",
        "persona_id": "competitive_intelligence_analyst",
        "routing_rule_id": "route_competitive_price_move",
        "decision_type": "competitive_response",
        "eligible_decision_dispositions": ["accept"],
        "eligible_action_dispositions": ["no_action"],
        "outcome_type": "decision_usefulness",
        "measure_id": "analyst_usefulness",
        "initial_value": 0.5,
        "minimum_value": 0.0,
        "maximum_value": 1.0,
        "adjustments": [
            {"outcome_value_json": '"not_useful"', "delta": -0.1},
            {"outcome_value_json": '"useful"', "delta": 0.05},
        ],
    }
    forbidden = {
        "callable",
        "code",
        "command",
        "execute",
        "function",
        "handler",
        "import",
        "python",
        "script",
    }
    assert not (_keys(module) & forbidden)
    assert all(path.suffix == ".json" for path in RELEASE_ROOT.rglob("*") if path.is_file())


def test_p1e_manifest_pins_the_reproducible_prepared_packet() -> None:
    manifest = _load(CONFORMANCE_ROOT / "p1e_governed_feedback_manifest.json")
    assert manifest["negative_case_count"] == 9
    assert manifest["scope"] == {
        "mode": "prepared",
        "delivery": False,
        "external_action": False,
        "live_effect": False,
        "provider_or_connector_in_pack": False,
    }
    assert {item["path"] for item in manifest["artifacts"]} == {
        "p1e_governed_feedback_input.json",
        "p1e_governed_feedback_expected.json",
        "p1e_governed_feedback_negative_cases.json",
    }
    for artifact in manifest["artifacts"]:
        assert _sha256(CONFORMANCE_ROOT / artifact["path"]) == artifact["sha256"]
    assert manifest["acceptance_script"]["sha256"] == (
        "ba816424bb3705464a94cd8f58e0f4fb05efce83b3d8761a0a8d81cfcfcc045b"
    )
    compatibility = _load(COMPATIBILITY_ROOT / "manifest.json")
    assert _sha256(ACCEPTANCE_PATH) == compatibility["acceptance_scripts"]["p1e"]


@pytest.mark.asyncio
async def test_governed_decision_outcome_feedback_matches_exact_expected() -> None:
    acceptance = _acceptance_module()
    result = await acceptance.run_positive()
    projection = await acceptance.positive_projection(result)
    acceptance.assert_positive(result, projection)
    expected = _load(COMPATIBILITY_ROOT / "p1e_governed_feedback_expected.json")
    assert projection == expected["expected"]

    assert projection["decision"]["explicit_no_action"] is True
    assert projection["governed_feedback"]["value"] == 0.55
    assert projection["governed_feedback"]["fresh_service_value"] == 0.55
    assert projection["governed_feedback"]["fresh_service_live_effect"] is False
    assert projection["invariants"]["external_action_executed"] is False
    assert projection["invariants"]["delivery_authority"] is False
    assert projection["invariants"]["provider_calls"] == 0
    assert not any(projection["invariants"]["live_counts"].values())


@pytest.mark.asyncio
async def test_negative_inventory_is_exact_and_leaves_no_residue() -> None:
    acceptance = _acceptance_module()
    observed = await acceptance.run_negative_inventory()
    expected = _load(COMPATIBILITY_ROOT / "p1e_governed_feedback_negative_cases.json")
    assert observed == expected["cases"]
    assert len(observed) == 9
    assert len({item["case_id"] for item in observed}) == 9
    assert all(not any(item["residue_delta"].values()) for item in observed)


def test_harness_uses_only_public_ace_surfaces() -> None:
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
