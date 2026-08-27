from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from conclave.domain.enums import ReviewerSlot, ReviewerType, ReviewStage


class ProviderPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=2, ge=1, le=5)
    timeout_seconds: int = Field(default=90, ge=1, le=600)
    max_input_characters: int = Field(default=30_000, ge=1)
    max_output_tokens: int = Field(default=4_000, ge=1)
    max_cost_usd: float = Field(default=0.15, gt=0)
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "medium"
    input_cost_per_million_usd: float = Field(default=2.50, ge=0)
    output_cost_per_million_usd: float = Field(default=15.00, ge=0)
    pricing_version: str = Field(default="openai-2026-07-27", min_length=1)


class SlotSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cadence: timedelta | Literal["event_only"]
    anchor_at: datetime | None = None
    reviewer_type: ReviewerType = ReviewerType.MODEL
    provider: str | None = None
    model: str | None = None
    role_version: str = "role-v1"
    prompt_version: str = "prompt-v1"
    schema_version: str = "assessment-v1"
    cross_review_role_version: str | None = None
    cross_review_prompt_version: str | None = None
    cross_review_schema_version: str | None = None
    judging_role_version: str | None = None
    judging_prompt_version: str | None = None
    judging_schema_version: str | None = None
    provider_policy: ProviderPolicy = Field(default_factory=ProviderPolicy)
    cross_review_provider_policy: ProviderPolicy | None = None
    judging_provider_policy: ProviderPolicy | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "SlotSchedule":
        if self.cadence == "event_only":
            if self.anchor_at is not None:
                raise ValueError("event-only slots cannot have an anchor")
            return self

        if self.cadence <= timedelta(0):
            raise ValueError("cadence must be positive")
        if self.anchor_at is None:
            raise ValueError("scheduled slots require anchor_at")
        if self.anchor_at.tzinfo is None:
            raise ValueError("anchor_at must be timezone-aware")
        return self

    def contract_for_stage(self, stage: ReviewStage) -> tuple[str, str, str]:
        if stage == ReviewStage.CROSS_REVIEW:
            return (
                self.cross_review_role_version or self.role_version,
                self.cross_review_prompt_version or self.prompt_version,
                self.cross_review_schema_version or self.schema_version,
            )
        if stage == ReviewStage.JUDGING:
            return (
                self.judging_role_version or self.role_version,
                self.judging_prompt_version or self.prompt_version,
                self.judging_schema_version or self.schema_version,
            )
        return self.role_version, self.prompt_version, self.schema_version

    def provider_policy_for_stage(self, stage: ReviewStage) -> ProviderPolicy:
        if stage == ReviewStage.CROSS_REVIEW:
            return self.cross_review_provider_policy or self.provider_policy
        if stage == ReviewStage.JUDGING:
            return self.judging_provider_policy or self.provider_policy
        return self.provider_policy


class PanelExpansion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # Retained so stored Phase 1 plan revisions remain readable. Automatic
    # routing uses the two deterministic materiality levers below.
    invoke_b_on_a_material: bool = True
    invoke_b_on_request_material: bool = True
    invoke_b_on_recommendation_material: bool = True
    invoke_b_on_failed_goal: bool = True
    nonmaterial_audit_sample_rate: float = Field(default=0.0, ge=0, le=1)


class ReviewPlanRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1)
    deployment_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    effective_at: datetime
    timezone: str
    evidence_delivery: Literal["fixture_replay", "caller_push"] = "fixture_replay"
    slots: dict[ReviewerSlot, SlotSchedule]
    panel_expansion: PanelExpansion = Field(default_factory=PanelExpansion)
    collision_policy: Literal["shared_session"] = "shared_session"
    cross_review_rounds: Literal[1] = 1
    auto_resolve_enabled: bool = True
    paused: bool = False

    @field_validator("effective_at")
    @classmethod
    def effective_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("effective_at must be timezone-aware")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    @model_validator(mode="after")
    def validate_slots(self) -> "ReviewPlanRevision":
        if set(self.slots) != {ReviewerSlot.A, ReviewerSlot.B, ReviewerSlot.C}:
            raise ValueError("review plans must define exactly slots A, B, and C")
        if self.slots[ReviewerSlot.A].cadence == "event_only":
            raise ValueError("reviewer A requires a cadence")
        if self.slots[ReviewerSlot.B].cadence == "event_only":
            raise ValueError("reviewer B requires a cadence")
        if self.slots[ReviewerSlot.C].cadence != "event_only":
            raise ValueError("reviewer C must be event-only")
        return self


class ReviewPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str
    deployment_id: str
    revisions: tuple[ReviewPlanRevision, ...]

    @model_validator(mode="after")
    def validate_revisions(self) -> "ReviewPlan":
        if not self.revisions:
            raise ValueError("a review plan requires at least one revision")
        numbers = [revision.revision for revision in self.revisions]
        if len(numbers) != len(set(numbers)):
            raise ValueError("revision numbers must be unique")
        if numbers != sorted(numbers):
            raise ValueError("revisions must be ordered")
        for revision in self.revisions:
            if revision.plan_id != self.plan_id:
                raise ValueError("revision plan_id does not match plan")
            if revision.deployment_id != self.deployment_id:
                raise ValueError("revision deployment_id does not match plan")
        return self
