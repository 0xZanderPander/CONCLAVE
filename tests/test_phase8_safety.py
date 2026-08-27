import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from conclave.config import Settings
from conclave.domain.enums import (
    RecommendationCategory,
    ReviewerSlot,
    ReviewerType,
    ReviewStage,
)
from conclave.pilot.phase8 import (
    Phase8BatchApproval,
    Phase8BatchBudget,
    Phase8Gate0Checks,
    Phase8Gate0Coverage,
    Phase8Gate0EvidenceItem,
    Phase8Gate0Report,
    phase8_content_hash,
)
from conclave.pilot.phase8_safety import (
    Phase8AuthorizationError,
    Phase8BatchRevokedError,
    Phase8SafetyRuntime,
    Phase8SafetyViolation,
    load_phase8_provider_secret,
    prepare_phase8_safety_boundary,
)
from conclave.plans.models import ProviderPolicy
from conclave.reviewers.factory import build_reviewer_runtime
from conclave.reviewers.runtime import (
    Assessment,
    ProviderCallResult,
    ProviderRegistryRuntime,
    ProviderUsage,
    RetryableReviewerProviderError,
    ReviewCall,
    ReviewerProviderExhaustedError,
)
from tests.test_phase8_foundation import (
    _access_manifest,
    _approval,
    _cohort,
)

_AUTH_NOW = datetime(2026, 7, 29, 17, 0, tzinfo=UTC)


def _hash_for_test(label: str) -> str:
    return phase8_content_hash({"label": label})


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _authorized_settings(
    tmp_path: Path,
    *,
    now: datetime,
    expired: bool = False,
    batch_spend_cap_usd: float = 5,
) -> tuple[Settings, object, object, object]:
    cohort, packages = _cohort()
    access = _access_manifest(cohort)
    gate_0_at = max(cohort.frozen_at, access.created_at, now - timedelta(minutes=2))
    gate_0 = Phase8Gate0Report.seal(
        contract_version="phase8-gate-0-report/v1",
        cohort_id=cohort.cohort_id,
        cohort_hash=cohort.cohort_hash,
        access_manifest_id=access.manifest_id,
        access_manifest_hash=access.manifest_hash,
        runner_version="phase8-runner/v1",
        generated_at=gate_0_at,
        checks=Phase8Gate0Checks(
            all_case_packages_validated=True,
            case_baseline_and_cohort_hashes_frozen=True,
            two_person_redaction_review_complete=True,
            plan_and_provider_access_manifest_frozen=True,
            route_batch_phase_and_wall_time_guards_passed=True,
            approval_and_case_allowlist_required_before_provider_construction=True,
            all_no_call_controls_predicted_to_stop=True,
            audit_idempotency_and_evaluation_dry_run_passed=True,
            approval_record_shape_validated=True,
        ),
        coverage=Phase8Gate0Coverage(
            total_cases=24,
            provider_eligible_cases=20,
            no_call_controls=4,
            real_event_cases=12,
            historical_replay_cases=12,
            outcome_linked_cases=12,
            materially_eligible_cases=6,
            weak_partial_or_tracking_unhealthy_cases=6,
            prior_disagreement_cases=4,
            observe_or_no_change_baselines=4,
        ),
        evidence=tuple(
            Phase8Gate0EvidenceItem(
                check_id=check_id,
                passed=True,
                details=("validated by the safety test fixture",),
            )
            for check_id in Phase8Gate0Checks.model_fields
        ),
        provider_attempt_count=0,
        provider_spend_usd=0.0,
        provider_credentials_loaded=False,
        passed=True,
    )
    base_approval = _approval(cohort, access)
    issued_at = gate_0_at + timedelta(seconds=1)
    expires_at = now - timedelta(seconds=1) if expired else now + timedelta(hours=2)
    if expired:
        issued_at = min(issued_at, expires_at - timedelta(hours=1))
    approval_document = base_approval.model_dump(
        mode="python",
        exclude={"approval_hash"},
    )
    approval_document.update(
        {
            "gate_0_report_hash": gate_0.report_hash,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "budget": Phase8BatchBudget(
                batch_spend_cap_usd=batch_spend_cap_usd,
                batch_attempt_cap=60,
                batch_token_cap=350_000,
                phase_spend_cap_usd=15.0,
                phase_attempt_cap=160,
                phase_token_cap=1_000_000,
                alert_percentages=(50, 75),
                automatic_stop_percentage=100,
                unused_authority_rolls_forward=False,
            ),
        }
    )
    approval = Phase8BatchApproval.seal(**approval_document)

    case_dir = tmp_path / "cases"
    for package in packages:
        _write(
            case_dir / f"{package.case_id}.json",
            package.model_dump(mode="json"),
        )
    cohort_path = tmp_path / "cohort.json"
    access_path = tmp_path / "access.json"
    gate_0_path = tmp_path / "gate0.json"
    approval_path = tmp_path / "approval.json"
    _write(cohort_path, cohort.model_dump(mode="json"))
    _write(access_path, access.model_dump(mode="json"))
    _write(gate_0_path, gate_0.model_dump(mode="json"))
    _write(approval_path, approval.model_dump(mode="json"))

    settings = Settings(
        environment="pilot",
        caller_auth_mode="static_bearer",
        caller_credentials_json=('{"phase8-pilot":{"token":"fixture","scopes":["review:submit"]}}'),
        reviewer_runtime_mode="phase8_pilot",
        openai_base_url="https://api.openai.test/v1",
        anthropic_base_url="https://api.anthropic.test/v1",
        phase8_cohort_manifest_path=str(cohort_path),
        phase8_case_packages_dir=str(case_dir),
        phase8_access_manifest_path=str(access_path),
        phase8_gate0_report_path=str(gate_0_path),
        phase8_approval_path=str(approval_path),
        phase8_runtime_state_path=str(tmp_path / "runtime-state.json"),
        phase8_revocation_path=str(tmp_path / "revocation.json"),
        phase8_openai_secret_path=str(tmp_path / "openai.secret"),
        phase8_anthropic_secret_path=str(tmp_path / "anthropic.secret"),
    )
    return settings, cohort, packages, approval


def _call(
    case: object,
    access: object,
    *,
    now: datetime,
) -> ReviewCall:
    stage = next(stage for stage in access.stages if stage.stage_id == "reviewer_a_independent")
    return ReviewCall(
        session_id=f"session-{case.case_id}",
        snapshot_hash=case.request_snapshot_hash,
        slot=ReviewerSlot.A,
        stage=ReviewStage.INDEPENDENT,
        round=1,
        reviewer_type=ReviewerType.MODEL,
        provider=stage.provider,
        model=stage.model,
        role_version=stage.role_version,
        prompt_version=stage.prompt_version,
        schema_version=stage.schema_version,
        snapshot=case.request_snapshot,
        requested_at=now,
        provider_policy=ProviderPolicy(
            max_attempts=stage.policy.max_attempts,
            timeout_seconds=stage.policy.timeout_seconds,
            max_input_characters=stage.policy.max_input_characters,
            max_output_tokens=stage.policy.max_output_tokens,
            max_cost_usd=stage.policy.max_cost_usd,
            reasoning_effort=stage.policy.reasoning_effort,
            input_cost_per_million_usd=stage.policy.input_cost_per_million_usd,
            output_cost_per_million_usd=stage.policy.output_cost_per_million_usd,
            pricing_version=stage.pricing_version,
        ),
    )


class _SuccessfulProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    def invoke(self, call: ReviewCall) -> ProviderCallResult:
        self.calls += 1
        return self.response(call)

    def response(self, call: ReviewCall) -> ProviderCallResult:
        return ProviderCallResult(
            output=Assessment(
                category=RecommendationCategory.OBSERVE,
                summary="No immediate change is supported.",
                confidence=0.8,
                evidence_quality="adequate",
            ),
            provider_request_id=f"request-{self.calls}",
            provider_response_id=f"response-{self.calls}",
            finish_status="completed",
            usage=ProviderUsage(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                cost_usd=0.02,
                pricing_version=call.provider_policy.pricing_version,
            ),
        )

    def close(self) -> None:
        self.closed = True


def _safety_runtime(
    settings: Settings,
    *,
    now: datetime,
    provider: object,
) -> Phase8SafetyRuntime:
    prepared = prepare_phase8_safety_boundary(settings, now=now)
    safety = Phase8SafetyRuntime(prepared, clock=lambda: now)
    inner = ProviderRegistryRuntime(
        {"openai": provider},
        max_attempts=2,
        attempt_guard=safety,
    )
    safety.bind_inner(inner)
    return safety


def test_phase8_mode_is_explicit_and_requires_every_safety_artifact() -> None:
    with pytest.raises(ValueError, match="ENVIRONMENT=pilot"):
        Settings(
            reviewer_runtime_mode="phase8_pilot",
            phase8_openai_secret_path="openai.secret",
            phase8_anthropic_secret_path="anthropic.secret",
        )

    with pytest.raises(ValueError, match="requires configured"):
        Settings(
            environment="pilot",
            caller_auth_mode="static_bearer",
            caller_credentials_json='{"pilot":{"token":"fixture","scopes":[]}}',
            reviewer_runtime_mode="phase8_pilot",
        )

    settings = Settings.from_environment(
        {
            "CONCLAVE_ENVIRONMENT": "pilot",
            "CONCLAVE_CALLER_AUTH_MODE": "static_bearer",
            "CONCLAVE_CALLER_CREDENTIALS_JSON": ('{"pilot":{"token":"fixture","scopes":[]}}'),
            "CONCLAVE_REVIEWER_RUNTIME_MODE": "phase8_pilot",
            "CONCLAVE_OPENAI_API_KEY": "must-not-load",
            "CONCLAVE_ANTHROPIC_API_KEY": "must-not-load",
            "CONCLAVE_PHASE8_COHORT_MANIFEST_PATH": "cohort.json",
            "CONCLAVE_PHASE8_CASE_PACKAGES_DIR": "cases",
            "CONCLAVE_PHASE8_ACCESS_MANIFEST_PATH": "access.json",
            "CONCLAVE_PHASE8_GATE0_REPORT_PATH": "gate0.json",
            "CONCLAVE_PHASE8_APPROVAL_PATH": "approval.json",
            "CONCLAVE_PHASE8_RUNTIME_STATE_PATH": "state.json",
            "CONCLAVE_PHASE8_REVOCATION_PATH": "revocation.json",
            "CONCLAVE_PHASE8_OPENAI_SECRET_PATH": "openai.secret",
            "CONCLAVE_PHASE8_ANTHROPIC_SECRET_PATH": "anthropic.secret",
        }
    )
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None


def test_external_provider_secret_must_be_private_regular_file(
    tmp_path: Path,
) -> None:
    secret_path = tmp_path / "provider.secret"
    secret_path.write_text("fixture-secret\n", encoding="utf-8")
    secret_path.chmod(0o600)

    assert load_phase8_provider_secret(str(secret_path), "test") == "fixture-secret"

    secret_path.chmod(0o644)
    with pytest.raises(Phase8AuthorizationError, match="group or world"):
        load_phase8_provider_secret(str(secret_path), "test")


def test_expired_approval_blocks_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = _AUTH_NOW
    settings, _, _, _ = _authorized_settings(tmp_path, now=now, expired=True)
    constructed: list[str] = []
    secrets_loaded: list[str] = []

    def constructor(**_kwargs: object) -> object:
        constructed.append("provider")
        return object()

    monkeypatch.setattr(
        "conclave.reviewers.factory.OpenAIResponsesProvider",
        constructor,
    )
    monkeypatch.setattr(
        "conclave.reviewers.factory.AnthropicMessagesProvider",
        constructor,
    )
    monkeypatch.setattr(
        "conclave.reviewers.factory.load_phase8_provider_secret",
        lambda _path, provider: secrets_loaded.append(provider) or "fixture",
    )

    with pytest.raises(Phase8AuthorizationError, match="chronology or approval"):
        build_reviewer_runtime(settings)

    assert constructed == []
    assert secrets_loaded == []


def test_gate_2_cannot_start_without_completed_gate_1_state(
    tmp_path: Path,
) -> None:
    now = _AUTH_NOW
    settings, cohort, _, gate_1 = _authorized_settings(tmp_path, now=now)
    eligible = tuple(case.case_id for case in cohort.cases if case.case_kind == "provider_eligible")
    gate_2_document = gate_1.model_dump(mode="python", exclude={"approval_hash"})
    gate_2_document.update(
        {
            "approval_id": "phase8-gate2-approval-001",
            "gate": "gate_2_completion",
            "batch_id": "phase8-gate2-batch-001",
            "prior_gate_review_hash": _hash_for_test("gate-1-review"),
            "eligible_case_ids": eligible[5:],
            "control_case_ids": (),
            "budget": gate_1.budget.model_copy(update={"batch_spend_cap_usd": 10}),
        }
    )
    gate_2 = Phase8BatchApproval.seal(**gate_2_document)
    _write(
        Path(settings.phase8_approval_path or ""),
        gate_2.model_dump(mode="json"),
    )

    with pytest.raises(Phase8AuthorizationError, match="Gate 2 cannot start"):
        prepare_phase8_safety_boundary(settings, now=now)


def test_tampered_durable_state_blocks_reconstruction(tmp_path: Path) -> None:
    now = _AUTH_NOW
    settings, _, _, _ = _authorized_settings(tmp_path, now=now)
    prepare_phase8_safety_boundary(settings, now=now)
    state_path = Path(settings.phase8_runtime_state_path or "")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["batch_cost_usd"] = 4.99
    _write(state_path, state)

    with pytest.raises(Phase8AuthorizationError, match="runtime state is invalid"):
        prepare_phase8_safety_boundary(settings, now=now)


def test_successful_attempt_is_case_scoped_and_durably_accounted(
    tmp_path: Path,
) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(tmp_path, now=now)
    access = _access_manifest(cohort)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    case = packages[0]
    call = _call(case, access, now=now)

    with runtime.case_scope(case.case_id):
        execution = runtime.review(call)

    state = runtime.state_store.read()
    assert execution.output.category == RecommendationCategory.OBSERVE
    assert provider.calls == 1
    assert state.batch_attempt_count == 1
    assert state.batch_token_count == 120
    assert state.batch_cost_usd == 0.02
    assert state.cases[case.case_id].stage_ids == ("reviewer_a_independent",)


def test_provider_review_without_case_scope_revokes_before_network(
    tmp_path: Path,
) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(tmp_path, now=now)
    access = _access_manifest(cohort)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)

    with pytest.raises(Phase8SafetyViolation, match="explicit Phase 8 case scope"):
        runtime.review(_call(packages[0], access, now=now))

    assert provider.calls == 0
    assert provider.closed is True
    assert Path(settings.phase8_revocation_path or "").is_file()
    with pytest.raises(Phase8BatchRevokedError):
        runtime.revocation_store.ensure_not_revoked(runtime.authorization.approval)


def test_no_call_control_can_never_reach_provider(tmp_path: Path) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(tmp_path, now=now)
    access = _access_manifest(cohort)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    control = next(package for package in packages if package.control_type == "duplicate_replay")

    with (
        runtime.case_scope(control.case_id),
        pytest.raises(
            Phase8SafetyViolation,
            match="no-call control",
        ),
    ):
        runtime.review(_call(control, access, now=now))

    assert provider.calls == 0


def test_exact_snapshot_and_blind_context_are_enforced(tmp_path: Path) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(tmp_path, now=now)
    access = _access_manifest(cohort)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    case = packages[0]
    call = _call(case, access, now=now).model_copy(update={"prior_claims": ("hidden peer claim",)})

    with (
        runtime.case_scope(case.case_id),
        pytest.raises(
            Phase8SafetyViolation,
            match="blind independent",
        ),
    ):
        runtime.review(call)

    assert provider.calls == 0


def test_model_substitution_is_rejected_before_network(tmp_path: Path) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(tmp_path, now=now)
    access = _access_manifest(cohort)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    case = packages[0]
    call = _call(case, access, now=now).model_copy(update={"model": "silent-substitute"})

    with (
        runtime.case_scope(case.case_id),
        pytest.raises(
            Phase8SafetyViolation,
            match="differs from the manifest",
        ),
    ):
        runtime.review(call)

    assert provider.calls == 0


def test_batch_budget_is_reserved_before_each_network_attempt(
    tmp_path: Path,
) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(
        tmp_path,
        now=now,
        batch_spend_cap_usd=0.05,
    )
    access = _access_manifest(cohort)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    case = packages[0]

    with (
        runtime.case_scope(case.case_id),
        pytest.raises(
            Phase8SafetyViolation,
            match="spend ceiling",
        ),
    ):
        runtime.review(_call(case, access, now=now))

    assert provider.calls == 0


def test_retry_is_authorized_and_accounted_one_attempt_at_a_time(
    tmp_path: Path,
) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(tmp_path, now=now)
    access = _access_manifest(cohort)

    class RetryOnce(_SuccessfulProvider):
        def invoke(self, call: ReviewCall) -> ProviderCallResult:
            self.calls += 1
            if self.calls == 1:
                raise RetryableReviewerProviderError("temporary provider failure")
            return self.response(call)

    provider = RetryOnce()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    case = packages[0]

    with runtime.case_scope(case.case_id):
        runtime.review(_call(case, access, now=now))

    state = runtime.state_store.read()
    assert provider.calls == 2
    assert state.batch_attempt_count == 2
    assert state.cases[case.case_id].attempt_count == 2


def test_control_stops_are_recorded_without_provider_usage(tmp_path: Path) -> None:
    now = _AUTH_NOW
    settings, _, packages, _ = _authorized_settings(tmp_path, now=now)
    provider = _SuccessfulProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    controls = [package for package in packages if package.case_kind == "no_call_control"]

    for control in controls:
        runtime.complete_no_call_control(
            control.case_id,
            observed_disposition=control.expected_disposition,
        )

    state = runtime.state_store.read()
    assert provider.calls == 0
    assert all(state.cases[control.case_id].completed for control in controls)
    assert state.batch_attempt_count == 0


def test_second_invalid_provider_output_revokes_the_batch(tmp_path: Path) -> None:
    now = _AUTH_NOW
    settings, cohort, packages, _ = _authorized_settings(tmp_path, now=now)
    access = _access_manifest(cohort)

    class InvalidProvider:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, call: ReviewCall) -> ProviderCallResult:
            self.calls += 1
            return ProviderCallResult(
                output={"not": "a valid assessment"},
                usage=ProviderUsage(
                    input_tokens=20,
                    output_tokens=10,
                    total_tokens=30,
                    cost_usd=0.01,
                    pricing_version=call.provider_policy.pricing_version,
                ),
            )

    provider = InvalidProvider()
    runtime = _safety_runtime(settings, now=now, provider=provider)
    first, second = packages[:2]

    with runtime.case_scope(first.case_id), pytest.raises(ReviewerProviderExhaustedError):
        runtime.review(_call(first, access, now=now))
    assert not Path(settings.phase8_revocation_path or "").exists()

    with (
        runtime.case_scope(second.case_id),
        pytest.raises(
            Phase8SafetyViolation,
            match="more than one",
        ),
    ):
        runtime.review(_call(second, access, now=now))

    assert provider.calls == 2
    assert Path(settings.phase8_revocation_path or "").is_file()
