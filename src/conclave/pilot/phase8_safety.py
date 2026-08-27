import fcntl
import json
import os
import stat
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from conclave.domain.enums import ReviewerSlot, ReviewerType, ReviewStage
from conclave.pilot.phase8 import (
    Phase8AccessManifest,
    Phase8BatchApproval,
    Phase8CasePackage,
    Phase8CohortManifest,
    Phase8Gate0Report,
    Phase8HashedArtifact,
    Phase8Model,
    Phase8RevocationRecord,
    Phase8StageAccess,
    Sha256,
    validate_phase8_approval_scope,
    validate_phase8_cohort_packages,
)
from conclave.reviewers.runtime import (
    ProviderAttempt,
    ProviderAttemptGuard,
    ReviewCall,
    ReviewerExecution,
    ReviewerRuntime,
)

if TYPE_CHECKING:
    from conclave.config import Settings


class Phase8AuthorizationError(RuntimeError):
    """The offline artifacts do not authorize provider construction."""


class Phase8SafetyViolation(RuntimeError):
    """A live call attempted to cross the frozen Phase 8 boundary."""


class Phase8BatchRevokedError(Phase8SafetyViolation):
    """The active batch has already been revoked."""


class Phase8StateError(RuntimeError):
    """The durable Phase 8 accounting state is inconsistent or unsafe."""


@dataclass(frozen=True, slots=True)
class Phase8AuthorizationBundle:
    cohort: Phase8CohortManifest
    packages: Mapping[str, Phase8CasePackage]
    access_manifest: Phase8AccessManifest
    gate_0_report: Phase8Gate0Report
    approval: Phase8BatchApproval

    @property
    def approved_case_ids(self) -> frozenset[str]:
        return frozenset((*self.approval.eligible_case_ids, *self.approval.control_case_ids))


@dataclass(frozen=True, slots=True)
class PreparedPhase8SafetyBoundary:
    authorization: Phase8AuthorizationBundle
    state_store: "Phase8StateStore"
    revocation_store: "Phase8RevocationStore"


class Phase8AttemptReservation(Phase8Model):
    reservation_id: str
    case_id: str
    session_id: str
    stage_id: str
    attempt_number: int = Field(ge=1)
    reserved_attempts: Literal[1]
    reserved_tokens: int = Field(ge=1)
    reserved_cost_usd: float = Field(gt=0)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class Phase8CaseUsage(Phase8Model):
    case_id: str
    session_id: str | None = None
    started_at: datetime
    last_attempt_completed_at: datetime | None = None
    stage_ids: tuple[str, ...] = ()
    attempt_count: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    total_latency_ms: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0, ge=0)
    completed: bool = False
    valid_result: bool | None = None

    @field_validator("started_at", "last_attempt_completed_at")
    @classmethod
    def timestamps_are_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("case usage timestamps must be timezone-aware")
        return value


class Phase8RuntimeState(Phase8HashedArtifact):
    hash_field = "state_hash"

    contract_version: Literal["phase8-runtime-state/v1"]
    cohort_id: str
    cohort_hash: Sha256
    active_gate: Literal["gate_1_canary", "gate_2_completion"]
    active_batch_id: str
    active_approval_hash: Sha256
    phase_attempt_count: int = Field(ge=0)
    phase_token_count: int = Field(ge=0)
    phase_cost_usd: float = Field(ge=0)
    batch_attempt_count: int = Field(ge=0)
    batch_token_count: int = Field(ge=0)
    batch_cost_usd: float = Field(ge=0)
    invalid_output_count: int = Field(ge=0)
    consecutive_failed_cases: int = Field(ge=0)
    phase_completed_case_ids: tuple[str, ...]
    cases: dict[str, Phase8CaseUsage]
    reservations: dict[str, Phase8AttemptReservation]
    batch_completed: bool
    gate_review_hash: Sha256 | None = None
    updated_at: datetime
    state_hash: Sha256

    @field_validator("updated_at")
    @classmethod
    def updated_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def completed_cases_are_unique(self) -> Self:
        if len(self.phase_completed_case_ids) != len(set(self.phase_completed_case_ids)):
            raise ValueError("completed Phase 8 cases cannot be repeated")
        if self.batch_completed and self.reservations:
            raise ValueError("a completed batch cannot retain provider reservations")
        return self


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase8AuthorizationError(f"cannot read valid {label}: {path}") from exc
    if not isinstance(document, dict):
        raise Phase8AuthorizationError(f"{label} must be a JSON object: {path}")
    return document


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(
                document,
                destination,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_name, path)
    except Exception:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


def load_phase8_provider_secret(path: str, provider: str) -> str:
    """Read a pilot secret only after authorization has passed."""

    secret_path = Path(path)
    try:
        metadata = secret_path.lstat()
    except OSError as exc:
        raise Phase8AuthorizationError(f"cannot read the external {provider} pilot secret") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise Phase8AuthorizationError(
            f"the external {provider} pilot secret must be a regular non-symlink file"
        )
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise Phase8AuthorizationError(
            f"the external {provider} pilot secret must not grant group or world access"
        )
    try:
        secret = secret_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise Phase8AuthorizationError(f"cannot read the external {provider} pilot secret") from exc
    if not secret or "\n" in secret or "\r" in secret:
        raise Phase8AuthorizationError(
            f"the external {provider} pilot secret is empty or malformed"
        )
    return secret


class Phase8RevocationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock_path = path.with_name(f".{path.name}.lock")

    def existing(self) -> Phase8RevocationRecord | None:
        if not self.path.exists():
            return None
        try:
            return Phase8RevocationRecord.model_validate(
                _read_json(self.path, "Phase 8 revocation record")
            )
        except Exception as exc:
            if isinstance(exc, Phase8AuthorizationError):
                raise
            raise Phase8AuthorizationError(
                "the Phase 8 revocation record is invalid; access remains blocked"
            ) from exc

    def ensure_not_revoked(self, approval: Phase8BatchApproval) -> None:
        record = self.existing()
        if record is None:
            return
        if record.batch_id != approval.batch_id:
            raise Phase8AuthorizationError(
                "a revocation record exists for a different batch; access remains blocked"
            )
        raise Phase8BatchRevokedError(
            f"Phase 8 batch {record.batch_id!r} is revoked: {record.reason}"
        )

    def revoke(
        self,
        approval: Phase8BatchApproval,
        *,
        reason: str,
        details: str,
        now: datetime,
    ) -> Phase8RevocationRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+", encoding="utf-8") as lock:
            os.chmod(self._lock_path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            existing = self.existing()
            if existing is not None:
                return existing
            record = Phase8RevocationRecord.seal(
                contract_version="phase8-revocation/v1",
                batch_id=approval.batch_id,
                approval_hash=approval.approval_hash,
                revoked_at=now,
                revoked_by="phase8-safety-boundary",
                reason=reason,
                details=details[:1_000],
                automatic_restart_allowed=False,
            )
            _atomic_write_json(self.path, record.model_dump(mode="json"))
            return record


class Phase8StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock_path = path.with_name(f".{path.name}.lock")

    def _load(self) -> Phase8RuntimeState | None:
        if not self.path.exists():
            return None
        try:
            return Phase8RuntimeState.model_validate(_read_json(self.path, "Phase 8 runtime state"))
        except Exception as exc:
            if isinstance(exc, Phase8AuthorizationError):
                raise Phase8StateError(str(exc)) from exc
            raise Phase8StateError(
                "Phase 8 runtime state is invalid; provider access remains blocked"
            ) from exc

    def _transaction(
        self,
        operation: Callable[
            [Phase8RuntimeState | None],
            tuple[Phase8RuntimeState, Any],
        ],
    ) -> Any:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+", encoding="utf-8") as lock:
            os.chmod(self._lock_path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            updated, result = operation(self._load())
            _atomic_write_json(self.path, updated.model_dump(mode="json"))
            return result

    def activate(
        self,
        authorization: Phase8AuthorizationBundle,
        *,
        now: datetime,
    ) -> Phase8RuntimeState:
        approval = authorization.approval
        cohort = authorization.cohort

        def operation(
            current: Phase8RuntimeState | None,
        ) -> tuple[Phase8RuntimeState, Phase8RuntimeState]:
            if current is None:
                if approval.gate != "gate_1_canary":
                    raise Phase8StateError(
                        "Gate 2 cannot start without the durable completed Gate 1 state"
                    )
                state = Phase8RuntimeState.seal(
                    contract_version="phase8-runtime-state/v1",
                    cohort_id=cohort.cohort_id,
                    cohort_hash=cohort.cohort_hash,
                    active_gate=approval.gate,
                    active_batch_id=approval.batch_id,
                    active_approval_hash=approval.approval_hash,
                    phase_attempt_count=0,
                    phase_token_count=0,
                    phase_cost_usd=0,
                    batch_attempt_count=0,
                    batch_token_count=0,
                    batch_cost_usd=0,
                    invalid_output_count=0,
                    consecutive_failed_cases=0,
                    phase_completed_case_ids=(),
                    cases={},
                    reservations={},
                    batch_completed=False,
                    updated_at=now,
                )
                return state, state
            if current.cohort_id != cohort.cohort_id or current.cohort_hash != (cohort.cohort_hash):
                raise Phase8StateError("runtime state belongs to a different cohort")
            if current.active_approval_hash == approval.approval_hash:
                if (
                    current.active_batch_id != approval.batch_id
                    or current.active_gate != approval.gate
                ):
                    raise Phase8StateError("approval hash is bound to different batch state")
                return current, current
            if approval.gate != "gate_2_completion":
                raise Phase8StateError(
                    "a new Gate 1 approval cannot replace existing pilot authority"
                )
            if (
                current.active_gate != "gate_1_canary"
                or not current.batch_completed
                or current.gate_review_hash != approval.prior_gate_review_hash
            ):
                raise Phase8StateError(
                    "Gate 2 requires the completed Gate 1 state and exact review hash"
                )
            if current.reservations:
                raise Phase8StateError("Gate 2 cannot inherit pending provider attempts")
            if set(approval.eligible_case_ids) & set(current.phase_completed_case_ids):
                raise Phase8StateError("Gate 2 cannot repeat a Gate 1 case")
            state = Phase8RuntimeState.seal(
                contract_version=current.contract_version,
                cohort_id=current.cohort_id,
                cohort_hash=current.cohort_hash,
                active_gate=approval.gate,
                active_batch_id=approval.batch_id,
                active_approval_hash=approval.approval_hash,
                phase_attempt_count=current.phase_attempt_count,
                phase_token_count=current.phase_token_count,
                phase_cost_usd=current.phase_cost_usd,
                batch_attempt_count=0,
                batch_token_count=0,
                batch_cost_usd=0,
                invalid_output_count=current.invalid_output_count,
                consecutive_failed_cases=current.consecutive_failed_cases,
                phase_completed_case_ids=current.phase_completed_case_ids,
                cases={},
                reservations={},
                batch_completed=False,
                updated_at=now,
            )
            return state, state

        return self._transaction(operation)

    def reserve_attempt(
        self,
        authorization: Phase8AuthorizationBundle,
        *,
        case: Phase8CasePackage,
        call: ReviewCall,
        stage: Phase8StageAccess,
        reservation_id: str,
        now: datetime,
    ) -> None:
        approval = authorization.approval
        route = case.routing_profile.expected_route
        if route is None:
            raise Phase8StateError("a no-call control cannot reserve a provider attempt")
        route_cost_limit, route_time_limit = _ROUTE_LIMITS[route]
        reserved_tokens = stage.policy.max_input_characters + stage.policy.max_output_tokens
        reserved_cost = stage.policy.max_cost_usd

        def operation(
            current: Phase8RuntimeState | None,
        ) -> tuple[Phase8RuntimeState, None]:
            state = _require_active_state(current, approval)
            if state.batch_completed:
                raise Phase8StateError("the approved batch is already complete")
            if state.reservations:
                raise Phase8StateError(
                    "a provider attempt is pending reconciliation; parallel calls are blocked"
                )
            usage = state.cases.get(case.case_id)
            if usage is None:
                usage = Phase8CaseUsage(
                    case_id=case.case_id,
                    session_id=call.session_id,
                    started_at=now,
                )
            if usage.completed:
                raise Phase8StateError("a completed case cannot invoke another provider")
            if usage.session_id != call.session_id:
                raise Phase8StateError("one Phase 8 case cannot map to multiple sessions")
            elapsed = (now - usage.started_at).total_seconds()
            if elapsed > route_time_limit:
                raise Phase8StateError("the route wall-time ceiling has been exceeded")

            expected_sequence = _ROUTE_STAGE_SEQUENCES[route]
            stage_ids = usage.stage_ids
            if stage.stage_id not in stage_ids:
                if len(stage_ids) >= len(expected_sequence) or (
                    expected_sequence[len(stage_ids)] != stage.stage_id
                ):
                    raise Phase8StateError(
                        "the provider stage is not legal for the frozen expected route"
                    )
                stage_ids = (*stage_ids, stage.stage_id)

            if usage.total_cost_usd + reserved_cost > route_cost_limit + 1e-12:
                raise Phase8StateError("the route cost ceiling cannot cover this attempt")
            if (
                state.batch_attempt_count + 1 > approval.budget.batch_attempt_cap
                or state.phase_attempt_count + 1 > approval.budget.phase_attempt_cap
            ):
                raise Phase8StateError("the attempt ceiling cannot cover this attempt")
            if (
                state.batch_token_count + reserved_tokens > approval.budget.batch_token_cap
                or state.phase_token_count + reserved_tokens > approval.budget.phase_token_cap
            ):
                raise Phase8StateError("the token ceiling cannot cover this attempt")
            if (
                state.batch_cost_usd + reserved_cost > approval.budget.batch_spend_cap_usd + 1e-12
                or state.phase_cost_usd + reserved_cost
                > approval.budget.phase_spend_cap_usd + 1e-12
            ):
                raise Phase8StateError("the spend ceiling cannot cover this attempt")

            reservation = Phase8AttemptReservation(
                reservation_id=reservation_id,
                case_id=case.case_id,
                session_id=call.session_id,
                stage_id=stage.stage_id,
                attempt_number=call.attempt_number,
                reserved_attempts=1,
                reserved_tokens=reserved_tokens,
                reserved_cost_usd=reserved_cost,
                created_at=now,
            )
            cases = dict(state.cases)
            cases[case.case_id] = usage.model_copy(update={"stage_ids": stage_ids})
            updated = Phase8RuntimeState.seal(
                **_state_update(
                    state,
                    cases=cases,
                    reservations={reservation_id: reservation},
                    updated_at=now,
                )
            )
            return updated, None

        self._transaction(operation)

    def settle_attempt(
        self,
        authorization: Phase8AuthorizationBundle,
        *,
        case: Phase8CasePackage,
        reservation_id: str,
        attempt: ProviderAttempt,
        now: datetime,
    ) -> None:
        approval = authorization.approval
        route = case.routing_profile.expected_route
        if route is None:
            raise Phase8StateError("a no-call control cannot settle a provider attempt")
        route_cost_limit, route_time_limit = _ROUTE_LIMITS[route]

        def operation(
            current: Phase8RuntimeState | None,
        ) -> tuple[Phase8RuntimeState, None]:
            state = _require_active_state(current, approval)
            try:
                reservation = state.reservations[reservation_id]
                usage = state.cases[case.case_id]
            except KeyError as exc:
                raise Phase8StateError(
                    "provider attempt has no matching durable reservation"
                ) from exc
            actual_tokens = attempt.usage.total_tokens
            actual_cost = attempt.usage.cost_usd
            if actual_tokens > reservation.reserved_tokens:
                raise Phase8StateError("provider attempt exceeded its token reservation")
            if actual_cost > reservation.reserved_cost_usd + 1e-12:
                raise Phase8StateError("provider attempt exceeded its cost reservation")
            elapsed = (now - usage.started_at).total_seconds()
            next_case_cost = usage.total_cost_usd + actual_cost
            if elapsed > route_time_limit:
                raise Phase8StateError("the route wall-time ceiling has been exceeded")
            if next_case_cost > route_cost_limit + 1e-12:
                raise Phase8StateError("the route cost ceiling has been exceeded")

            updated_usage = usage.model_copy(
                update={
                    "last_attempt_completed_at": now,
                    "attempt_count": usage.attempt_count + 1,
                    "total_tokens": usage.total_tokens + actual_tokens,
                    "total_latency_ms": usage.total_latency_ms + attempt.latency_ms,
                    "total_cost_usd": round(next_case_cost, 12),
                }
            )
            reservations = dict(state.reservations)
            del reservations[reservation_id]
            cases = dict(state.cases)
            cases[case.case_id] = updated_usage
            invalid_outputs = state.invalid_output_count + (
                1 if attempt.status == "invalid_output" else 0
            )
            if invalid_outputs > 1:
                raise Phase8StateError(
                    "more than one provider contract failure occurred in the cohort"
                )
            updated = Phase8RuntimeState.seal(
                **_state_update(
                    state,
                    phase_attempt_count=state.phase_attempt_count + 1,
                    phase_token_count=state.phase_token_count + actual_tokens,
                    phase_cost_usd=round(state.phase_cost_usd + actual_cost, 12),
                    batch_attempt_count=state.batch_attempt_count + 1,
                    batch_token_count=state.batch_token_count + actual_tokens,
                    batch_cost_usd=round(state.batch_cost_usd + actual_cost, 12),
                    invalid_output_count=invalid_outputs,
                    cases=cases,
                    reservations=reservations,
                    updated_at=now,
                )
            )
            return updated, None

        self._transaction(operation)

    def complete_case(
        self,
        authorization: Phase8AuthorizationBundle,
        *,
        case_id: str,
        valid_result: bool,
        now: datetime,
    ) -> None:
        approval = authorization.approval
        case = authorization.packages[case_id]

        def operation(
            current: Phase8RuntimeState | None,
        ) -> tuple[Phase8RuntimeState, None]:
            state = _require_active_state(current, approval)
            if state.reservations:
                raise Phase8StateError("a case cannot complete with a pending attempt")
            usage = state.cases.get(case_id)
            if usage is None:
                if case.case_kind != "no_call_control":
                    raise Phase8StateError("eligible case has no provider-attempt record")
                usage = Phase8CaseUsage(case_id=case_id, started_at=now)
            if usage.completed:
                if usage.valid_result != valid_result:
                    raise Phase8StateError("completed case result cannot be changed")
                return state, None
            expected_stages = (
                ()
                if case.case_kind == "no_call_control"
                else _ROUTE_STAGE_SEQUENCES[case.routing_profile.expected_route]
            )
            if valid_result and usage.stage_ids != expected_stages:
                raise Phase8StateError(
                    "valid case completion does not match the frozen route stages"
                )
            if case.case_kind == "no_call_control":
                if not valid_result:
                    raise Phase8StateError("a no-call control did not stop safely")
                consecutive = state.consecutive_failed_cases
            else:
                consecutive = 0 if valid_result else state.consecutive_failed_cases + 1
            if consecutive >= 2:
                raise Phase8StateError(
                    "two consecutive provider-eligible sessions lacked a valid result"
                )
            completed_ids = (
                state.phase_completed_case_ids
                if case_id in state.phase_completed_case_ids
                else (*state.phase_completed_case_ids, case_id)
            )
            cases = dict(state.cases)
            cases[case_id] = usage.model_copy(
                update={"completed": True, "valid_result": valid_result}
            )
            updated = Phase8RuntimeState.seal(
                **_state_update(
                    state,
                    consecutive_failed_cases=consecutive,
                    phase_completed_case_ids=completed_ids,
                    cases=cases,
                    updated_at=now,
                )
            )
            return updated, None

        self._transaction(operation)

    def complete_batch(
        self,
        authorization: Phase8AuthorizationBundle,
        *,
        gate_review_hash: str,
        now: datetime,
    ) -> None:
        approval = authorization.approval
        approved_ids = authorization.approved_case_ids

        def operation(
            current: Phase8RuntimeState | None,
        ) -> tuple[Phase8RuntimeState, None]:
            state = _require_active_state(current, approval)
            if state.reservations:
                raise Phase8StateError("batch cannot complete with a pending attempt")
            completed = {case_id for case_id, usage in state.cases.items() if usage.completed}
            if completed != approved_ids:
                raise Phase8StateError(
                    "batch cannot complete until every approved case is terminal"
                )
            if approval.gate == "gate_1_canary" and any(
                not state.cases[case_id].valid_result for case_id in approval.eligible_case_ids
            ):
                raise Phase8StateError("Gate 1 requires five valid audited results")
            updated = Phase8RuntimeState.seal(
                **_state_update(
                    state,
                    batch_completed=True,
                    gate_review_hash=gate_review_hash,
                    updated_at=now,
                )
            )
            return updated, None

        self._transaction(operation)

    def read(self) -> Phase8RuntimeState:
        state = self._load()
        if state is None:
            raise Phase8StateError("Phase 8 runtime state does not exist")
        return state


def _state_update(state: Phase8RuntimeState, **updates: Any) -> dict[str, Any]:
    document = state.model_dump(mode="python", exclude={"state_hash"})
    document.update(updates)
    return document


def _require_active_state(
    state: Phase8RuntimeState | None,
    approval: Phase8BatchApproval,
) -> Phase8RuntimeState:
    if state is None:
        raise Phase8StateError("Phase 8 runtime state is missing")
    if (
        state.active_batch_id != approval.batch_id
        or state.active_approval_hash != approval.approval_hash
        or state.active_gate != approval.gate
    ):
        raise Phase8StateError("runtime state does not match the active approval")
    return state


_ROUTE_LIMITS: dict[str, tuple[float, int]] = {
    "a_only": (0.12, 3 * 60),
    "ab_agreement": (0.25, 5 * 60),
    "cross_review_resolved": (0.55, 8 * 60),
    "c_tie_broken": (0.95, 12 * 60),
}

_ROUTE_STAGE_SEQUENCES: dict[str, tuple[str, ...]] = {
    "a_only": ("reviewer_a_independent",),
    "ab_agreement": (
        "reviewer_a_independent",
        "reviewer_b_independent",
    ),
    "cross_review_resolved": (
        "reviewer_a_independent",
        "reviewer_b_independent",
        "reviewer_a_cross_review",
        "reviewer_b_cross_review",
    ),
    "c_tie_broken": (
        "reviewer_a_independent",
        "reviewer_b_independent",
        "reviewer_a_cross_review",
        "reviewer_b_cross_review",
        "reviewer_c_blind_assessment",
        "reviewer_c_judgment",
    ),
}


def validate_phase8_guard_configuration(
    access_manifest: Phase8AccessManifest,
) -> tuple[str, ...]:
    """Verify that every frozen route fits the runtime's hard guard envelope."""

    stages = {stage.stage_id: stage for stage in access_manifest.stages}
    if set(stages) != {
        stage_id for sequence in _ROUTE_STAGE_SEQUENCES.values() for stage_id in sequence
    }:
        raise Phase8StateError("access manifest does not cover the runtime route guards")
    details: list[str] = []
    for route, sequence in _ROUTE_STAGE_SEQUENCES.items():
        cost_limit, wall_time_limit = _ROUTE_LIMITS[route]
        first_attempt_cost = sum(stages[stage_id].policy.max_cost_usd for stage_id in sequence)
        if first_attempt_cost > cost_limit + 1e-12:
            raise Phase8StateError(f"{route} cannot complete inside its route cost guard")
        first_attempt_time = sum(stages[stage_id].policy.timeout_seconds for stage_id in sequence)
        if first_attempt_time > wall_time_limit:
            raise Phase8StateError(f"{route} contains a stage outside its wall-time guard")
        details.append(
            f"{route}: first-attempt ceiling ${first_attempt_cost:.2f} <= "
            f"${cost_limit:.2f}; stage timeouts {first_attempt_time}s <= "
            f"wall-time guard {wall_time_limit}s"
        )
    if any(stage.policy.max_attempts > 2 for stage in stages.values()):
        raise Phase8StateError("a stage exceeds the two-attempt Phase 8 ceiling")
    details.append(
        "All stages reserve attempts, tokens, and cost before execution; batch and phase "
        "caps are fixed by the approval contract."
    )
    return tuple(details)


def _stage_id(call: ReviewCall) -> str:
    mapping = {
        (ReviewerSlot.A, ReviewStage.INDEPENDENT): "reviewer_a_independent",
        (ReviewerSlot.B, ReviewStage.INDEPENDENT): "reviewer_b_independent",
        (ReviewerSlot.A, ReviewStage.CROSS_REVIEW): "reviewer_a_cross_review",
        (ReviewerSlot.B, ReviewStage.CROSS_REVIEW): "reviewer_b_cross_review",
        (ReviewerSlot.C, ReviewStage.INDEPENDENT): "reviewer_c_blind_assessment",
        (ReviewerSlot.C, ReviewStage.JUDGING): "reviewer_c_judgment",
    }
    try:
        return mapping[(call.slot, call.stage)]
    except KeyError as exc:
        raise Phase8SafetyViolation("reviewer slot/stage is outside the pilot topology") from exc


def _state_violation_reason(message: str) -> str:
    if "contract failure" in message:
        return "cohort_contract_failure"
    if "stage is not legal" in message:
        return "unapproved_contract_or_provider"
    if (
        "pending reconciliation" in message
        or "matching durable reservation" in message
        or "runtime state" in message
    ):
        return "audit_integrity_failure"
    return "budget_or_time_breach"


def _load_phase8_bundle(
    settings: "Settings",
    *,
    now: datetime,
) -> Phase8AuthorizationBundle:
    required_paths = {
        "cohort manifest": settings.phase8_cohort_manifest_path,
        "case package directory": settings.phase8_case_packages_dir,
        "access manifest": settings.phase8_access_manifest_path,
        "Gate 0 report": settings.phase8_gate0_report_path,
        "batch approval": settings.phase8_approval_path,
    }
    missing = [name for name, path in required_paths.items() if not path]
    if missing:
        raise Phase8AuthorizationError(f"Phase 8 requires configured {', '.join(missing)}")
    cohort = Phase8CohortManifest.model_validate(
        _read_json(
            Path(settings.phase8_cohort_manifest_path or ""),
            "Phase 8 cohort manifest",
        )
    )
    case_dir = Path(settings.phase8_case_packages_dir or "")
    try:
        case_paths = sorted(case_dir.glob("*.json"))
    except OSError as exc:
        raise Phase8AuthorizationError("cannot enumerate Phase 8 case packages") from exc
    if len(case_paths) != 24:
        raise Phase8AuthorizationError(
            "the Phase 8 case directory must contain exactly 24 JSON packages"
        )
    packages = tuple(
        Phase8CasePackage.model_validate(_read_json(path, f"Phase 8 case package {path.name}"))
        for path in case_paths
    )
    validate_phase8_cohort_packages(cohort, packages)
    access = Phase8AccessManifest.model_validate(
        _read_json(
            Path(settings.phase8_access_manifest_path or ""),
            "Phase 8 access manifest",
        )
    )
    gate_0 = Phase8Gate0Report.model_validate(
        _read_json(
            Path(settings.phase8_gate0_report_path or ""),
            "Phase 8 Gate 0 report",
        )
    )
    approval = Phase8BatchApproval.model_validate(
        _read_json(
            Path(settings.phase8_approval_path or ""),
            "Phase 8 batch approval",
        )
    )
    by_id = {package.case_id: package for package in packages}
    bundle = Phase8AuthorizationBundle(
        cohort=cohort,
        packages=by_id,
        access_manifest=access,
        gate_0_report=gate_0,
        approval=approval,
    )
    validate_phase8_approval_scope(approval, cohort, access)
    if (
        gate_0.cohort_id != cohort.cohort_id
        or gate_0.cohort_hash != cohort.cohort_hash
        or gate_0.access_manifest_id != access.manifest_id
        or gate_0.access_manifest_hash != access.manifest_hash
        or approval.gate_0_report_hash != gate_0.report_hash
    ):
        raise Phase8AuthorizationError(
            "Gate 0 evidence does not match the approved cohort and access manifest"
        )
    if not (
        cohort.frozen_at <= gate_0.generated_at <= approval.issued_at <= now < approval.expires_at
    ):
        raise Phase8AuthorizationError("Phase 8 artifact chronology or approval expiry is invalid")
    if access.created_at > gate_0.generated_at:
        raise Phase8AuthorizationError("Gate 0 predates the frozen access manifest")
    for package in packages:
        if package.redaction_attestation.reviewed_at > cohort.frozen_at:
            raise Phase8AuthorizationError(
                "a redaction attestation was completed after the cohort freeze"
            )
        if package.baseline and package.baseline.captured_at > cohort.frozen_at:
            raise Phase8AuthorizationError("a baseline was captured after cohort freeze")
        if package.case_kind == "provider_eligible" and package.version_pins != access.version_pins:
            raise Phase8AuthorizationError(
                "a provider-eligible case does not match the access-manifest versions"
            )

    endpoints_by_provider = {
        provider: {stage.base_url for stage in access.stages if stage.provider == provider}
        for provider in ("openai", "anthropic")
    }
    configured_endpoints = {
        "openai": settings.openai_base_url.rstrip("/"),
        "anthropic": settings.anthropic_base_url.rstrip("/"),
    }
    if any(
        endpoints_by_provider[provider] != {configured_endpoints[provider]}
        for provider in endpoints_by_provider
    ):
        raise Phase8AuthorizationError(
            "configured provider endpoint does not exactly match the access manifest"
        )
    return bundle


def prepare_phase8_safety_boundary(
    settings: "Settings",
    *,
    now: datetime | None = None,
) -> PreparedPhase8SafetyBoundary:
    """Validate all authority and durable state before provider construction."""

    now = now or datetime.now(UTC)
    try:
        bundle = _load_phase8_bundle(settings, now=now)
    except (Phase8AuthorizationError, Phase8BatchRevokedError):
        raise
    except Exception as exc:
        raise Phase8AuthorizationError(
            "Phase 8 authorization artifacts failed strict validation"
        ) from exc
    if not settings.phase8_runtime_state_path or not settings.phase8_revocation_path:
        raise Phase8AuthorizationError(
            "Phase 8 requires durable runtime-state and revocation paths"
        )
    revocation_store = Phase8RevocationStore(Path(settings.phase8_revocation_path))
    revocation_store.ensure_not_revoked(bundle.approval)
    state_store = Phase8StateStore(Path(settings.phase8_runtime_state_path))
    try:
        state_store.activate(bundle, now=now)
    except Phase8StateError as exc:
        raise Phase8AuthorizationError(str(exc)) from exc
    return PreparedPhase8SafetyBoundary(
        authorization=bundle,
        state_store=state_store,
        revocation_store=revocation_store,
    )


class Phase8SafetyRuntime(ReviewerRuntime, ProviderAttemptGuard):
    """Fail-closed, case-scoped authorization and accounting boundary."""

    def __init__(
        self,
        prepared: PreparedPhase8SafetyBoundary,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.authorization = prepared.authorization
        self.state_store = prepared.state_store
        self.revocation_store = prepared.revocation_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._inner: ReviewerRuntime | None = None
        self._case_context: ContextVar[str | None] = ContextVar(
            f"phase8_case_{self.authorization.approval.batch_id}",
            default=None,
        )

    def bind_inner(self, runtime: ReviewerRuntime) -> None:
        if self._inner is not None:
            raise RuntimeError("the Phase 8 provider runtime is already bound")
        self._inner = runtime

    @contextmanager
    def case_scope(self, case_id: str) -> Iterator[None]:
        if self._case_context.get() is not None:
            self._violate(
                "unapproved_contract_or_provider",
                "nested Phase 8 case scopes are prohibited",
            )
        if case_id not in self.authorization.approved_case_ids:
            self._violate(
                "unapproved_contract_or_provider",
                "case is outside the exact approved batch allowlist",
            )
        token = self._case_context.set(case_id)
        try:
            yield
        finally:
            self._case_context.reset(token)

    def review(self, call: ReviewCall) -> ReviewerExecution:
        self._ensure_live_authority()
        case = self._current_case()
        if case.case_kind != "provider_eligible":
            self._violate(
                "unapproved_contract_or_provider",
                "a no-call control attempted to reach a provider",
            )
        self._validate_call(case, call)
        if self._inner is None:
            self._violate(
                "unapproved_contract_or_provider",
                "Phase 8 provider runtime was not bound",
            )
        return self._inner.review(call)

    def before_provider_attempt(self, call: ReviewCall) -> None:
        self._ensure_live_authority()
        case = self._current_case()
        self._validate_call(case, call)
        stage = self._stage_for_call(call)
        reservation_id = self._reservation_id(case.case_id, call)
        try:
            self.state_store.reserve_attempt(
                self.authorization,
                case=case,
                call=call,
                stage=stage,
                reservation_id=reservation_id,
                now=self._clock(),
            )
        except Phase8StateError as exc:
            self._violate(_state_violation_reason(str(exc)), str(exc))

    def after_provider_attempt(
        self,
        call: ReviewCall,
        attempt: ProviderAttempt,
    ) -> None:
        case = self._current_case()
        stage = self._stage_for_call(call)
        if attempt.attempt_number != call.attempt_number:
            self._violate(
                "unapproved_contract_or_provider",
                "provider telemetry attempt number does not match the invocation",
            )
        if attempt.completed_at < attempt.started_at:
            self._violate(
                "audit_integrity_failure",
                "provider attempt completion predates its start",
            )
        if attempt.latency_ms > stage.policy.timeout_seconds * 1_000:
            self._violate(
                "budget_or_time_breach",
                "provider attempt exceeded the pinned timeout",
            )
        if attempt.usage.pricing_version != stage.pricing_version:
            self._violate(
                "unapproved_contract_or_provider",
                "provider attempt pricing version does not match the manifest",
            )
        if attempt.status == "succeeded" and attempt.usage.total_tokens <= 0:
            self._violate(
                "audit_integrity_failure",
                "successful provider attempt lacks token telemetry",
            )
        reservation_id = self._reservation_id(case.case_id, call)
        try:
            self.state_store.settle_attempt(
                self.authorization,
                case=case,
                reservation_id=reservation_id,
                attempt=attempt,
                now=self._clock(),
            )
        except Phase8StateError as exc:
            self._violate(_state_violation_reason(str(exc)), str(exc))
        self._ensure_not_revoked()

    def complete_case(self, case_id: str, *, valid_audited_result: bool) -> None:
        self._ensure_not_revoked()
        if case_id not in self.authorization.approved_case_ids:
            self._violate(
                "unapproved_contract_or_provider",
                "cannot complete a case outside the approved batch",
            )
        try:
            self.state_store.complete_case(
                self.authorization,
                case_id=case_id,
                valid_result=valid_audited_result,
                now=self._clock(),
            )
        except Phase8StateError as exc:
            reason = (
                "consecutive_session_failures"
                if "consecutive" in str(exc)
                else "audit_integrity_failure"
            )
            self._violate(reason, str(exc))

    def complete_no_call_control(
        self,
        case_id: str,
        *,
        observed_disposition: str,
    ) -> None:
        self._ensure_not_revoked()
        try:
            case = self.authorization.packages[case_id]
        except KeyError:
            self._violate(
                "unapproved_contract_or_provider",
                "unknown no-call control",
            )
        if (
            case_id not in self.authorization.approval.control_case_ids
            or case.case_kind != "no_call_control"
            or case.expected_disposition != observed_disposition
        ):
            self._violate(
                "unapproved_contract_or_provider",
                "no-call control did not stop at its frozen disposition",
            )
        self.complete_case(case_id, valid_audited_result=True)

    def complete_batch(self, *, gate_review_hash: str) -> None:
        self._ensure_not_revoked()
        try:
            self.state_store.complete_batch(
                self.authorization,
                gate_review_hash=gate_review_hash,
                now=self._clock(),
            )
        except Phase8StateError as exc:
            self._violate("audit_integrity_failure", str(exc))
        self._disable_inner()

    def revoke(self, *, reason: str, details: str) -> Phase8RevocationRecord:
        record = self.revocation_store.revoke(
            self.authorization.approval,
            reason=reason,
            details=details,
            now=self._clock(),
        )
        self._disable_inner()
        return record

    def _current_case(self) -> Phase8CasePackage:
        case_id = self._case_context.get()
        if case_id is None:
            self._violate(
                "unapproved_contract_or_provider",
                "provider review requires an explicit Phase 8 case scope",
            )
        try:
            return self.authorization.packages[case_id]
        except KeyError:
            self._violate(
                "unapproved_contract_or_provider",
                "case scope does not resolve to the frozen cohort",
            )

    def _ensure_live_authority(self) -> None:
        self._ensure_not_revoked()
        now = self._clock()
        approval = self.authorization.approval
        if not (approval.issued_at <= now < approval.expires_at):
            self._violate(
                "unapproved_contract_or_provider",
                "batch approval is not currently valid",
            )

    def _ensure_not_revoked(self) -> None:
        try:
            self.revocation_store.ensure_not_revoked(self.authorization.approval)
        except Phase8BatchRevokedError:
            self._disable_inner()
            raise
        except Phase8AuthorizationError as exc:
            self._disable_inner()
            raise Phase8BatchRevokedError(str(exc)) from exc

    def _stage_for_call(self, call: ReviewCall) -> Phase8StageAccess:
        stage_id = _stage_id(call)
        stages = {stage.stage_id: stage for stage in self.authorization.access_manifest.stages}
        return stages[stage_id]

    def _validate_call(self, case: Phase8CasePackage, call: ReviewCall) -> None:
        stage = self._stage_for_call(call)
        expected_round = 1 if stage.stage == "independent" else 2
        if call.reviewer_type != ReviewerType.MODEL or call.round != expected_round:
            self._violate(
                "unapproved_contract_or_provider",
                "reviewer type or round is outside the access manifest",
            )
        exact = {
            "provider": stage.provider,
            "model": stage.model,
            "role_version": stage.role_version,
            "prompt_version": stage.prompt_version,
            "schema_version": stage.schema_version,
        }
        if any(getattr(call, field) != expected for field, expected in exact.items()):
            self._violate(
                "unapproved_contract_or_provider",
                "provider, model, role, prompt, or schema differs from the manifest",
            )
        policy = call.provider_policy
        expected_policy = stage.policy
        policy_values = {
            "max_attempts": expected_policy.max_attempts,
            "timeout_seconds": expected_policy.timeout_seconds,
            "max_input_characters": expected_policy.max_input_characters,
            "max_output_tokens": expected_policy.max_output_tokens,
            "max_cost_usd": expected_policy.max_cost_usd,
            "reasoning_effort": expected_policy.reasoning_effort,
            "input_cost_per_million_usd": (expected_policy.input_cost_per_million_usd),
            "output_cost_per_million_usd": (expected_policy.output_cost_per_million_usd),
            "pricing_version": stage.pricing_version,
        }
        if any(getattr(policy, field) != expected for field, expected in policy_values.items()):
            self._violate(
                "unapproved_contract_or_provider",
                "provider policy differs from the exact manifest",
            )
        if (
            call.snapshot_hash != case.request_snapshot_hash
            or call.snapshot != case.request_snapshot
        ):
            self._violate(
                "context_leakage",
                "provider call does not contain the exact approved request snapshot",
            )
        if not (
            self.authorization.approval.issued_at
            <= call.requested_at
            < self.authorization.approval.expires_at
        ):
            self._violate(
                "unapproved_contract_or_provider",
                "provider call request time is outside batch authority",
            )
        if call.stage == ReviewStage.INDEPENDENT and (
            call.prior_claims
            or call.own_assessment is not None
            or call.peer_assessments
            or call.cross_review_responses
            or call.comparison_history
        ):
            self._violate(
                "context_leakage",
                "blind independent review contains peer or comparison context",
            )
        if call.stage == ReviewStage.CROSS_REVIEW and (
            call.own_assessment is None
            or len(call.peer_assessments) != 1
            or not call.comparison_history
            or call.cross_review_responses
        ):
            self._violate(
                "context_leakage",
                "cross-review context does not match the bounded contract",
            )
        if call.stage == ReviewStage.JUDGING and (
            call.own_assessment is None
            or len(call.peer_assessments) < 3
            or len(call.cross_review_responses) != 2
            or len(call.comparison_history) != 2
        ):
            self._violate(
                "context_leakage",
                "Reviewer C judgment context is incomplete or unbounded",
            )

    @staticmethod
    def _reservation_id(case_id: str, call: ReviewCall) -> str:
        return (
            f"{case_id}|{call.session_id}|{call.slot.value}|{call.stage.value}|"
            f"{call.round}|{call.attempt_number}"
        )

    def _violate(self, reason: str, details: str) -> None:
        self.revocation_store.revoke(
            self.authorization.approval,
            reason=reason,
            details=details,
            now=self._clock(),
        )
        self._disable_inner()
        raise Phase8SafetyViolation(details)

    def _disable_inner(self) -> None:
        inner = self._inner
        self._inner = None
        close = getattr(inner, "close", None)
        if callable(close):
            close()
