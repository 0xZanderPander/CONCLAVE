import json
import math
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from conclave.auditing.verification import AuditVerifier
from conclave.domain.enums import ReviewerSlot, ReviewState
from conclave.evaluation.service import ReviewerEvaluationService
from conclave.feedback import FeedbackIntakeService
from conclave.fixtures import (
    build_feedback_for_session,
    load_design_plan_revisions,
    load_request_fixture,
)
from conclave.intake import ReviewIntakeService
from conclave.ledger.repository import LedgerRepository, create_schema
from conclave.orchestration.service import ReviewOrchestrator
from conclave.orchestration.state_machine import (
    InvalidTransitionError,
    validate_recovery_transition,
    validate_transition,
)
from conclave.paths import design_fixtures_root
from conclave.pilot.models import (
    Phase7PilotCase,
    Phase7PilotDataset,
    PilotFeedbackProfile,
)
from conclave.pilot.runtime import Phase7PilotRuntime
from conclave.plans.models import ReviewPlanRevision
from conclave.reviewers.prompts import (
    REVIEWER_A_CROSS_PROMPT_VERSION,
    REVIEWER_A_CROSS_ROLE_VERSION,
    REVIEWER_A_PROMPT_VERSION,
    REVIEWER_A_ROLE_VERSION,
    REVIEWER_B_CROSS_PROMPT_VERSION,
    REVIEWER_B_CROSS_ROLE_VERSION,
    REVIEWER_B_PROMPT_VERSION,
    REVIEWER_B_ROLE_VERSION,
    REVIEWER_C_BLIND_PROMPT_VERSION,
    REVIEWER_C_BLIND_ROLE_VERSION,
    REVIEWER_C_JUDGE_PROMPT_VERSION,
    REVIEWER_C_JUDGE_ROLE_VERSION,
)
from conclave.reviewers.runtime import ReviewerProviderExhaustedError

_PILOT_NOW = datetime(2026, 7, 28, 20, 0, tzinfo=UTC)


def load_phase7_pilot_dataset(path: Path | None = None) -> Phase7PilotDataset:
    path = path or design_fixtures_root() / "phase7-pilot-cases.json"
    with path.open(encoding="utf-8") as source:
        return Phase7PilotDataset.model_validate(json.load(source))


def _pilot_revision(revision: ReviewPlanRevision) -> ReviewPlanRevision:
    slots = dict(revision.slots)
    slots[ReviewerSlot.A] = slots[ReviewerSlot.A].model_copy(
        update={
            "provider": "phase7-synthetic",
            "model": "deterministic-pilot-v1",
            "role_version": REVIEWER_A_ROLE_VERSION,
            "prompt_version": REVIEWER_A_PROMPT_VERSION,
            "schema_version": "assessment-v2",
            "cross_review_role_version": REVIEWER_A_CROSS_ROLE_VERSION,
            "cross_review_prompt_version": REVIEWER_A_CROSS_PROMPT_VERSION,
            "cross_review_schema_version": "cross-review-v1",
        }
    )
    slots[ReviewerSlot.B] = slots[ReviewerSlot.B].model_copy(
        update={
            "provider": "phase7-synthetic",
            "model": "deterministic-pilot-v1",
            "role_version": REVIEWER_B_ROLE_VERSION,
            "prompt_version": REVIEWER_B_PROMPT_VERSION,
            "schema_version": "assessment-v2",
            "cross_review_role_version": REVIEWER_B_CROSS_ROLE_VERSION,
            "cross_review_prompt_version": REVIEWER_B_CROSS_PROMPT_VERSION,
            "cross_review_schema_version": "cross-review-v1",
        }
    )
    slots[ReviewerSlot.C] = slots[ReviewerSlot.C].model_copy(
        update={
            "provider": "phase7-synthetic",
            "model": "deterministic-pilot-v1",
            "role_version": REVIEWER_C_BLIND_ROLE_VERSION,
            "prompt_version": REVIEWER_C_BLIND_PROMPT_VERSION,
            "schema_version": "assessment-v2",
            "judging_role_version": REVIEWER_C_JUDGE_ROLE_VERSION,
            "judging_prompt_version": REVIEWER_C_JUDGE_PROMPT_VERSION,
            "judging_schema_version": "reviewer-c-judgment-v2",
        }
    )
    return revision.model_copy(update={"slots": slots})


def _repository() -> tuple[object, LedgerRepository]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(
        dbapi_connection: object,
        _connection_record: object,
    ) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    create_schema(engine)
    factory = sessionmaker(engine, expire_on_commit=False, class_=Session)
    return engine, LedgerRepository(factory)


def _prepare_request(case: Phase7PilotCase) -> dict[str, Any]:
    document = deepcopy(load_request_fixture(case.request_fixture))
    suffix = case.case_id.replace("-", "_")
    base_due_at = datetime.fromisoformat(
        document["review_trigger"]["due_at"].replace("Z", "+00:00")
    )
    due_at = base_due_at + timedelta(minutes=int(case.case_id[-3:]))
    document["caller"] = {
        "caller_id": "phase7-pilot-harness",
        "auth_subject": "phase7-local-fixture",
    }
    document["idempotency_key"] = f"phase7:{case.case_id}"
    document["evidence_version"] = f"phase7:{case.case_id}:evidence-v1"
    document["review_trigger"].update(
        {
            "occurrence_id": f"occ_{suffix}",
            "kind": case.trigger_kind,
            "due_at": due_at.isoformat().replace("+00:00", "Z"),
        }
    )
    if case.scenario == "stale":
        observed_at = due_at - timedelta(hours=25)
        document["quality"]["freshness"].update(
            {
                "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                "metric_period_start": (
                    observed_at - timedelta(hours=8)
                ).isoformat().replace("+00:00", "Z"),
                "metric_period_end": (
                    observed_at - timedelta(hours=1)
                ).isoformat().replace("+00:00", "Z"),
            }
        )
    return document


def _feedback(
    case: Phase7PilotCase,
    *,
    session_id: str,
    evidence_version: str,
) -> dict[str, Any]:
    document = build_feedback_for_session(
        session_id=session_id,
        evidence_version=evidence_version,
    )
    document["decision_ref"] = f"phase7-decision:{case.case_id}"
    document["action_ref"] = f"phase7-action:{case.case_id}"
    document["outcome"]["outcome_ref"] = f"phase7-outcome:{case.case_id}"
    document["outcome"]["confounders"] = []
    document["outcome"]["evaluated_at"] = "2026-07-28T19:00:00Z"
    profile: dict[
        PilotFeedbackProfile,
        tuple[str, str, str, str, bool, str],
    ] = {
        "beneficial_panel": (
            "accepted",
            "accepted_as_is",
            "preferred_panel",
            "beneficial",
            True,
            "adequate",
        ),
        "beneficial_baseline": (
            "modified",
            "accepted_with_changes",
            "preferred_baseline",
            "beneficial",
            True,
            "adequate",
        ),
        "harmful_baseline": (
            "rejected",
            "rejected",
            "preferred_baseline",
            "harmful",
            False,
            "strong",
        ),
        "mixed_panel": (
            "modified",
            "accepted_with_changes",
            "preferred_panel",
            "mixed",
            True,
            "weak",
        ),
        "no_effect_neither": (
            "no_action",
            "not_applicable",
            "neither",
            "no_effect",
            False,
            "adequate",
        ),
        "inconclusive": (
            "deferred",
            "not_applicable",
            "not_comparable",
            "inconclusive",
            False,
            "insufficient",
        ),
        "none": (
            "deferred",
            "not_applicable",
            "not_comparable",
            "inconclusive",
            False,
            "insufficient",
        ),
    }
    (
        disposition,
        relationship,
        preference,
        outcome,
        executed,
        quality,
    ) = profile[case.feedback_profile]
    document["decision_summary"] = {
        "disposition": disposition,
        "relationship_to_panel": relationship,
        "panel_preference": preference,
    }
    document["outcome"].update(
        {
            "classification": outcome,
            "action_executed": executed,
            "evidence_quality": quality,
        }
    )
    if not executed:
        document["action_ref"] = None
    return document


def _independence_isolated(runtime: Phase7PilotRuntime) -> bool:
    independent_calls = [
        call
        for call in runtime.calls
        if call.stage.value == "independent"
    ]
    return bool(independent_calls) and all(
        call.prior_claims == ()
        and call.own_assessment is None
        and call.peer_assessments == ()
        and call.cross_review_responses == ()
        and call.comparison_history == ()
        for call in independent_calls
    )


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(math.ceil(percentile * len(ordered)) - 1, 0)
    return ordered[index]


def _case_passed(
    case: Phase7PilotCase,
    *,
    final_state: str,
    route: str | None,
    status: str | None,
    category: str | None,
) -> bool:
    expected = case.expected
    return (
        final_state == expected.final_state
        and route == expected.route
        and status == expected.status
        and category == expected.category
    )


def _terminal_audit_verified(
    repository: LedgerRepository,
    *,
    session_id: str,
    final_state: str,
) -> bool:
    events = repository.audit_events("review_session", session_id)
    if (
        not events
        or events[0].event_type != "session_created"
        or [event.event_index for event in events]
        != list(range(1, len(events) + 1))
    ):
        return False
    reconstructed = ReviewState(events[0].event_payload["state"])
    for audit_event in events[1:]:
        if audit_event.event_type != "state_transitioned":
            continue
        source = ReviewState(audit_event.event_payload["source"])
        target = ReviewState(audit_event.event_payload["target"])
        if source != reconstructed:
            return False
        try:
            validate_transition(source, target)
        except InvalidTransitionError:
            try:
                validate_recovery_transition(source, target)
            except InvalidTransitionError:
                return False
        reconstructed = target
    return reconstructed.value == final_state


def run_phase7_pilot(
    *,
    dataset: Phase7PilotDataset | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    dataset = dataset or load_phase7_pilot_dataset()
    engine, repository = _repository()
    case_results: list[dict[str, Any]] = []
    try:
        for revision in load_design_plan_revisions():
            repository.add_plan_revision(_pilot_revision(revision))

        for case in dataset.cases:
            document = _prepare_request(case)
            accepted = ReviewIntakeService(repository).accept(document)
            idempotency_verified = not case.repeat_intake
            if case.repeat_intake:
                replay = ReviewIntakeService(repository).accept(deepcopy(document))
                idempotency_verified = (
                    replay.session_id == accepted.session_id
                    and replay.snapshot_hash == accepted.snapshot_hash
                )

            runtime = Phase7PilotRuntime(case)
            recovery_performed = False
            captured_error: Exception | None = None
            if accepted.state != ReviewState.STALE_OR_INELIGIBLE_EVIDENCE:
                try:
                    ReviewOrchestrator(repository, runtime).run(
                        accepted.session_id,
                        now=_PILOT_NOW,
                    )
                except ReviewerProviderExhaustedError as exc:
                    captured_error = exc
                    if case.recover_cross_review:
                        repository.recover_cross_review(
                            session_id=accepted.session_id,
                            operator_id="phase7-pilot-operator",
                            reason="Synthetic provider availability was restored.",
                            recovered_at=_PILOT_NOW + timedelta(minutes=1),
                        )
                        recovery_performed = True
                        captured_error = None
                        ReviewOrchestrator(repository, runtime).run(
                            accepted.session_id,
                            now=_PILOT_NOW + timedelta(minutes=1),
                        )

            result = repository.get_result(accepted.session_id)
            audit_verified = False
            terminal_audit_verified = False
            evidence_traceable = False
            clarity_heuristic = False
            route = result.path if result is not None else None
            status = result.document["status"] if result is not None else None
            category = (
                result.document["recommendation"]["category"]
                if result is not None
                else None
            )
            summary = (
                result.document["recommendation"]["summary"]
                if result is not None
                else None
            )
            if result is not None and case.feedback_profile != "none":
                FeedbackIntakeService(repository).accept(
                    session_id=accepted.session_id,
                    caller_id=document["caller"]["caller_id"],
                    document=_feedback(
                        case,
                        session_id=accepted.session_id,
                        evidence_version=document["evidence_version"],
                    ),
                )
                ReviewerEvaluationService(repository).evaluate(
                    accepted.session_id
                )
                verification = AuditVerifier(repository).verify_session(
                    accepted.session_id
                )
                audit_verified = verification.final_state == ReviewState.EVALUATED
                evidence_traceable = (
                    result.document["evidence_version"]
                    == document["evidence_version"]
                    and result.document["request_snapshot_hash"]
                    == accepted.snapshot_hash
                )
                clarity_heuristic = bool(
                    summary
                    and len(summary) >= 60
                    and "fixture" not in summary.lower()
                )

            session = repository.get_session(accepted.session_id)
            if session is None:
                raise RuntimeError("pilot session disappeared")
            if result is None:
                terminal_audit_verified = _terminal_audit_verified(
                    repository,
                    session_id=accepted.session_id,
                    final_state=session.current_state,
                )
            invocations = repository.list_invocations(accepted.session_id)
            attempt_count = sum(invocation.attempt_count for invocation in invocations)
            total_latency_ms = sum(
                invocation.latency_ms or 0 for invocation in invocations
            )
            total_cost_usd = round(
                sum(invocation.cost_usd or 0 for invocation in invocations),
                8,
            )
            final_state = session.current_state
            expected_pass = _case_passed(
                case,
                final_state=final_state,
                route=route,
                status=status,
                category=category,
            )
            case_results.append(
                {
                    "case_id": case.case_id,
                    "title": case.title,
                    "coverage": list(case.coverage),
                    "expected_outcome_passed": expected_pass,
                    "final_state": final_state,
                    "route": route,
                    "status": status,
                    "category": category,
                    "recommendation_summary": summary,
                    "input_material": accepted.material,
                    "eligibility_reasons": list(accepted.eligibility_reasons),
                    "invocation_count": len(invocations),
                    "provider_attempt_count": attempt_count,
                    "total_latency_ms": total_latency_ms,
                    "total_cost_usd": total_cost_usd,
                    "recovery_performed": recovery_performed,
                    "idempotency_verified": idempotency_verified,
                    "independent_context_isolated": (
                        _independence_isolated(runtime)
                        if runtime.calls
                        else True
                    ),
                    "snapshot_consistent": all(
                        call.snapshot_hash == accepted.snapshot_hash
                        for call in runtime.calls
                    ),
                    "evidence_traceable": evidence_traceable,
                    "audit_verified": audit_verified,
                    "terminal_audit_verified": terminal_audit_verified,
                    "clarity_heuristic_passed": clarity_heuristic,
                    "contained_error_type": (
                        type(captured_error).__name__
                        if captured_error is not None
                        else None
                    ),
                }
            )

        route_counts = Counter(
            result["route"] for result in case_results if result["route"]
        )
        status_counts = Counter(
            result["status"] for result in case_results if result["status"]
        )
        category_counts = Counter(
            result["category"] for result in case_results if result["category"]
        )
        coverage_counts = Counter(
            tag
            for case in dataset.cases
            for tag in case.coverage
        )
        completed = [result for result in case_results if result["route"]]
        latencies = [result["total_latency_ms"] for result in completed]
        provider_metrics = repository.provider_metrics()
        directional = ReviewerEvaluationService(repository).metrics()
        summary = {
            "case_count": len(case_results),
            "expected_outcomes_passed": sum(
                int(result["expected_outcome_passed"])
                for result in case_results
            ),
            "reliability_rate": (
                sum(
                    int(result["expected_outcome_passed"])
                    for result in case_results
                )
                / len(case_results)
            ),
            "completed_results": len(completed),
            "expected_terminal_cases": len(case_results) - len(completed),
            "recovered_cases": sum(
                int(result["recovery_performed"]) for result in case_results
            ),
            "idempotency_checks_passed": sum(
                int(result["idempotency_verified"])
                for result in case_results
                if "idempotency" in result["coverage"]
            ),
            "audit_verifications_passed": sum(
                int(result["audit_verified"]) for result in completed
            ),
            "terminal_audit_verifications_passed": sum(
                int(result["terminal_audit_verified"])
                for result in case_results
                if result["route"] is None
            ),
            "all_audit_traces_passed": sum(
                int(
                    result["audit_verified"]
                    or result["terminal_audit_verified"]
                )
                for result in case_results
            ),
            "independence_checks_passed": sum(
                int(result["independent_context_isolated"])
                for result in case_results
            ),
            "snapshot_consistency_checks_passed": sum(
                int(result["snapshot_consistent"]) for result in case_results
            ),
            "evidence_traceability_checks_passed": sum(
                int(result["evidence_traceable"]) for result in completed
            ),
            "clarity_heuristic_checks_passed": sum(
                int(result["clarity_heuristic_passed"]) for result in completed
            ),
            "total_latency_ms": sum(latencies),
            "average_latency_ms": (
                sum(latencies) / len(latencies) if latencies else None
            ),
            "p50_latency_ms": _percentile(latencies, 0.5),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "total_cost_usd": round(
                sum(result["total_cost_usd"] for result in case_results),
                8,
            ),
            "average_cost_usd_per_completed_result": (
                round(
                    sum(result["total_cost_usd"] for result in completed)
                    / len(completed),
                    8,
                )
                if completed
                else None
            ),
        }
        report = {
            "pilot_version": "phase7-pilot-results/v1",
            "dataset_version": dataset.dataset_version,
            "as_of": dataset.as_of,
            "interpretation": "directional_only",
            "summary": summary,
            "routing": {
                "counts": dict(sorted(route_counts.items())),
                "rates": {
                    route: count / len(completed)
                    for route, count in sorted(route_counts.items())
                },
            },
            "result_statuses": dict(sorted(status_counts.items())),
            "recommendation_categories": dict(sorted(category_counts.items())),
            "coverage": dict(sorted(coverage_counts.items())),
            "directional_evaluation_metrics": asdict(directional),
            "provider_attempt_metrics": {
                "counts": provider_metrics.counts,
                "total_tokens": provider_metrics.total_tokens,
                "total_cost_usd": provider_metrics.total_cost_usd,
                "average_latency_ms": provider_metrics.average_latency_ms,
            },
            "cases": case_results,
        }
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "phase7-pilot-results.json"
            output_path.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return report
    finally:
        engine.dispose()
