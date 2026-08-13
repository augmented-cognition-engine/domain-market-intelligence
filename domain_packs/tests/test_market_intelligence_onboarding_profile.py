from __future__ import annotations

import json
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1] / "market_intelligence"


def test_market_intelligence_onboarding_profile_is_domain_owned_and_non_authorizing() -> None:
    profile = json.loads((PACK_ROOT / "onboarding_profile.json").read_text(encoding="utf-8"))

    assert profile["contract"] == "ace.intelligence.onboarding-profile/v1alpha1"
    assert profile["profile_id"] == "onboarding_profile:market-intelligence"
    assert profile["domain_label"] == "Marketing Intelligence"
    assert profile["topic_label"] == "Your market and competitors"
    assert {item["outcome_id"] for item in profile["outcomes"]} == {
        "competitive_intelligence",
        "product_intelligence",
        "market_understanding",
        "customer_understanding",
        "marketing_performance",
        "narrative_and_messaging",
    }
    assert len(profile["source_groups"]) == 5
    private = next(
        group
        for group in profile["source_groups"]
        if group["evidence_role"] == "private_organizational"
    )
    assert private["default_selected"] is False
    assert private["access_label"] == "Private · permission required"
    assert profile["guardrails"]["authorizes_connections"] is False
    assert profile["guardrails"]["authorizes_monitors"] is False
