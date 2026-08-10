"""Hermetic contract tests for the external two-phase GC1 verifier."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "gc1_external_consumer.py"
SCENARIO_PATH = REPO_ROOT / "conformance" / "gc1_market_cognition_scenario.json"

spec = importlib.util.spec_from_file_location("gc1_external_consumer", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeRunner:
    def __init__(
        self,
        payloads: list[dict[str, Any]],
        *,
        failure: str = "cognition_use_attribution_incomplete",
    ):
        self.payloads = deque(payloads)
        self.failure_message = failure
        self.calls: list[tuple[str, ...]] = []

    def json(self, *args: str) -> dict[str, Any]:
        self.calls.append(args)
        if not self.payloads:
            raise AssertionError(f"unexpected command: {args}")
        return self.payloads.popleft()

    def failure(self, *args: str) -> str:
        self.calls.append(args)
        return self.failure_message


def _scenario() -> dict[str, Any]:
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def test_parse_json_output_accepts_public_task_progress_prefix() -> None:
    payload = {"id": "task:fresh", "status": "completed"}
    output = (
        "Accepted as task:fresh; waiting on the durable receipt…\n"
        + json.dumps(payload, indent=2)
        + "\n"
    )

    assert module._parse_json_output(output) == payload


def test_parse_json_output_rejects_non_receipt_output() -> None:
    with pytest.raises(module.JourneyError, match="did not return one JSON object"):
        module._parse_json_output("Accepted as task:fresh; still waiting\n")


def _use(task_id: str, selection_id: str, use_id: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "status": "completed",
        "cognition_selection_receipt": {
            "selection_receipt_id": selection_id,
            "selected_revision_ids": ["cognition_revision:exact"],
        },
        "cognition_use_receipt": {
            "use_receipt_id": use_id,
            "selected_revision_ids": ["cognition_revision:exact"],
            "state": "used",
            "material_use_hash": "a" * 64,
        },
    }


def _selection(selection_id: str) -> dict[str, Any]:
    return {
        "selection_receipt_id": selection_id,
        "selected_revision_ids": ["cognition_revision:exact"],
    }


def _use_receipt(use_id: str) -> dict[str, Any]:
    return {
        "use_receipt_id": use_id,
        "selected_revision_ids": ["cognition_revision:exact"],
        "state": "used",
        "material_use_hash": "a" * 64,
    }


def _prepare_payloads() -> list[dict[str, Any]]:
    proposal = {
        "proposal_id": "cognition_proposal:exact",
        "proposal_hash": "b" * 64,
    }
    revision = {"revision_id": "cognition_revision:exact", "material_hash": "c" * 64}
    head = {
        "head_id": "cognition_head:exact",
        "active_revision_id": "cognition_revision:exact",
        "generation": 1,
        "lifecycle": "active",
    }
    return [
        {
            "proposal": proposal,
            "semantic_diff": {"changes": [{"path": "$.name"}]},
            "selectable": False,
        },
        {"proposal": proposal, "state": "pending", "selectable": False},
        {"proposal_id": proposal["proposal_id"], "changes": [{"path": "$.name"}]},
        {
            "review_receipt": {
                "receipt_id": "cognition_review:exact",
                "disposition": "approve",
                "result_revision_id": "cognition_revision:exact",
                "result_head_id": "cognition_head:exact",
            }
        },
        revision,
        head,
        _use("task:first", "cognition_selection:first", "cognition_use:first"),
        _selection("cognition_selection:first"),
        _use_receipt("cognition_use:first"),
    ]


def test_prepare_records_non_selectable_reviewed_and_materially_used_revision(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "gc1-state.json"
    runner = FakeRunner(_prepare_payloads())

    state = module.prepare(
        runner=runner,
        scenario=_scenario(),
        source_task_id="task:source",
        state_path=state_path,
    )

    assert state["phase"] == "prepared"
    assert state["revision_id"] == "cognition_revision:exact"
    assert state["first_use"]["material_use_hash"] == "a" * 64
    assert json.loads(state_path.read_text(encoding="utf-8")) == state
    assert runner.calls[0][:3] == ("cognition", "teach", "task:source")
    assert not runner.payloads


def test_prepare_refuses_to_replace_an_existing_restart_receipt(tmp_path: Path) -> None:
    state_path = tmp_path / "gc1-state.json"
    state_path.write_text("{}\n", encoding="utf-8")
    runner = FakeRunner(_prepare_payloads())

    with pytest.raises(module.JourneyError, match="refusing to replace"):
        module.prepare(
            runner=runner,
            scenario=_scenario(),
            source_task_id="task:source",
            state_path=state_path,
        )
    assert runner.calls == []


def test_resume_proves_restart_exact_use_retirement_and_fail_closed_selection(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "gc1-state.json"
    prepared = module.prepare(
        runner=FakeRunner(_prepare_payloads()),
        scenario=_scenario(),
        source_task_id="task:source",
        state_path=state_path,
    )
    revision = {"revision_id": "cognition_revision:exact", "material_hash": "c" * 64}
    head = {
        "head_id": "cognition_head:exact",
        "active_revision_id": "cognition_revision:exact",
        "generation": 1,
        "lifecycle": "active",
    }
    retired = {**head, "generation": 2, "lifecycle": "retired"}
    runner = FakeRunner(
        [
            revision,
            head,
            _use("task:restart", "cognition_selection:restart", "cognition_use:restart"),
            _selection("cognition_selection:restart"),
            _use_receipt("cognition_use:restart"),
            {
                "lifecycle_receipt": {
                    "receipt_id": "cognition_lifecycle:retire",
                    "result_lifecycle": "retired",
                    "result_generation": 2,
                }
            },
            retired,
        ]
    )

    completed = module.resume(runner=runner, scenario=_scenario(), state_path=state_path)

    assert completed["phase"] == "complete"
    assert completed["revision_hash"] == prepared["revision_hash"]
    assert completed["restart_use"]["selected_revision_ids"] == ["cognition_revision:exact"]
    assert completed["post_retirement_failure"] == "cognition_use_attribution_incomplete"
    assert runner.calls[-1][:3] == ("cognition", "use", "market_signal_review")
    assert runner.calls[-1][3] == _scenario()["post_retirement_use_prompt"]
    assert runner.calls[-1][3] != _scenario()["restart_use_prompt"]
    assert json.loads(state_path.read_text(encoding="utf-8")) == completed
    assert not runner.payloads


def test_external_consumer_does_not_import_core_or_ace_python_modules() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "from core" not in source
    assert "import core" not in source
    assert "from ace" not in source
    assert "import ace" not in source
    assert "subprocess.run" in source


def test_resume_rejects_network_failure_as_retirement_evidence(tmp_path: Path) -> None:
    state_path = tmp_path / "gc1-state.json"
    module.prepare(
        runner=FakeRunner(_prepare_payloads()),
        scenario=_scenario(),
        source_task_id="task:source",
        state_path=state_path,
    )
    revision = {"revision_id": "cognition_revision:exact", "material_hash": "c" * 64}
    head = {
        "head_id": "cognition_head:exact",
        "active_revision_id": "cognition_revision:exact",
        "generation": 1,
        "lifecycle": "active",
    }
    retired = {**head, "generation": 2, "lifecycle": "retired"}
    runner = FakeRunner(
        [
            revision,
            head,
            _use("task:restart", "cognition_selection:restart", "cognition_use:restart"),
            _selection("cognition_selection:restart"),
            _use_receipt("cognition_use:restart"),
            {
                "lifecycle_receipt": {
                    "receipt_id": "cognition_lifecycle:retire",
                    "result_lifecycle": "retired",
                }
            },
            retired,
        ],
        failure="Submission connection failed",
    )

    with pytest.raises(module.JourneyError, match="did not prove cognition ineligibility"):
        module.resume(runner=runner, scenario=_scenario(), state_path=state_path)
