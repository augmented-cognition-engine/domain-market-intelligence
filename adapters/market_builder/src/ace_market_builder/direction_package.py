"""Content-addressed Market direction package for an external creative engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from ace.application import PreparedLifecycleDeliveryV1Alpha1, lifecycle_exact_reference
from ace.core import FrozenContract, canonical_hash
from ace.core.agent_composition import ExactArtifactReferenceV1Alpha1

MARKET_DIRECTION_PACKAGE_VERSION = "ace.market-intelligence.direction-package/v1alpha1"


def _bounded(value: str, *, name: str, maximum: int = 4_000) -> str:
    if not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be non-empty, trimmed, and at most {maximum} characters")
    return value


def _unique(values: tuple[str, ...], *, name: str) -> tuple[str, ...]:
    normalized = tuple(_bounded(value, name=name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{name} must be unique")
    return normalized


class _Contract(FrozenContract):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
        validate_default=True,
        allow_inf_nan=False,
    )


class ApprovedMarketClaimV1Alpha1(_Contract):
    """One approved claim with exact evidence coordinates and visible limits."""

    claim_id: str
    statement: str = Field(max_length=4_000)
    citations: tuple[ExactArtifactReferenceV1Alpha1, ...] = Field(min_length=1, max_length=32)
    approval_ref: str
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    status: Literal["approved"] = "approved"

    @field_validator("claim_id", "approval_ref")
    @classmethod
    def validate_refs(cls, value: str, info) -> str:
        return _bounded(value, name=info.field_name, maximum=240)

    @field_validator("statement")
    @classmethod
    def validate_statement(cls, value: str) -> str:
        return _bounded(value, name="statement")

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _unique(value, name="limitations")

    @model_validator(mode="after")
    def validate_citations(self) -> Self:
        identities = tuple((item.artifact_id, item.artifact_digest, item.artifact_contract) for item in self.citations)
        if len(identities) != len(set(identities)):
            raise ValueError("claim citations must be unique")
        return self


class MarketDirectionPackageV1Alpha1(_Contract):
    """Engine-ready direction only; never a rendered page or execution grant."""

    contract: Literal["ace.market-intelligence.direction-package/v1alpha1"] = MARKET_DIRECTION_PACKAGE_VERSION
    product_id: str
    source_brief: ExactArtifactReferenceV1Alpha1
    decision: ExactArtifactReferenceV1Alpha1
    objective: str = Field(max_length=4_000)
    audience: tuple[str, ...] = Field(min_length=1, max_length=16)
    story_architecture: tuple[str, ...] = Field(min_length=1, max_length=16)
    content_hierarchy: tuple[str, ...] = Field(min_length=1, max_length=32)
    approved_claims: tuple[ApprovedMarketClaimV1Alpha1, ...] = Field(min_length=1, max_length=64)
    constraints: tuple[str, ...] = Field(min_length=1, max_length=32)
    open_questions: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    required_assets: tuple[str, ...] = Field(min_length=1, max_length=32)
    delivery_authority: Literal[False] = False
    external_effect_occurred: Literal[False] = False
    prepared_at: datetime
    package_id: str | None = None
    package_digest: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}$")

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        return _bounded(value, name="product_id", maximum=240)

    @field_validator("objective")
    @classmethod
    def validate_objective(cls, value: str) -> str:
        return _bounded(value, name="objective")

    @field_validator(
        "audience",
        "story_architecture",
        "content_hierarchy",
        "constraints",
        "open_questions",
        "required_assets",
    )
    @classmethod
    def validate_sections(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        return _unique(value, name=info.field_name)

    @field_validator("prepared_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("prepared_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_sources_and_identity(self) -> Self:
        if self.source_brief.artifact_contract != "ace.intelligence.brief/v1alpha1":
            raise ValueError("direction package requires one exact canonical Brief")
        if self.decision.artifact_contract != "ace.core.decision/v1alpha1":
            raise ValueError("direction package requires one exact user Decision")
        claim_ids = tuple(item.claim_id for item in self.approved_claims)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("approved claim identities must be unique")
        material = self.model_dump(mode="json", exclude={"package_id", "package_digest"})
        digest = canonical_hash(material)
        expected_id = f"market_direction_package:{digest[:32]}"
        expected_digest = f"sha256:{digest}"
        if self.package_id is not None and self.package_id != expected_id:
            raise ValueError("package_id does not match exact direction material")
        if self.package_digest is not None and self.package_digest != expected_digest:
            raise ValueError("package_digest does not match exact direction material")
        object.__setattr__(self, "package_id", expected_id)
        object.__setattr__(self, "package_digest", expected_digest)
        return self


def prepare_market_direction_delivery(
    package: MarketDirectionPackageV1Alpha1,
    *,
    source_manifest: ExactArtifactReferenceV1Alpha1,
    target_ref: str,
    prepared_at: datetime,
) -> PreparedLifecycleDeliveryV1Alpha1:
    """Wrap the exact direction artifact for Core AC5 without sending it."""

    exact = MarketDirectionPackageV1Alpha1.model_validate(package.model_dump(mode="python"))
    return PreparedLifecycleDeliveryV1Alpha1(
        product_id=exact.product_id,
        source_manifest=source_manifest,
        artifacts=(lifecycle_exact_reference(exact),),
        target_ref=_bounded(target_ref, name="target_ref", maximum=240),
        prepared_at=prepared_at,
    )


__all__ = [
    "MARKET_DIRECTION_PACKAGE_VERSION",
    "ApprovedMarketClaimV1Alpha1",
    "MarketDirectionPackageV1Alpha1",
    "prepare_market_direction_delivery",
]
