from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import ace.application as ace_application

if not hasattr(ace_application, "IntelligenceResourcePlaneService"):
    pytest.skip(
        "the exact ACE Core 0.8 candidate resource plane is required",
        allow_module_level=True,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPO_ROOT / "scripts"
ACCEPTANCE_PATH = SCRIPT_ROOT / "v08_intelligence_os_acceptance.py"


def _acceptance_module():
    sys.path.insert(0, str(SCRIPT_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "market_v08_intelligence_os_acceptance", ACCEPTANCE_PATH
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPT_ROOT))


async def test_market_journey_is_visible_through_the_unchanged_resource_plane() -> None:
    result = await _acceptance_module().run_acceptance(core_candidate_commit="test-candidate")

    assert result["domain"] == "market_intelligence"
    assert result["query"]["page_state"] == "complete"
    assert result["query"]["exact_restart_reopen"] is True
    assert result["loop"]["all_present"] is True
    assert result["loop"]["action_disposition"] == "no_action"
    assert result["loop"]["feedback_live_effect"] is False
    assert result["limitations"] == {
        "prepared_fixture": True,
        "external_action": False,
        "delivery_authority": False,
        "beneficial_impact_claimed": False,
    }
