from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from conclave.domain.enums import ReviewerSlot, ReviewerType


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


class PanelExpansion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invoke_b_on_a_material: bool = True
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
