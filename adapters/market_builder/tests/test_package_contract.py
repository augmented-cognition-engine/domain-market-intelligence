from __future__ import annotations

import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

from packaging.requirements import Requirement

ADAPTER_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = ADAPTER_ROOT.parents[1]


def _project(path: Path):
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_market_builder_is_separate_from_the_inert_root_pack() -> None:
    adapter = _project(ADAPTER_ROOT / "pyproject.toml")["project"]
    root = _project(REPOSITORY_ROOT / "pyproject.toml")["project"]

    assert adapter["name"] == "ace-app-market-intelligence-builder"
    assert adapter["version"] == "0.1.0"
    assert adapter["entry-points"] == {
        "ace.intelligence_builders": {
            "market_intelligence_command_center": "ace_market_builder:MarketIntelligenceBuilderExecutor",
        },
        "ace.intelligence_build_planners": {
            "market_intelligence_command_center": "ace_market_builder:MarketIntelligenceBuilderPlanner",
        },
    }
    assert {Requirement(item).name for item in adapter["dependencies"]} == {
        "ace-core",
        "ace-domain-market-intelligence",
    }
    assert root["name"] == "ace-domain-market-intelligence"
    assert "entry-points" not in root
    assert "ace-app-market-intelligence-builder" not in root["dependencies"]
    assert not any((REPOSITORY_ROOT / "domain_packs" / "market_intelligence").rglob("*.py"))


def test_market_builder_wheel_contains_only_the_trusted_adapter(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ("README.md", "pyproject.toml"):
        (source / name).write_bytes((ADAPTER_ROOT / name).read_bytes())
    package = source / "src/ace_market_builder"
    package.mkdir(parents=True)
    for path in (ADAPTER_ROOT / "src/ace_market_builder").glob("*.py"):
        (package / path.name).write_bytes(path.read_bytes())
    output = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(output), str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    (wheel,) = output.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        entry_points_file = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        entry_points_text = archive.read(entry_points_file).decode("utf-8")
    assert {
        "ace_market_builder/__init__.py",
        "ace_market_builder/direction_package.py",
        "ace_market_builder/executor.py",
        "ace_market_builder/planner.py",
    } <= names
    assert not any(name.startswith("domain_packs/") for name in names)
    assert entry_points_text == (
        "[ace.intelligence_build_planners]\n"
        "market_intelligence_command_center = ace_market_builder:MarketIntelligenceBuilderPlanner\n"
        "\n"
        "[ace.intelligence_builders]\n"
        "market_intelligence_command_center = ace_market_builder:MarketIntelligenceBuilderExecutor\n"
    )
