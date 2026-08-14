from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

try:
    from ace.application import LiveBriefSynthesisService, LiveIntelligenceBridgeService
    from ace.intelligence import (
        IntelligenceResourceMode,
        detect_live_numeric_shift,
        eligible_live_signal_routes,
    )
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "ace" or exc.name.startswith(("ace.", "pydantic"))):
        pytest.skip(
            "the ACE P1F source or exact wheel is required for Market conformance",
            allow_module_level=True,
        )
    raise

# The P1F acceptance script is loaded lazily inside _acceptance_module(), and it transitively
# imports p1c2_live_public_source_acceptance, which requires the separately installed public product
# source adapter. Without this guard the module collects cleanly and then fails at run time, which
# reads as a broken conformance packet rather than an absent optional artifact.
pytest.importorskip(
    "ace_market_public_product_source",
    reason=(
        "ace_market_public_product_source is not installed. It is a separately installed adapter "
        "artifact, not part of the Domain Pack. Install it, or add "
        "adapters/public_product_source/src to PYTHONPATH, to run the LIVE bridge conformance "
        "suite."
    ),
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPO_ROOT / "scripts"
ACCEPTANCE_PATH = SCRIPT_ROOT / "p1f_live_intelligence_bridge_acceptance.py"
EXPECTED_PATH = (
    REPO_ROOT
    / "domain_packs"
    / "market_intelligence"
    / "releases"
    / "v0_6_0"
    / "conformance"
    / "p1f_live_bridge_expected.json"
)
CONFORMANCE_ROOT = EXPECTED_PATH.parent
COMPATIBILITY_ROOT = (
    REPO_ROOT
    / "domain_packs"
    / "market_intelligence"
    / "conformance"
    / "compatibility"
    / "core_0_8_3"
)
COMPATIBILITY_EXPECTED_PATH = COMPATIBILITY_ROOT / "p1f_live_bridge_expected.json"


def _acceptance_module():
    sys.path.insert(0, str(SCRIPT_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "market_p1f_live_bridge_acceptance",
            ACCEPTANCE_PATH,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPT_ROOT))


def test_p1f_manifest_pins_its_inert_conformance_packet() -> None:
    manifest = json.loads(
        (CONFORMANCE_ROOT / "p1f_live_bridge_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["packet"] == "P1F"
    assert manifest["domain_pack_dependency"]["pack_version"] == "0.3.0"
    assert manifest["negative_case_count"] == 4
    assert manifest["scope"] == {
        "mode": "live",
        "delivery": False,
        "external_actions": False,
        "decision_feedback": False,
        "provider_or_connector_in_pack": False,
        "pack_schema_change": False,
    }
    for artifact in manifest["artifacts"]:
        payload = (CONFORMANCE_ROOT / artifact["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]


@pytest.mark.asyncio
async def test_live_source_to_governed_brief_matches_exact_expected() -> None:
    acceptance = _acceptance_module()
    projection, result = await acceptance.run_acceptance()
    expected = json.loads(COMPATIBILITY_EXPECTED_PATH.read_text(encoding="utf-8"))["expected"]

    assert projection == expected
    assert projection["mode"] == IntelligenceResourceMode.LIVE.value
    assert projection["delivery_authority"] is False
    assert projection["external_actions"] == []
    assert projection["provider_calls"] == 1
    assert (
        len(result.source_environment.immutable_store.records) > projection["source_record_count"]
    )


@pytest.mark.asyncio
async def test_live_bridge_negative_matrix_is_exercised_exactly() -> None:
    acceptance = _acceptance_module()
    exercised = await acceptance.run_negative_cases()
    negative_path = COMPATIBILITY_ROOT / "p1f_live_bridge_negative_cases.json"
    declared = json.loads(negative_path.read_text(encoding="utf-8"))["cases"]

    assert exercised == tuple(sorted(item["case_id"] for item in declared))


def test_p1f_public_surface_is_split_between_application_and_pure_intelligence() -> None:
    assert LiveIntelligenceBridgeService.__module__ == ("ace.application.live_intelligence_bridge")
    assert LiveBriefSynthesisService.__module__ == ("ace.application.live_intelligence_bridge")
    assert detect_live_numeric_shift.__module__ == ("ace.intelligence.detection.numeric_delta")
    assert eligible_live_signal_routes.__module__ == "ace.intelligence.routing"
