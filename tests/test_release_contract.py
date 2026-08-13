"""Publishable identity and data-only boundary for Market Intelligence 0.7.0."""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = REPO_ROOT / "domain_packs" / "market_intelligence"
ROOT_PROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
ADAPTER_PROJECT = tomllib.loads(
    (REPO_ROOT / "adapters" / "public_product_source" / "pyproject.toml").read_text(
        encoding="utf-8"
    )
)

ROOT_DISTRIBUTION = "ace-domain-market-intelligence"
ROOT_VERSION = "0.7.0"
ADAPTER_DISTRIBUTION = "ace-market-public-product-source"


def test_root_distribution_identity_and_compatibility_are_exact() -> None:
    project = ROOT_PROJECT["project"]

    assert project["name"] == ROOT_DISTRIBUTION
    assert project["version"] == ROOT_VERSION
    assert project["requires-python"] == ">=3.12,<3.13"
    assert project["dependencies"] == ["ace-core>=0.8.2,<0.9"]

    requirement = Requirement(project["dependencies"][0])
    assert canonicalize_name(requirement.name) == "ace-core"
    assert requirement.specifier == SpecifierSet(">=0.8.2,<0.9")
    assert requirement.marker is None
    assert requirement.url is None


def test_repository_identity_license_and_public_links_are_complete() -> None:
    project = ROOT_PROJECT["project"]
    expected_urls = {
        "Homepage": "https://github.com/augmented-cognition-engine/domain-market-intelligence",
        "Repository": "https://github.com/augmented-cognition-engine/domain-market-intelligence",
        "Issues": "https://github.com/augmented-cognition-engine/domain-market-intelligence/issues",
        "Changelog": "https://github.com/augmented-cognition-engine/domain-market-intelligence/blob/main/CHANGELOG.md",
        "Roadmap": "https://github.com/augmented-cognition-engine/domain-market-intelligence/blob/main/ROADMAP.md",
    }

    assert project["license"] == "Apache-2.0"
    assert project["urls"] == expected_urls
    for name in (
        "LICENSE",
        "NOTICE",
        "README.md",
        "ROADMAP.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
    ):
        assert (REPO_ROOT / name).is_file(), name

    license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "independently versioned ACE domain product",
        "JSON-only Domain Pack",
        "## What you install, and what you get",
        "## Product loop",
        "## Connector boundary",
        "## Guardrails",
        "## Roadmap and project status",
        "## Community and security",
    ):
        assert phrase in readme


def test_root_distribution_mapping_is_inert_and_data_only() -> None:
    setuptools = ROOT_PROJECT["tool"]["setuptools"]

    assert setuptools["include-package-data"] is False
    assert setuptools["packages"]["find"] == {
        "where": ["."],
        "include": ["domain_packs.market_intelligence*"],
        "exclude": ["domain_packs.tests*"],
        "namespaces": True,
    }
    assert setuptools["package-data"]["domain_packs.market_intelligence"] == [
        "*.json",
        "modules/*.json",
        "conformance/*.json",
        "releases/*/*.json",
        "releases/*/modules/*.json",
        "releases/*/conformance/*.json",
    ]

    project = ROOT_PROJECT["project"]
    assert "scripts" not in project
    assert "gui-scripts" not in project
    assert "entry-points" not in project

    files = sorted(path for path in PACK_ROOT.rglob("*") if path.is_file())
    assert len(files) == 40
    assert {path.suffix for path in files} == {".json"}
    assert (PACK_ROOT / "onboarding_profile.json") in files
    assert not (REPO_ROOT / "domain_packs" / "__init__.py").exists()


def test_connector_is_separate_and_never_a_root_dependency() -> None:
    adapter = ADAPTER_PROJECT["project"]

    assert adapter["name"] == ADAPTER_DISTRIBUTION
    assert adapter["version"] == "0.2.0"
    assert adapter["requires-python"] == ">=3.12,<3.13"
    assert adapter["license"] == "Apache-2.0"
    assert adapter["dependencies"] == ["ace-core>=0.8.2,<0.9"]
    assert adapter["urls"] == {
        "Repository": "https://github.com/augmented-cognition-engine/domain-market-intelligence",
        "Issues": "https://github.com/augmented-cognition-engine/domain-market-intelligence/issues",
    }

    published_requirements = [Requirement(item) for item in ROOT_PROJECT["project"]["dependencies"]]
    assert canonicalize_name(ADAPTER_DISTRIBUTION) not in {
        canonicalize_name(item.name) for item in published_requirements
    }
    assert ROOT_PROJECT["tool"]["uv"]["sources"][ADAPTER_DISTRIBUTION] == {
        "path": "adapters/public_product_source",
        "editable": True,
    }


def test_pack_history_is_explicit_and_preserved() -> None:
    import json

    manifests = (
        PACK_ROOT / "manifest.json",
        PACK_ROOT / "releases" / "v0_4_0" / "manifest.json",
        PACK_ROOT / "releases" / "v0_5_0" / "manifest.json",
    )
    versions = [
        json.loads(path.read_text(encoding="utf-8"))["metadata"]["version"] for path in manifests
    ]

    assert versions == ["0.3.0", "0.4.0", "0.5.0"]
    assert (
        PACK_ROOT / "releases" / "v0_6_0" / "conformance" / "p1f_live_bridge_manifest.json"
    ).is_file()


def test_public_two_domain_install_refreshes_new_release_metadata() -> None:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "--refresh-package ace-core" in ci
    assert "--refresh-package ace-domain-world-intelligence" in ci
