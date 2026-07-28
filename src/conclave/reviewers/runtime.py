from collections.abc import Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from conclave.domain.enums import (
    RecommendationCategory,
    ReviewerSlot,
    ReviewerType,
    ReviewStage,
)
from conclave.plans.models import ProviderPolicy


class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    magnitude: float | None = None
    urgency: Literal["low", "normal", "high"] = "normal"
    confidence: float = Field(ge=0, le=1)


class ExperimentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis: str = Field(min_length=1)
    control: str = Field(min_length=1)
    isolated_change: str = Field(min_length=1)
    success_metric: str = Field(min_length=1)
    minimum_evidence: str = Field(min_length=1)
    exposure_limit: str = Field(min_length=1)
    stop_conditions: tuple[str, ...] = Field(min_length=1)
    review_after_hours: float = Field(gt=0)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: RecommendationCategory
    summary: str = Field(min_length=1)
    claims: tuple[str, ...] = ()
    actions: tuple[RecommendedAction, ...] = ()
    experiment: ExperimentDefinition | None = None
    material: bool = False
    risk: Literal["low", "medium", "high"] = "low"
    confidence: float = Field(ge=0, le=1)
    evidence_quality: Literal["strong", "adequate", "weak", "insufficient"]
    expected_goal_impact: Literal["negative", "neutral", "uncertain", "positive"] | None = None
    tracking_health: Literal["healthy", "degraded", "unhealthy"] | None = None
    optimization_eligible: bool | None = None
    primary_conversion: str | None = None
    missing_evidence: tuple[str, ...] = ()
    review_after_hours: float | None = Field(default=None, ge=0)


class ReviewerCJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: Literal[
        "select_a",
        "select_b",
        "synthesize",
        "insufficient_evidence",
        "escalate",
    ]
    summary: str = Field(min_length=1)
    selected_slot: Literal["A", "B"] | None = None
    resolution_assessment: Assessment | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_quality: Literal["strong", "adequate", "weak", "insufficient"]
    unresolved_claims: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_verdict(self) -> "ReviewerCJudgment":
        expected_slot = {
            "select_a": "A",
            "select_b": "B",
        }.get(self.verdict)
        if expected_slot is not None:
            if self.selected_slot != expected_slot:
                raise ValueError(f"{self.verdict} requires selected_slot={expected_slot}")
            if self.resolution_assessment is not None:
                raise ValueError("select verdicts cannot include a resolution assessment")
            return self
        if self.selected_slot is not None:
            raise ValueError(f"{self.verdict} cannot select a reviewer slot")
        if self.resolution_assessment is None:
            raise ValueError(f"{self.verdict} requires a resolution assessment")
        return self


ReviewOutput = Assessment | ReviewerCJudgment


class PeerAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: ReviewerSlot
    stage: ReviewStage
    round: int = Field(ge=1)
    assessment: Assessment


class ReviewCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    snapshot_hash: str
    slot: ReviewerSlot
    stage: ReviewStage
    round: int = Field(ge=1)
    reviewer_type: ReviewerType
    provider: str
    model: str
    role_version: str
    prompt_version: str
    schema_version: str
    snapshot: dict[str, Any]
    prior_claims: tuple[str, ...] = ()
    peer_assessments: tuple[PeerAssessment, ...] = ()
    requested_at: datetime
    provider_policy: ProviderPolicy = Field(default_factory=ProviderPolicy)
    attempt_number: int = Field(default=1, ge=1)


class ReviewerRuntime(Protocol):
    def review(self, call: ReviewCall) -> "ReviewerExecution":
        """Return one structured output and safe provider telemetry."""


class ProviderUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)
    pricing_version: str | None = None


class ProviderCallResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    output: ReviewOutput | Mapping[str, Any]
    provider_request_id: str | None = None
    provider_response_id: str | None = None
    finish_status: str | None = None
    usage: ProviderUsage = Field(default_factory=ProviderUsage)


class ProviderAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_number: int = Field(ge=1)
    status: Literal[
        "succeeded",
        "retryable_failure",
        "permanent_failure",
        "invalid_output",
        "budget_exceeded",
    ]
    started_at: datetime
    completed_at: datetime
    latency_ms: int = Field(ge=0)
    provider_request_id: str | None = None
    provider_response_id: str | None = None
    finish_status: str | None = None
    usage: ProviderUsage = Field(default_factory=ProviderUsage)
    error_type: str | None = None
    error_message: str | None = None


class ReviewerExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    output: ReviewOutput
    attempts: tuple[ProviderAttempt, ...] = ()


class ReviewerProvider(Protocol):
    def invoke(
        self,
        call: ReviewCall,
    ) -> ProviderCallResult | ReviewOutput | Mapping[str, Any]:
        """Return a structured response without changing external state."""


class UnknownReviewerProviderError(LookupError):
    pass


class ReviewerProviderExhaustedError(RuntimeError):
    def __init__(self, message: str, attempts: tuple[ProviderAttempt, ...]) -> None:
        super().__init__(message)
        self.attempts = attempts


class ReviewerProviderError(RuntimeError):
    error_type = "provider_error"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        provider_request_id: str | None = None,
        provider_response_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_request_id = provider_request_id
        self.provider_response_id = provider_response_id


class RetryableReviewerProviderError(ReviewerProviderError):
    error_type = "retryable_provider_error"
    retryable = True


class PermanentReviewerProviderError(ReviewerProviderError):
    error_type = "permanent_provider_error"


class ReviewerBudgetExceededError(PermanentReviewerProviderError):
    error_type = "budget_exceeded"


class ProviderRegistryRuntime:
    """Routes reviewer calls through replaceable, contract-checked providers."""

    def __init__(
        self,
        providers: Mapping[str, ReviewerProvider],
        *,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self._providers = dict(providers)
        self._max_attempts = max_attempts
        self._assessment_adapter = TypeAdapter(Assessment)
        self._judgment_adapter = TypeAdapter(ReviewerCJudgment)

    def review(self, call: ReviewCall) -> ReviewerExecution:
        try:
            provider = self._providers[call.provider]
        except KeyError as exc:
            raise UnknownReviewerProviderError(
                f"reviewer provider {call.provider!r} is not registered"
            ) from exc
        maximum_attempts = min(self._max_attempts, call.provider_policy.max_attempts)
        attempts: list[ProviderAttempt] = []
        for attempt in range(1, maximum_attempts + 1):
            attempt_call = call.model_copy(update={"attempt_number": attempt})
            started_at = datetime.now(UTC)
            started_clock = monotonic()
            try:
                response = provider.invoke(attempt_call)
                result = (
                    response
                    if isinstance(response, ProviderCallResult)
                    else ProviderCallResult(output=response)
                )
                adapter = (
                    self._judgment_adapter
                    if call.stage == ReviewStage.JUDGING
                    else self._assessment_adapter
                )
                output = adapter.validate_python(result.output)
                completed_at = datetime.now(UTC)
                latency_ms = max(
                    int((monotonic() - started_clock) * 1000),
                    0,
                )
                if result.usage.cost_usd > call.provider_policy.max_cost_usd:
                    attempts.append(
                        ProviderAttempt(
                            attempt_number=attempt,
                            status="budget_exceeded",
                            started_at=started_at,
                            completed_at=completed_at,
                            latency_ms=latency_ms,
                            provider_request_id=result.provider_request_id,
                            provider_response_id=result.provider_response_id,
                            finish_status=result.finish_status,
                            usage=result.usage,
                            error_type="budget_exceeded",
                            error_message="provider response exceeded the approved cost ceiling",
                        )
                    )
                    raise ReviewerProviderExhaustedError(
                        f"reviewer provider {call.provider!r} exceeded its cost ceiling",
                        tuple(attempts),
                    )
                attempts.append(
                    ProviderAttempt(
                        attempt_number=attempt,
                        status="succeeded",
                        started_at=started_at,
                        completed_at=completed_at,
                        latency_ms=latency_ms,
                        provider_request_id=result.provider_request_id,
                        provider_response_id=result.provider_response_id,
                        finish_status=result.finish_status,
                        usage=result.usage,
                    )
                )
                return ReviewerExecution(output=output, attempts=tuple(attempts))
            except ReviewerProviderExhaustedError:
                raise
            except ReviewerProviderError as exc:
                completed_at = datetime.now(UTC)
                attempts.append(
                    ProviderAttempt(
                        attempt_number=attempt,
                        status=(
                            "budget_exceeded"
                            if isinstance(exc, ReviewerBudgetExceededError)
                            else (
                                "retryable_failure"
                                if exc.retryable
                                else "permanent_failure"
                            )
                        ),
                        started_at=started_at,
                        completed_at=completed_at,
                        latency_ms=max(int((monotonic() - started_clock) * 1000), 0),
                        provider_request_id=exc.provider_request_id,
                        provider_response_id=exc.provider_response_id,
                        error_type=exc.error_type,
                        error_message=str(exc)[:1000],
                    )
                )
                if not exc.retryable or attempt == maximum_attempts:
                    raise ReviewerProviderExhaustedError(
                        f"reviewer provider {call.provider!r} failed "
                        f"after {attempt} attempt{'s' if attempt != 1 else ''}",
                        tuple(attempts),
                    ) from exc
            except Exception as exc:
                completed_at = datetime.now(UTC)
                attempts.append(
                    ProviderAttempt(
                        attempt_number=attempt,
                        status="invalid_output",
                        started_at=started_at,
                        completed_at=completed_at,
                        latency_ms=max(int((monotonic() - started_clock) * 1000), 0),
                        error_type="invalid_output",
                        error_message="provider output failed the reviewer contract",
                    )
                )
                raise ReviewerProviderExhaustedError(
                    f"reviewer provider {call.provider!r} returned invalid output",
                    tuple(attempts),
                ) from exc
        raise AssertionError("provider retry loop exited unexpectedly")


class FakeReviewerRuntime:
    """Deterministic runtime for orchestration and ledger tests."""

    def __init__(
        self,
        responses: Mapping[tuple[ReviewerSlot, ReviewStage, int], ReviewOutput],
    ) -> None:
        self._responses = dict(responses)
        self.calls: list[ReviewCall] = []

    def review(self, call: ReviewCall) -> ReviewerExecution:
        key = (call.slot, call.stage, call.round)
        try:
            response = self._responses[key]
        except KeyError as exc:
            raise LookupError(f"no fake reviewer response registered for {key}") from exc
        self.calls.append(call)
        return ReviewerExecution(output=response)
