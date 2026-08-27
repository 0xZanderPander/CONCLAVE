import json
import tempfile
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from conclave.auditing.verification import AuditVerifier
from conclave.config import Settings
from conclave.contracts.validation import ContractValidationError, validate_review_request
from conclave.domain.enums import ReviewerSlot, ReviewStage, ReviewState
from conclave.evaluation.service import ReviewerEvaluationService
from conclave.feedback import FeedbackIntakeService
from conclave.fixtures import load_design_plan_revisions
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import LedgerRepository, canonical_hash
from conclave.orchestration.service import ReviewOrchestrator
from conclave.pilot.phase8 import (
    Phase8AccessManifest,
    Phase8BatchApproval,
    Phase8BatchBudget,
    Phase8CasePackage,
    Phase8CohortCase,
    Phase8CohortManifest,
    Phase8Gate0Checks,
    Phase8Gate0Coverage,
    Phase8Gate0EvidenceItem,
    Phase8Gate0Report,
    phase8_content_hash,
    validate_phase8_approval_scope,
    validate_phase8_cohort_packages,
)
from conclave.pilot.phase8_safety import (
    Phase8AuthorizationError,
    Phase8SafetyRuntime,
    validate_phase8_guard_configuration,
)
from conclave.pilot.runner import (
    _feedback,
    _pilot_revision,
    _prepare_request,
    _repository,
    load_phase7_pilot_dataset,
)
from conclave.pilot.runtime import Phase7PilotRuntime
from conclave.plans.models import ReviewPlanRevision
from conclave.reviewers.runtime import ReviewerExecution
from conclave.task_packs.registry import default_task_pack_registry

PHASE8_RUNNER_VERSION = "phase8-runner/v1"


class Phase8CohortError(ValueError):
    """A curated cohort cannot be frozen without changing its source artifacts."""


class Phase8Gate0Error(RuntimeError):
    """The credential-free Gate 0 preflight did not pass."""


@dataclass(frozen=True, slots=True)
class Phase8CaseRunResult:
    case_id: str
    case_kind: str
    observed_disposition: str
    session_id: str | None
    result_hash: str | None
    audit_verified: bool


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase8CohortError(f"cannot read valid {label}: {path}") from exc
    if not isinstance(document, dict):
        raise Phase8CohortError(f"{label} must be a JSON object: {path}")
    return document


def _write_new_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as target:
            json.dump(document, target, indent=2, sort_keys=True)
            target.write("\n")
    except FileExistsError as exc:
        raise Phase8CohortError(f"refusing to overwrite immutable artifact: {path}") from exc


def load_phase8_case_packages(case_packages_dir: Path) -> tuple[Phase8CasePackage, ...]:
    paths = sorted(case_packages_dir.glob("*.json"))
    if len(paths) != 24:
        raise Phase8CohortError("the cohort directory must contain exactly 24 JSON packages")
    try:
        packages = tuple(
            Phase8CasePackage.model_validate(_read_json(path, f"case package {path.name}"))
            for path in paths
        )
    except ValidationError as exc:
        raise Phase8CohortError("a Phase 8 case package failed strict validation") from exc
    return tuple(sorted(packages, key=lambda package: package.case_id))


def _validate_declared_request_contracts(packages: tuple[Phase8CasePackage, ...]) -> None:
    for package in packages:
        valid = True
        try:
            validate_review_request(package.request_snapshot)
        except ContractValidationError:
            valid = False
        if valid != package.request_contract_valid:
            raise Phase8CohortError(
                f"declared request-contract validity is wrong for {package.case_id}"
            )


def _validate_freeze_chronology(
    packages: tuple[Phase8CasePackage, ...],
    *,
    frozen_at: datetime,
) -> None:
    if frozen_at.tzinfo is None or frozen_at.utcoffset() is None:
        raise Phase8CohortError("cohort freeze time must be timezone-aware")
    for package in packages:
        timestamps = [
            package.source_provenance.verified_at,
            package.redaction_attestation.reviewed_at,
            package.routing_profile.reviewed_at,
        ]
        if package.baseline is not None:
            timestamps.append(package.baseline.captured_at)
        if package.outcome_package is not None:
            timestamps.append(package.outcome_package.evaluated_at)
        if any(timestamp > frozen_at for timestamp in timestamps):
            raise Phase8CohortError(
                f"case {package.case_id} contains review evidence after the cohort freeze"
            )


def freeze_phase8_cohort(
    *,
    case_packages_dir: Path,
    output_path: Path,
    cohort_id: str,
    revision: int,
    frozen_at: datetime | None = None,
) -> Phase8CohortManifest:
    """Freeze 24 already-curated real/replay packages into one immutable manifest."""

    frozen_at = frozen_at or datetime.now(UTC)
    packages = load_phase8_case_packages(case_packages_dir)
    _validate_declared_request_contracts(packages)
    _validate_freeze_chronology(packages, frozen_at=frozen_at)
    manifest = Phase8CohortManifest.seal(
        contract_version="phase8-cohort-manifest/v1",
        cohort_id=cohort_id,
        revision=revision,
        frozen_at=frozen_at,
        cases=tuple(Phase8CohortCase.from_case_package(package) for package in packages),
    )
    validate_phase8_cohort_packages(manifest, packages)
    _write_new_json(output_path, manifest.model_dump(mode="json"))
    return manifest


def _load_cohort_bundle(
    *,
    cohort_manifest_path: Path,
    case_packages_dir: Path,
    access_manifest_path: Path,
    plan_revision_path: Path,
) -> tuple[
    Phase8CohortManifest,
    tuple[Phase8CasePackage, ...],
    Phase8AccessManifest,
    ReviewPlanRevision,
]:
    try:
        cohort = Phase8CohortManifest.model_validate(
            _read_json(cohort_manifest_path, "cohort manifest")
        )
        packages = load_phase8_case_packages(case_packages_dir)
        access = Phase8AccessManifest.model_validate(
            _read_json(access_manifest_path, "provider-access manifest")
        )
        plan = ReviewPlanRevision.model_validate(
            _read_json(plan_revision_path, "review-plan revision")
        )
    except ValidationError as exc:
        raise Phase8Gate0Error("a Gate 0 input artifact failed strict validation") from exc
    validate_phase8_cohort_packages(cohort, packages)
    _validate_declared_request_contracts(packages)
    _validate_freeze_chronology(packages, frozen_at=cohort.frozen_at)
    if access.cohort_id != cohort.cohort_id or access.cohort_hash != cohort.cohort_hash:
        raise Phase8Gate0Error("provider-access manifest does not match the frozen cohort")
    if access.created_at < cohort.frozen_at:
        raise Phase8Gate0Error("provider-access manifest predates the cohort freeze")
    if plan.plan_id != access.version_pins.plan_id or plan.revision != (
        access.version_pins.plan_revision
    ):
        raise Phase8Gate0Error("review-plan identity does not match the access manifest")
    if canonical_hash(plan.model_dump(mode="json")) != access.version_pins.plan_hash:
        raise Phase8Gate0Error("review-plan content does not match its frozen hash")
    for stage in access.stages:
        schedule = plan.slots[ReviewerSlot(stage.slot)]
        review_stage = ReviewStage(stage.stage)
        role, prompt, schema = schedule.contract_for_stage(review_stage)
        policy = schedule.provider_policy_for_stage(review_stage)
        expected = {
            "provider": schedule.provider,
            "model": schedule.model,
            "role_version": role,
            "prompt_version": prompt,
            "schema_version": schema,
            "pricing_version": policy.pricing_version,
        }
        actual = {
            "provider": stage.provider,
            "model": stage.model,
            "role_version": stage.role_version,
            "prompt_version": stage.prompt_version,
            "schema_version": stage.schema_version,
            "pricing_version": stage.pricing_version,
        }
        if actual != expected:
            raise Phase8Gate0Error(
                f"access stage {stage.stage_id} does not match the frozen review plan"
            )
        policy_fields = (
            "max_attempts",
            "timeout_seconds",
            "max_input_characters",
            "max_output_tokens",
            "max_cost_usd",
            "reasoning_effort",
            "input_cost_per_million_usd",
            "output_cost_per_million_usd",
        )
        if any(getattr(policy, field) != getattr(stage.policy, field) for field in policy_fields):
            raise Phase8Gate0Error(
                f"access policy {stage.stage_id} does not match the frozen review plan"
            )
    registry = default_task_pack_registry()
    for package in packages:
        if package.case_kind != "provider_eligible":
            continue
        if package.version_pins != access.version_pins:
            raise Phase8Gate0Error(
                f"case {package.case_id} does not use the access-manifest versions"
            )
        task_pack = registry.get(package.request_snapshot["task_pack_ref"])
        expected_task_pack_ref = (
            f"{access.version_pins.task_pack_id}/{access.version_pins.task_pack_revision}"
        )
        if task_pack.task_pack_ref != expected_task_pack_ref:
            raise Phase8Gate0Error("task-pack identity does not match its frozen version pin")
        if task_pack.content_hash != access.version_pins.task_pack_hash:
            raise Phase8Gate0Error("task-pack content does not match its frozen hash")
    return cohort, packages, access, plan


class _NoAttemptDryRunRuntime:
    """Use Phase 7's deterministic outputs without recording a provider attempt."""

    def __init__(self) -> None:
        case = next(
            item for item in load_phase7_pilot_dataset().cases if item.case_id == "phase7-005"
        )
        self.case = case
        self.inner = Phase7PilotRuntime(case)

    def review(self, call: Any) -> ReviewerExecution:
        execution = self.inner.review(call)
        return execution.model_copy(update={"attempts": ()})


def _run_local_audit_dry_run() -> dict[str, Any]:
    runtime = _NoAttemptDryRunRuntime()
    document = _prepare_request(runtime.case)
    engine, repository = _repository()
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(_pilot_revision(revision))
        intake = ReviewIntakeService(repository)
        accepted = intake.accept(deepcopy(document))
        replay = intake.accept(deepcopy(document))
        idempotent = (
            replay.session_id == accepted.session_id
            and replay.snapshot_hash == accepted.snapshot_hash
        )
        ReviewOrchestrator(repository, runtime).run(accepted.session_id)
        result = repository.get_result(accepted.session_id)
        if result is None:
            raise Phase8Gate0Error("local dry run did not produce a result")
        FeedbackIntakeService(repository).accept(
            session_id=accepted.session_id,
            caller_id=document["caller"]["caller_id"],
            document=_feedback(
                runtime.case,
                session_id=accepted.session_id,
                evidence_version=document["evidence_version"],
            ),
        )
        evaluation = ReviewerEvaluationService(repository).evaluate(accepted.session_id)
        audit = AuditVerifier(repository).verify_session(accepted.session_id)
        provider_metrics = repository.provider_metrics()
        if (
            provider_metrics.counts
            or provider_metrics.total_tokens
            or (provider_metrics.total_cost_usd)
        ):
            raise Phase8Gate0Error("local dry run recorded provider usage")
        if not idempotent or audit.final_state != ReviewState.EVALUATED:
            raise Phase8Gate0Error("local dry-run integrity checks did not pass")
        return {
            "fixture_case_id": runtime.case.case_id,
            "session_id": accepted.session_id,
            "result_hash": result.result_hash,
            "evaluation_hash": evaluation.candidate_hash,
            "audit_event_count": audit.event_count,
            "invocation_count": audit.invocation_count,
            "provider_attempt_count": 0,
            "provider_cost_usd": 0.0,
            "idempotency_verified": True,
            "audit_reconstruction_verified": True,
            "evaluation_verified": True,
            "interpretation": "mechanics_only_not_pilot_evidence",
        }
    finally:
        engine.dispose()


def _predict_no_call_controls(
    packages: tuple[Phase8CasePackage, ...],
    access: Phase8AccessManifest,
) -> dict[str, str]:
    registry = default_task_pack_registry()
    approved_providers = {stage.provider for stage in access.stages}
    controls = {package.control_type: package for package in packages if package.control_type}
    stale = controls["stale_package"]
    stale_eligibility = registry.validate_request(stale.request_snapshot)
    if stale_eligibility.review_eligible or "stale_evidence" not in stale_eligibility.reasons:
        raise Phase8Gate0Error("stale control is not predicted to stop as stale")
    invalid = controls["invalid_contract"]
    try:
        validate_review_request(invalid.request_snapshot)
    except ContractValidationError:
        pass
    else:
        raise Phase8Gate0Error("invalid-contract control unexpectedly validates")
    duplicate = controls["duplicate_replay"]
    if duplicate.duplicate_of_case_id is None:
        raise Phase8Gate0Error("duplicate control does not identify its original")
    unapproved = controls["unapproved_provider"]
    if unapproved.requested_provider in approved_providers:
        raise Phase8Gate0Error("unapproved-provider control names an approved provider")
    return {
        stale.case_id: "stop_stale",
        invalid.case_id: "stop_invalid_contract",
        duplicate.case_id: "stop_duplicate",
        unapproved.case_id: "stop_unapproved_provider",
    }


def _approval_shape_probe(
    cohort: Phase8CohortManifest,
    access: Phase8AccessManifest,
    *,
    generated_at: datetime,
) -> Phase8BatchApproval:
    eligible = tuple(case.case_id for case in cohort.cases if case.case_kind == "provider_eligible")
    controls = tuple(case.case_id for case in cohort.cases if case.case_kind == "no_call_control")
    probe = Phase8BatchApproval.seal(
        contract_version="phase8-batch-approval/v1",
        approval_id="gate0-shape-probe-not-authority",
        gate="gate_1_canary",
        batch_id="gate0-shape-probe-not-authority",
        cohort_id=cohort.cohort_id,
        cohort_hash=cohort.cohort_hash,
        access_manifest_id=access.manifest_id,
        access_manifest_hash=access.manifest_hash,
        gate_0_report_hash=phase8_content_hash({"gate0": "shape-probe"}),
        eligible_case_ids=eligible[:5],
        control_case_ids=controls,
        budget=Phase8BatchBudget(
            batch_spend_cap_usd=5,
            batch_attempt_cap=60,
            batch_token_cap=350_000,
            phase_spend_cap_usd=15.0,
            phase_attempt_cap=160,
            phase_token_cap=1_000_000,
            alert_percentages=(50, 75),
            automatic_stop_percentage=100,
            unused_authority_rolls_forward=False,
        ),
        approved_provider_access=True,
        approved_by="gate0-shape-probe-not-a-human-approval",
        stop_authority="gate0-shape-probe-not-a-human-approval",
        issued_at=generated_at + timedelta(days=1),
        expires_at=generated_at + timedelta(days=1, hours=1),
    )
    validate_phase8_approval_scope(probe, cohort, access)
    return probe


def _prove_preconstruction_boundary(
    *,
    cohort_manifest_path: Path,
    case_packages_dir: Path,
    access_manifest_path: Path,
    access: Phase8AccessManifest,
) -> str:
    from conclave.reviewers.factory import build_reviewer_runtime

    endpoints = {
        provider: next(stage.base_url for stage in access.stages if stage.provider == provider)
        for provider in ("openai", "anthropic")
    }
    with tempfile.TemporaryDirectory(prefix="conclave-phase8-gate0-") as temporary:
        root = Path(temporary)
        settings = Settings(
            environment="pilot",
            caller_auth_mode="static_bearer",
            caller_credentials_json='{"gate0":{"token":"local","scopes":["review:submit"]}}',
            reviewer_runtime_mode="phase8_pilot",
            openai_base_url=endpoints["openai"],
            anthropic_base_url=endpoints["anthropic"],
            phase8_cohort_manifest_path=str(cohort_manifest_path),
            phase8_case_packages_dir=str(case_packages_dir),
            phase8_access_manifest_path=str(access_manifest_path),
            phase8_gate0_report_path=str(root / "absent-gate0.json"),
            phase8_approval_path=str(root / "absent-approval.json"),
            phase8_runtime_state_path=str(root / "runtime-state.json"),
            phase8_revocation_path=str(root / "revocation.json"),
            phase8_openai_secret_path=str(root / "absent-openai.secret"),
            phase8_anthropic_secret_path=str(root / "absent-anthropic.secret"),
        )
        try:
            build_reviewer_runtime(settings)
        except Phase8AuthorizationError as exc:
            message = str(exc)
            if "Gate 0 report" not in message:
                raise Phase8Gate0Error(
                    "preconstruction boundary failed at the wrong authorization check"
                ) from exc
            return message
    raise Phase8Gate0Error("runtime construction succeeded without Gate 0 and approval")


def _coverage(
    cohort: Phase8CohortManifest,
    packages: tuple[Phase8CasePackage, ...],
) -> Phase8Gate0Coverage:
    eligible = [case for case in cohort.cases if case.case_kind == "provider_eligible"]
    sources = Counter(package.source_provenance.source_kind for package in packages)
    return Phase8Gate0Coverage(
        total_cases=24,
        provider_eligible_cases=20,
        no_call_controls=4,
        real_event_cases=sources["real_event"],
        historical_replay_cases=sources["historical_replay"],
        outcome_linked_cases=sum(case.outcome_linked for case in eligible),
        materially_eligible_cases=sum(case.materially_eligible for case in eligible),
        weak_partial_or_tracking_unhealthy_cases=sum(
            case.weak_partial_or_tracking_unhealthy for case in eligible
        ),
        prior_disagreement_cases=sum(case.prior_reviewers_disagreed for case in eligible),
        observe_or_no_change_baselines=sum(case.baseline_observe_or_no_change for case in eligible),
    )


def run_phase8_gate0(
    *,
    cohort_manifest_path: Path,
    case_packages_dir: Path,
    access_manifest_path: Path,
    plan_revision_path: Path,
    generated_at: datetime | None = None,
) -> Phase8Gate0Report:
    """Run the complete credential-free Gate 0 preflight and seal its evidence."""

    generated_at = generated_at or datetime.now(UTC)
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise Phase8Gate0Error("Gate 0 generation time must be timezone-aware")
    cohort, packages, access, plan = _load_cohort_bundle(
        cohort_manifest_path=cohort_manifest_path,
        case_packages_dir=case_packages_dir,
        access_manifest_path=access_manifest_path,
        plan_revision_path=plan_revision_path,
    )
    if generated_at < max(cohort.frozen_at, access.created_at):
        raise Phase8Gate0Error("Gate 0 cannot predate its frozen cohort or access manifest")
    controls = _predict_no_call_controls(packages, access)
    guard_details = validate_phase8_guard_configuration(access)
    boundary_message = _prove_preconstruction_boundary(
        cohort_manifest_path=cohort_manifest_path,
        case_packages_dir=case_packages_dir,
        access_manifest_path=access_manifest_path,
        access=access,
    )
    dry_run = _run_local_audit_dry_run()
    probe = _approval_shape_probe(cohort, access, generated_at=generated_at)
    package_hashes = tuple(package.case_package_hash for package in packages)
    redaction_hashes = tuple(package.redaction_attestation.attestation_hash for package in packages)
    baseline_hashes = tuple(
        package.baseline.baseline_hash for package in packages if package.baseline is not None
    )
    evidence = (
        Phase8Gate0EvidenceItem(
            check_id="all_case_packages_validated",
            passed=True,
            details=(
                "24 packages passed the immutable Phase 8 model and request-contract checks.",
                "Every package carries human-attested real-event or historical-replay provenance.",
            ),
            evidence_hashes=package_hashes,
        ),
        Phase8Gate0EvidenceItem(
            check_id="case_baseline_and_cohort_hashes_frozen",
            passed=True,
            details=(
                "All package, request, baseline, outcome, and cohort links were recomputed.",
                "All curation timestamps precede or equal the cohort freeze.",
            ),
            evidence_hashes=(cohort.cohort_hash, *baseline_hashes),
        ),
        Phase8Gate0EvidenceItem(
            check_id="two_person_redaction_review_complete",
            passed=True,
            details=("Every case has two distinct redaction reviewers and a complete checklist.",),
            evidence_hashes=redaction_hashes,
        ),
        Phase8Gate0EvidenceItem(
            check_id="plan_and_provider_access_manifest_frozen",
            passed=True,
            details=(
                f"Plan {plan.plan_id} r{plan.revision} matches its canonical hash.",
                "All eligible cases use the exact task-pack and access-manifest version pins.",
            ),
            evidence_hashes=(access.manifest_hash, access.version_pins.plan_hash),
        ),
        Phase8Gate0EvidenceItem(
            check_id="route_batch_phase_and_wall_time_guards_passed",
            passed=True,
            details=guard_details,
            evidence_hashes=(access.manifest_hash,),
        ),
        Phase8Gate0EvidenceItem(
            check_id="approval_and_case_allowlist_required_before_provider_construction",
            passed=True,
            details=(
                "Runtime construction stopped before secrets or provider adapters without "
                "Gate 0 and approval.",
                boundary_message,
            ),
        ),
        Phase8Gate0EvidenceItem(
            check_id="all_no_call_controls_predicted_to_stop",
            passed=True,
            details=tuple(
                f"{case_id}: {disposition}" for case_id, disposition in sorted(controls.items())
            ),
        ),
        Phase8Gate0EvidenceItem(
            check_id="audit_idempotency_and_evaluation_dry_run_passed",
            passed=True,
            details=(
                "A deterministic, network-free fixture produced an evaluated and "
                "reconstructable ledger.",
                "The dry run is mechanics-only and is not Phase 8 pilot evidence.",
            ),
            evidence_hashes=(
                dry_run["result_hash"],
                dry_run["evaluation_hash"],
                phase8_content_hash(dry_run),
            ),
        ),
        Phase8Gate0EvidenceItem(
            check_id="approval_record_shape_validated",
            passed=True,
            details=(
                "An in-memory, future-dated, non-authorizing Gate 1 shape probe validated "
                "exact scope and budgets.",
                "No approval artifact was written and no provider access was granted.",
            ),
            evidence_hashes=(probe.approval_hash,),
        ),
    )
    return Phase8Gate0Report.seal(
        contract_version="phase8-gate-0-report/v1",
        cohort_id=cohort.cohort_id,
        cohort_hash=cohort.cohort_hash,
        access_manifest_id=access.manifest_id,
        access_manifest_hash=access.manifest_hash,
        runner_version=PHASE8_RUNNER_VERSION,
        generated_at=generated_at,
        checks=Phase8Gate0Checks(**{item.check_id: True for item in evidence}),
        coverage=_coverage(cohort, packages),
        evidence=evidence,
        provider_attempt_count=0,
        provider_spend_usd=0.0,
        provider_credentials_loaded=False,
        passed=True,
    )


def write_phase8_gate0_evidence(
    report: Phase8Gate0Report,
    *,
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "phase8-gate0-report.json"
    markdown_path = output_dir / "PHASE_8_GATE_0_EVIDENCE.md"
    _write_new_json(json_path, report.model_dump(mode="json"))
    coverage = report.coverage
    lines = [
        "# Phase 8 Gate 0 Evidence",
        "",
        "**Status: PASSED OFFLINE — THIS IS NOT PROVIDER AUTHORIZATION.**",
        "",
        f"- Report hash: `{report.report_hash}`",
        f"- Cohort: `{report.cohort_id}` / `{report.cohort_hash}`",
        f"- Access manifest: `{report.access_manifest_id}` / `{report.access_manifest_hash}`",
        f"- Generated: `{report.generated_at.isoformat()}`",
        "- Provider credentials loaded: no",
        "- External provider attempts: 0",
        "- Provider spend: $0.00",
        "",
        "## Cohort coverage",
        "",
        "- 20 provider-eligible cases and 4 no-call controls",
        (
            f"- {coverage.real_event_cases} real-event and "
            f"{coverage.historical_replay_cases} historical-replay packages"
        ),
        f"- {coverage.outcome_linked_cases} outcome-linked eligible cases",
        f"- {coverage.materially_eligible_cases} materially eligible cases",
        f"- {coverage.weak_partial_or_tracking_unhealthy_cases} weak/partial/tracking cases",
        f"- {coverage.prior_disagreement_cases} prior-disagreement cases",
        f"- {coverage.observe_or_no_change_baselines} observe/no-change baselines",
        "",
        "## Evidence checks",
        "",
    ]
    for item in report.evidence:
        lines.append(f"### {item.check_id}")
        lines.append("")
        lines.extend(f"- {detail}" for detail in item.details)
        lines.append("")
    lines.extend(
        [
            "## Next authorization boundary",
            "",
            "Gate 1 remains disabled until a separate human approval is issued for "
            "exactly five eligible cases and all four controls.",
            "",
        ]
    )
    try:
        with markdown_path.open("x", encoding="utf-8") as target:
            target.write("\n".join(lines))
    except FileExistsError as exc:
        raise Phase8CohortError(
            f"refusing to overwrite immutable artifact: {markdown_path}"
        ) from exc
    return json_path, markdown_path


class Phase8BatchRunner:
    """Run only the exact batch already activated by the Phase 8 safety boundary."""

    def __init__(
        self,
        repository: LedgerRepository,
        runtime: Phase8SafetyRuntime,
    ) -> None:
        self.repository = repository
        self.runtime = runtime
        self.intake = ReviewIntakeService(repository)
        self.orchestrator = ReviewOrchestrator(repository, runtime)

    def run_case(
        self,
        case_id: str,
        *,
        now: datetime | None = None,
    ) -> Phase8CaseRunResult:
        now = now or datetime.now(UTC)
        if case_id not in self.runtime.authorization.approved_case_ids:
            raise Phase8AuthorizationError("case is outside the exact approved batch allowlist")
        package = self.runtime.authorization.packages[case_id]
        if package.case_kind == "no_call_control":
            return self._run_control(package)
        accepted = self.intake.accept(deepcopy(package.request_snapshot))
        if accepted.snapshot_hash != package.request_snapshot_hash:
            self.runtime.revoke(
                reason="audit_integrity_failure",
                details="stored request snapshot differs from the frozen case package",
            )
            raise Phase8Gate0Error("stored request snapshot differs from the frozen package")
        if accepted.state == ReviewState.STALE_OR_INELIGIBLE_EVIDENCE:
            self.runtime.complete_case(case_id, valid_audited_result=False)
            raise Phase8Gate0Error("provider-eligible case stopped during intake")
        try:
            with self.runtime.case_scope(case_id):
                self.orchestrator.run(accepted.session_id, now=now)
            result = self.repository.get_result(accepted.session_id)
            if result is None or result.path != package.routing_profile.expected_route:
                self.runtime.complete_case(case_id, valid_audited_result=False)
                raise Phase8Gate0Error("case result did not match its frozen expected route")
            audit = AuditVerifier(self.repository).verify_session(accepted.session_id)
            self.runtime.complete_case(case_id, valid_audited_result=True)
            return Phase8CaseRunResult(
                case_id=case_id,
                case_kind=package.case_kind,
                observed_disposition="provider_call_allowed",
                session_id=accepted.session_id,
                result_hash=audit.result_hash,
                audit_verified=True,
            )
        except Exception:
            state = self.runtime.state_store.read()
            usage = state.cases.get(case_id)
            if usage is not None and not usage.completed and not state.reservations:
                self.runtime.complete_case(case_id, valid_audited_result=False)
            raise

    def run_group(
        self,
        case_ids: tuple[str, ...],
        *,
        now: datetime | None = None,
    ) -> tuple[Phase8CaseRunResult, ...]:
        """Run one approved checkpoint group; groups never exceed five cases."""

        if not case_ids or len(case_ids) > 5:
            raise Phase8AuthorizationError("a Phase 8 execution group requires one to five cases")
        if len(case_ids) != len(set(case_ids)):
            raise Phase8AuthorizationError("a Phase 8 execution group cannot repeat a case")
        before = self.runtime.state_store.read()
        if before.batch_completed or before.reservations:
            raise Phase8AuthorizationError("the batch is not ready for an execution group")
        results = tuple(self.run_case(case_id, now=now) for case_id in case_ids)
        after = self.runtime.state_store.read()
        if after.reservations:
            raise Phase8AuthorizationError(
                "execution group ended with an unreconciled provider attempt"
            )
        return results

    def _run_control(self, package: Phase8CasePackage) -> Phase8CaseRunResult:
        disposition: str
        session_id: str | None = None
        if package.control_type == "invalid_contract":
            try:
                validate_review_request(package.request_snapshot)
            except ContractValidationError:
                disposition = "stop_invalid_contract"
            else:
                raise Phase8Gate0Error("invalid-contract control unexpectedly validated")
        elif package.control_type == "stale_package":
            accepted = self.intake.accept(deepcopy(package.request_snapshot))
            session_id = accepted.session_id
            if accepted.state != ReviewState.STALE_OR_INELIGIBLE_EVIDENCE:
                raise Phase8Gate0Error("stale control did not stop during intake")
            disposition = "stop_stale"
        elif package.control_type == "duplicate_replay":
            accepted = self.intake.accept(deepcopy(package.request_snapshot))
            replay = self.intake.accept(deepcopy(package.request_snapshot))
            session_id = accepted.session_id
            if (
                accepted.session_id != replay.session_id
                or accepted.snapshot_hash != replay.snapshot_hash
            ):
                raise Phase8Gate0Error("duplicate replay created a second review session")
            disposition = "stop_duplicate"
        elif package.control_type == "unapproved_provider":
            approved = {
                stage.provider for stage in self.runtime.authorization.access_manifest.stages
            }
            if package.requested_provider in approved:
                raise Phase8Gate0Error("provider control names an approved provider")
            disposition = "stop_unapproved_provider"
        else:
            raise Phase8Gate0Error("unknown no-call control type")
        self.runtime.complete_no_call_control(
            package.case_id,
            observed_disposition=disposition,
        )
        return Phase8CaseRunResult(
            case_id=package.case_id,
            case_kind=package.case_kind,
            observed_disposition=disposition,
            session_id=session_id,
            result_hash=None,
            audit_verified=True,
        )

    def complete_batch(self, *, gate_review_hash: str) -> None:
        self.runtime.complete_batch(gate_review_hash=gate_review_hash)
