#!/usr/bin/env python3
"""Two-phase external GC1 journey through only the public ``ace`` CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

CONTRACT_VERSION = "ace.market.gc1-external-consumer/v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO = REPO_ROOT / "conformance" / "gc1_market_cognition_scenario.json"


class JourneyError(RuntimeError):
    """The external consumer could not prove a required public behavior."""


class Runner(Protocol):
    def json(self, *args: str) -> dict[str, Any]: ...

    def failure(self, *args: str) -> str: ...


@dataclass(frozen=True, slots=True)
class AceCliRunner:
    url: str
    executable: str = "ace"

    def _run(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.executable, "--url", self.url, *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def json(self, *args: str) -> dict[str, Any]:
        completed = self._run(args)
        if completed.returncode != 0:
            message = " ".join(completed.stderr.split())[:500]
            raise JourneyError(f"ace command failed ({completed.returncode}): {message}")
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise JourneyError("ace command did not return one JSON object") from exc
        if not isinstance(payload, dict):
            raise JourneyError("ace command did not return one JSON object")
        return payload

    def failure(self, *args: str) -> str:
        completed = self._run(args)
        if completed.returncode == 0:
            raise JourneyError("ace command unexpectedly succeeded after cognition retirement")
        return " ".join((completed.stderr or completed.stdout).split())[:500]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise JourneyError(f"required JSON does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise JourneyError(f"invalid JSON at {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise JourneyError(f"required JSON object is not an object: {path}")
    return value


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require(value: Any, message: str) -> Any:
    if value is None or value == "" or value == [] or value == {}:
        raise JourneyError(message)
    return value


def _use_attribution(task: dict[str, Any], revision_id: str) -> dict[str, Any]:
    if task.get("status") != "completed":
        raise JourneyError(f"fresh cognition use did not complete: {task.get('status')}")
    selection = _require(task.get("cognition_selection_receipt"), "selection receipt is missing")
    use = _require(task.get("cognition_use_receipt"), "use receipt is missing")
    if not isinstance(selection, dict) or not isinstance(use, dict):
        raise JourneyError("cognition receipt is not an object")
    selected = tuple(str(item) for item in selection.get("selected_revision_ids", []))
    used = tuple(str(item) for item in use.get("selected_revision_ids", []))
    if not selected or selected != used or revision_id not in selected:
        raise JourneyError("fresh task did not select and use the exact approved revision")
    if use.get("state") != "used" or not use.get("material_use_hash"):
        raise JourneyError("fresh task lacks material-use attribution")
    return {
        "task_id": _require(task.get("id"), "fresh task identity is missing"),
        "selection_receipt_id": _require(
            selection.get("selection_receipt_id"), "selection receipt identity is missing"
        ),
        "use_receipt_id": _require(use.get("use_receipt_id"), "use receipt identity is missing"),
        "selected_revision_ids": list(selected),
        "material_use_hash": use["material_use_hash"],
    }


def _inspect_use(runner: Runner, attribution: dict[str, Any]) -> dict[str, str]:
    selection = runner.json("cognition", "selection", str(attribution["selection_receipt_id"]))
    use = runner.json("cognition", "use-receipt", str(attribution["use_receipt_id"]))
    if tuple(selection.get("selected_revision_ids", [])) != tuple(
        attribution["selected_revision_ids"]
    ):
        raise JourneyError("retrieved selection receipt changed")
    if tuple(use.get("selected_revision_ids", [])) != tuple(attribution["selected_revision_ids"]):
        raise JourneyError("retrieved use receipt changed")
    if use.get("material_use_hash") != attribution["material_use_hash"]:
        raise JourneyError("retrieved material-use hash changed")
    return {"selection_hash": _hash(selection), "use_hash": _hash(use)}


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise JourneyError(f"refusing to replace existing prepare state: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _replace(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare(
    *,
    runner: Runner,
    scenario: dict[str, Any],
    source_task_id: str,
    state_path: Path,
) -> dict[str, Any]:
    if state_path.exists():
        raise JourneyError(f"refusing to replace existing prepare state: {state_path}")
    stable_key = str(_require(scenario.get("stable_key"), "scenario stable_key is missing"))
    taught = runner.json(
        "cognition",
        "teach",
        source_task_id,
        "--stable-key",
        stable_key,
        "--name",
        str(_require(scenario.get("name"), "scenario name is missing")),
        "--description",
        str(_require(scenario.get("description"), "scenario description is missing")),
        "--intent",
        str(_require(scenario.get("intent"), "scenario intent is missing")),
        "--base-recipe",
        str(_require(scenario.get("base_recipe"), "scenario base_recipe is missing")),
    )
    if taught.get("selectable") is not False:
        raise JourneyError("teaching did not return a non-selectable proposal")
    proposal = _require(taught.get("proposal"), "proposal is missing")
    if not isinstance(proposal, dict):
        raise JourneyError("proposal is not an object")
    proposal_id = str(_require(proposal.get("proposal_id"), "proposal identity is missing"))

    inspection = runner.json("cognition", "inspect", proposal_id)
    semantic_diff = runner.json("cognition", "diff", proposal_id)
    if not semantic_diff.get("changes"):
        raise JourneyError("proposal semantic diff is empty")
    if inspection.get("selectable") is not False:
        raise JourneyError("pending proposal became selectable before review")

    review = runner.json(
        "cognition",
        "review",
        proposal_id,
        "--review-request-id",
        "market-gc1-approve-v1",
        "--disposition",
        "approve",
        "--rationale",
        "Reviewed exact semantic change and source provenance.",
        "--expected-generation",
        "0",
    )
    review_receipt = _require(review.get("review_receipt"), "review receipt is missing")
    if not isinstance(review_receipt, dict) or review_receipt.get("disposition") != "approve":
        raise JourneyError("proposal was not approved through the public review boundary")
    revision_id = str(
        _require(review_receipt.get("result_revision_id"), "revision identity is missing")
    )
    head_id = str(_require(review_receipt.get("result_head_id"), "head identity is missing"))

    revision = runner.json("cognition", "revision", revision_id)
    head = runner.json("cognition", "head", head_id)
    if revision.get("revision_id") != revision_id or head.get("active_revision_id") != revision_id:
        raise JourneyError("approved revision is not the active head")
    if head.get("lifecycle") != "active":
        raise JourneyError("approved head is not active")

    task = runner.json(
        "cognition",
        "use",
        stable_key,
        str(_require(scenario.get("fresh_use_prompt"), "fresh use prompt is missing")),
    )
    first_use = _use_attribution(task, revision_id)
    first_use.update(_inspect_use(runner, first_use))

    state = {
        "contract_version": CONTRACT_VERSION,
        "phase": "prepared",
        "scenario_hash": _hash(scenario),
        "source_task_id": source_task_id,
        "stable_key": stable_key,
        "proposal_id": proposal_id,
        "proposal_hash": _require(proposal.get("proposal_hash"), "proposal hash is missing"),
        "inspection_hash": _hash(inspection),
        "semantic_diff_hash": _hash(semantic_diff),
        "review_receipt_id": _require(
            review_receipt.get("receipt_id"), "review receipt identity is missing"
        ),
        "review_receipt_hash": _hash(review_receipt),
        "revision_id": revision_id,
        "revision_hash": _hash(revision),
        "head_id": head_id,
        "head_generation": int(_require(head.get("generation"), "head generation is missing")),
        "head_hash": _hash(head),
        "first_use": first_use,
    }
    _write_new(state_path, state)
    return state


def resume(
    *,
    runner: Runner,
    scenario: dict[str, Any],
    state_path: Path,
) -> dict[str, Any]:
    state = _load_object(state_path)
    if state.get("contract_version") != CONTRACT_VERSION or state.get("phase") != "prepared":
        raise JourneyError("resume requires one prepared GC1 state receipt")
    if state.get("scenario_hash") != _hash(scenario):
        raise JourneyError("scenario changed between prepare and resume")

    revision_id = str(state["revision_id"])
    head_id = str(state["head_id"])
    stable_key = str(state["stable_key"])
    revision = runner.json("cognition", "revision", revision_id)
    head = runner.json("cognition", "head", head_id)
    if _hash(revision) != state.get("revision_hash") or _hash(head) != state.get("head_hash"):
        raise JourneyError("revision or head changed across restart")
    if head.get("active_revision_id") != revision_id or head.get("lifecycle") != "active":
        raise JourneyError("approved revision did not remain active across restart")

    task = runner.json(
        "cognition",
        "use",
        stable_key,
        str(_require(scenario.get("restart_use_prompt"), "restart use prompt is missing")),
    )
    restart_use = _use_attribution(task, revision_id)
    restart_use.update(_inspect_use(runner, restart_use))

    lifecycle = runner.json(
        "cognition",
        "lifecycle",
        head_id,
        "--review-request-id",
        "market-gc1-retire-v1",
        "--action",
        "retire",
        "--rationale",
        str(_require(scenario.get("retire_rationale"), "retire rationale is missing")),
        "--expected-generation",
        str(state["head_generation"]),
    )
    lifecycle_receipt = _require(lifecycle.get("lifecycle_receipt"), "lifecycle receipt is missing")
    if (
        not isinstance(lifecycle_receipt, dict)
        or lifecycle_receipt.get("result_lifecycle") != "retired"
    ):
        raise JourneyError("head was not retired")
    retired_head = runner.json("cognition", "head", head_id)
    if retired_head.get("lifecycle") != "retired":
        raise JourneyError("retired head inspection did not report retirement")

    failure = runner.failure(
        "cognition",
        "use",
        stable_key,
        str(_require(scenario.get("restart_use_prompt"), "restart use prompt is missing")),
    )
    allowed_failure_codes = (
        "cognition_use_not_completed",
        "cognition_use_attribution_missing",
        "cognition_use_attribution_incomplete",
    )
    if not any(code in failure for code in allowed_failure_codes):
        raise JourneyError("post-retirement failure did not prove cognition ineligibility")
    completed = {
        **state,
        "phase": "complete",
        "restart_use": restart_use,
        "lifecycle_receipt_id": _require(
            lifecycle_receipt.get("receipt_id"), "lifecycle receipt identity is missing"
        ),
        "lifecycle_receipt_hash": _hash(lifecycle_receipt),
        "retired_head_hash": _hash(retired_head),
        "post_retirement_failure": failure,
    }
    _replace(state_path, completed)
    return completed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "resume"))
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument(
        "--source-task", help="Completed product-scoped task used by the prepare phase"
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    scenario = _load_object(args.scenario)
    runner = AceCliRunner(url=args.url)
    if args.phase == "prepare":
        if not args.source_task:
            raise SystemExit("--source-task is required for prepare")
        result = prepare(
            runner=runner,
            scenario=scenario,
            source_task_id=args.source_task,
            state_path=args.state_file,
        )
    else:
        result = resume(runner=runner, scenario=scenario, state_path=args.state_file)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
