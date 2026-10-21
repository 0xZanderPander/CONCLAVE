"""Reviewer runtime: the engine side of a model call.

Domain output models live in packs. Chimera's models and the generic claim
primitives are re-exported here so existing imports keep working.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from conclave.domain.enums import ReviewerSlot, ReviewerType, ReviewStage
from conclave.packs.chimera.models import (
    Assessment,
    AssessmentV2ProviderOutput,
    CrossReviewResponse,
    CrossReviewV1ProviderOutput,
    ExperimentDefinition,
    RecommendedAction,
    ReviewerCJudgment,
    ReviewerCJudgmentV2ProviderOutput,
)
from conclave.packs.claims import (
    AssessmentClaim,
    PeerClaimReview,
    assign_assessment_claim_ids,
)
from conclave.plans.models import ProviderPolicy

if TYPE_CHECKING:
    from conclave.packs.registry import PackRegistry

__all__ = [
    "Assessment",
    "AssessmentClaim",
    "AssessmentV2ProviderOutput",
    "CrossReviewResponse",
    "CrossReviewV1ProviderOutput",
    "ExperimentDefinition",
    "FakeReviewerRuntime",
    "PeerAssessment",
    "PeerClaimReview",
    "PeerCrossReviewResponse",
    "PermanentReviewerProviderError",
    "ProviderAttempt",
    "ProviderAttemptGuard",
    "ProviderCallResult",
    "ProviderRegistryRuntime",
    "ProviderUsage",
    "RecommendedAction",
    "RetryableReviewerProviderError",
    "ReviewCall",
    "ReviewOutput",
    "ReviewerBudgetExceededError",
    "ReviewerCJudgment",
    "ReviewerCJudgmentV2ProviderOutput",
    "ReviewerExecution",
    "ReviewerProvider",
    "ReviewerProviderError",
    "ReviewerProviderExhaustedError",
    "ReviewerRuntime",
    "UnknownReviewerProviderError",
    "assign_assessment_claim_ids",
]


ReviewOutput = Any
"""Any pack-defined reviewer output (assessment, cross-review response or judgment).

Typed ``Any`` rather than ``BaseModel`` so pydantic carries the pack's concrete
model through ``ProviderCallResult`` and ``ReviewerExecution`` instead of
coercing it to a bare ``BaseModel``."""


class PeerAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: ReviewerSlot
    stage: ReviewStage
    round: int = Field(ge=1)
    assessment: Any


class PeerCrossReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: ReviewerSlot
    stage: Literal[ReviewStage.CROSS_REVIEW] = ReviewStage.CROSS_REVIEW
    round: int = Field(default=2, ge=1)
    response: Any


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
    prior_claims: tuple[str | AssessmentClaim, ...] = ()
    own_assessment: PeerAssessment | None = None
    peer_assessments: tuple[PeerAssessment, ...] = ()
    cross_review_responses: tuple[PeerCrossReviewResponse, ...] = ()
    comparison_history: tuple[dict[str, Any], ...] = ()
    requested_at: datetime
    provider_policy: ProviderPolicy = Field(default_factory=ProviderPolicy)
    attempt_number: int = Field(default=1, ge=1)
    task_pack_ref: str | None = None
    """Pack the session runs under. Set by the orchestrator; resolved from the
    snapshot (then the registry default) for hand-built legacy calls."""


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


class ProviderAttemptGuard(Protocol):
    def before_provider_attempt(self, call: ReviewCall) -> None:
        """Authorize one provider attempt before network access."""

    def after_provider_attempt(
        self,
        call: ReviewCall,
        attempt: ProviderAttempt,
    ) -> None:
        """Account for one provider attempt before its result is returned."""


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
        attempt_guard: ProviderAttemptGuard | None = None,
        packs: "PackRegistry | None" = None,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self._providers = dict(providers)
        self._max_attempts = max_attempts
        self._attempt_guard = attempt_guard
        self._packs = packs

    def close(self) -> None:
        seen: set[int] = set()
        for provider in self._providers.values():
            identity = id(provider)
            if identity in seen:
                continue
            seen.add(identity)
            close = getattr(provider, "close", None)
            if callable(close):
                close()

    def _pack_registry(self) -> "PackRegistry":
        if self._packs is None:
            from conclave.packs.registry import default_pack_registry

            self._packs = default_pack_registry()
        return self._packs

    def review(self, call: ReviewCall) -> ReviewerExecution:
        try:
            provider = self._providers[call.provider]
        except KeyError as exc:
            raise UnknownReviewerProviderError(
                f"reviewer provider {call.provider!r} is not registered"
            ) from exc
        pack = self._pack_registry().for_call(call)
        maximum_attempts = min(self._max_attempts, call.provider_policy.max_attempts)
        attempts: list[ProviderAttempt] = []
        first_attempt = call.attempt_number
        for attempt in range(first_attempt, first_attempt + maximum_attempts):
            attempt_call = call.model_copy(update={"attempt_number": attempt})
            if self._attempt_guard is not None:
                self._attempt_guard.before_provider_attempt(attempt_call)
            started_at = datetime.now(UTC)
            started_clock = monotonic()
            result: ProviderCallResult | None = None
            try:
                response = provider.invoke(attempt_call)
                result = (
                    response
                    if isinstance(response, ProviderCallResult)
                    else ProviderCallResult(output=response)
                )
                output = pack.parse_output(call.stage, call.schema_version, result.output)
                completed_at = datetime.now(UTC)
                latency_ms = max(
                    int((monotonic() - started_clock) * 1000),
                    0,
                )
                if result.usage.cost_usd > call.provider_policy.max_cost_usd:
                    failed_attempt = ProviderAttempt(
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
                    if self._attempt_guard is not None:
                        self._attempt_guard.after_provider_attempt(
                            attempt_call,
                            failed_attempt,
                        )
                    attempts.append(failed_attempt)
                    raise ReviewerProviderExhaustedError(
                        f"reviewer provider {call.provider!r} exceeded its cost ceiling",
                        tuple(attempts),
                    )
                succeeded_attempt = ProviderAttempt(
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
                if self._attempt_guard is not None:
                    self._attempt_guard.after_provider_attempt(
                        attempt_call,
                        succeeded_attempt,
                    )
                attempts.append(succeeded_attempt)
                return ReviewerExecution(output=output, attempts=tuple(attempts))
            except ReviewerProviderExhaustedError:
                raise
            except ReviewerProviderError as exc:
                completed_at = datetime.now(UTC)
                failed_attempt = ProviderAttempt(
                    attempt_number=attempt,
                    status=(
                        "budget_exceeded"
                        if isinstance(exc, ReviewerBudgetExceededError)
                        else ("retryable_failure" if exc.retryable else "permanent_failure")
                    ),
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=max(int((monotonic() - started_clock) * 1000), 0),
                    provider_request_id=exc.provider_request_id,
                    provider_response_id=exc.provider_response_id,
                    usage=ProviderUsage(pricing_version=call.provider_policy.pricing_version),
                    error_type=exc.error_type,
                    error_message=str(exc)[:1000],
                )
                if self._attempt_guard is not None:
                    self._attempt_guard.after_provider_attempt(
                        attempt_call,
                        failed_attempt,
                    )
                attempts.append(failed_attempt)
                attempts_used = attempt - first_attempt + 1
                if not exc.retryable or attempts_used == maximum_attempts:
                    raise ReviewerProviderExhaustedError(
                        f"reviewer provider {call.provider!r} failed "
                        f"after {attempts_used} "
                        f"attempt{'s' if attempts_used != 1 else ''}",
                        tuple(attempts),
                    ) from exc
            except Exception as exc:
                completed_at = datetime.now(UTC)
                failed_attempt = ProviderAttempt(
                    attempt_number=attempt,
                    status="invalid_output",
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=max(int((monotonic() - started_clock) * 1000), 0),
                    provider_request_id=(
                        result.provider_request_id if result is not None else None
                    ),
                    provider_response_id=(
                        result.provider_response_id if result is not None else None
                    ),
                    finish_status=(result.finish_status if result is not None else None),
                    usage=(
                        result.usage
                        if result is not None
                        else ProviderUsage(pricing_version=call.provider_policy.pricing_version)
                    ),
                    error_type="invalid_output",
                    error_message="provider output failed the reviewer contract",
                )
                if self._attempt_guard is not None:
                    self._attempt_guard.after_provider_attempt(
                        attempt_call,
                        failed_attempt,
                    )
                attempts.append(failed_attempt)
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
