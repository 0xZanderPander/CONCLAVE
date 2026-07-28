from typing import Any

from conclave.contracts.validation import validate_review_result
from conclave.domain.enums import RecommendationCategory
from conclave.ledger.models import (
    RequestSnapshotRecord,
    ReviewerInvocationRecord,
    ReviewSessionRecord,
)
from conclave.reviewers.runtime import Assessment, ReviewerCJudgment
from conclave.task_packs.comparison import ComparisonResult, ComparisonRound

_AUTO_RESOLVE_CATEGORIES = {
    RecommendationCategory.OBSERVE,
    RecommendationCategory.COLLECT_MORE_DATA,
}


def _assessment(invocation: ReviewerInvocationRecord) -> Assessment:
    if invocation.status != "completed" or invocation.assessment_payload is None:
        raise ValueError(f"invocation {invocation.invocation_id!r} has no valid assessment")
    return Assessment.model_validate(invocation.assessment_payload)


def _judgment(invocation: ReviewerInvocationRecord) -> ReviewerCJudgment:
    if invocation.status != "completed" or invocation.assessment_payload is None:
        raise ValueError(f"invocation {invocation.invocation_id!r} has no valid judgment")
    return ReviewerCJudgment.model_validate(invocation.assessment_payload)


def _find(
    invocations: list[ReviewerInvocationRecord],
    *,
    slot: str,
    stage: str,
    round_number: int,
) -> ReviewerInvocationRecord:
    try:
        return next(
            invocation
            for invocation in invocations
            if invocation.reviewer_slot == slot
            and invocation.stage == stage
            and invocation.round == round_number
        )
    except StopIteration as exc:
        raise ValueError(
            f"missing invocation for slot={slot}, stage={stage}, round={round_number}"
        ) from exc


def build_review_result(
    *,
    session: ReviewSessionRecord,
    snapshot: RequestSnapshotRecord,
    invocations: list[ReviewerInvocationRecord],
    path: str,
    final_assessment: Assessment | None = None,
    comparisons: tuple[ComparisonRound, ...] = (),
    judgment: ReviewerCJudgment | None = None,
    route_triggers: tuple[str, ...] = (),
    auto_resolve_enabled: bool = True,
    routing_mode: str = "fixture",
) -> dict[str, Any]:
    request = snapshot.content
    baseline_invocation = _find(
        invocations,
        slot="A",
        stage="independent",
        round_number=1,
    )
    baseline = _assessment(baseline_invocation)
    comparison: ComparisonResult | None = (
        comparisons[-1].comparison if comparisons else None
    )

    if path == "a_only":
        final = final_assessment or baseline
        disagreement_level = "none"
        distance: float | None = None
        disagreement_summary = "Reviewer A completed the non-material review."
    elif path == "ab_agreement":
        final = final_assessment or _assessment(
            _find(invocations, slot="B", stage="independent", round_number=1)
        )
        disagreement_level = "within_tolerance"
        distance = comparison.distance if comparison is not None else 0.0
        disagreement_summary = "Reviewers A and B remained within tolerance."
    elif path == "cross_review_resolved":
        final = final_assessment or _assessment(
            _find(invocations, slot="A", stage="cross_review", round_number=2)
        )
        disagreement_level = "cross_reviewed"
        distance = (
            comparison.distance
            if comparison is not None
            else max(request["comparator"]["tolerance"] + 0.01, 0.4)
        )
        disagreement_summary = "A and B completed one bounded cross-review round."
    elif path == "c_tie_broken":
        judgment = judgment or _judgment(
            _find(invocations, slot="C", stage="judging", round_number=2)
        )
        if final_assessment is not None:
            final = final_assessment
        elif judgment.selected_slot is not None:
            final = _assessment(
                _find(
                    invocations,
                    slot=judgment.selected_slot,
                    stage="cross_review",
                    round_number=2,
                )
            )
        elif judgment.resolution_assessment is not None:
            final = judgment.resolution_assessment
        else:
            raise ValueError("reviewer-C judgment did not resolve to an assessment")
        disagreement_level = "tie_broken"
        distance = (
            comparison.distance
            if comparison is not None
            else max(request["comparator"]["tolerance"] + 0.01, 0.4)
        )
        disagreement_summary = (
            "Disagreement survived cross review; C reviewed independently and judged the options."
        )
    else:
        raise ValueError(f"unknown orchestration path {path!r}")

    can_auto_resolve = (
        auto_resolve_enabled
        and path in {"a_only", "ab_agreement"}
        and final.category in _AUTO_RESOLVE_CATEGORIES
        and not final.actions
        and not final.material
        and final.risk == "low"
        and not (comparison and comparison.hard_triggers)
    )
    status = "auto_resolved" if can_auto_resolve else "caller_decision_required"

    trigger = request["review_trigger"]["kind"]
    default_trigger = trigger if trigger != "manual" else "audit_sample"
    triggered_by = list(dict.fromkeys((default_trigger, *route_triggers)))
    reviewer_metadata = [
        {
            "slot": invocation.reviewer_slot,
            "reviewer_type": invocation.reviewer_type,
            "stage": invocation.stage,
            "round": invocation.round,
            "provider": invocation.provider,
            "model": invocation.model,
            "prompt_version": invocation.prompt_version,
            "schema_version": invocation.schema_version,
        }
        for invocation in invocations
    ]
    tie_breaker = None
    if path == "c_tie_broken":
        if judgment is None:
            raise ValueError("reviewer-C result is missing its judgment")
        tie_breaker = {
            "verdict": judgment.verdict,
            "selected_slot": judgment.selected_slot,
            "confidence": judgment.confidence,
            "evidence_quality": judgment.evidence_quality,
            "unresolved_claims": list(judgment.unresolved_claims),
        }

    resolution_basis = {
        "a_only": "a_only",
        "ab_agreement": "within_tolerance",
        "cross_review_resolved": "cross_review_converged",
        "c_tie_broken": (
            f"c_{judgment.verdict}" if judgment is not None else "c_judgment"
        ),
    }[path]
    decisive_stage = (
        comparisons[-1].stage.value if comparisons else "independent"
    )

    document: dict[str, Any] = {
        "contract_version": "review-result/v1",
        "review_session_id": session.session_id,
        "request_idempotency_key": session.idempotency_key,
        "occurrence_id": session.occurrence_id,
        "task_pack_ref": request["task_pack_ref"],
        "task_pack_hash": session.task_pack_hash,
        "review_plan_ref": session.plan_id,
        "review_plan_revision": session.plan_revision,
        "request_snapshot_hash": snapshot.content_hash,
        "evidence_version": session.evidence_version,
        "status": status,
        "recommendation": {
            "category": final.category.value,
            "summary": final.summary,
            "actions": [
                action.model_dump(mode="json", exclude_none=False) for action in final.actions
            ],
            "experiment": final.experiment,
        },
        "claims": [
            {
                "statement": claim,
                "evidence_references": [],
                "alternative_explanations": [],
            }
            for claim in final.claims
        ],
        "disagreement": {
            "level": disagreement_level,
            "summary": disagreement_summary,
            "distance": distance,
            "tolerance": request["comparator"]["tolerance"],
            "triggered_by": triggered_by,
            "hard_triggers": (
                [trigger.value for trigger in comparison.hard_triggers]
                if comparison is not None
                else []
            ),
            "agreements": list(comparison.agreements) if comparison is not None else [],
            "disagreements": (list(comparison.disagreements) if comparison is not None else []),
        },
        "comparison_history": [
            comparison_round.public_document()
            for comparison_round in comparisons
        ],
        "resolution": {
            "basis": resolution_basis,
            "decisive_stage": decisive_stage,
        },
        "baseline": {
            "category": baseline.category.value,
            "changed_by_panel": baseline.category != final.category,
        },
        "confidence": final.confidence,
        "evidence_quality": final.evidence_quality,
        "missing_evidence": list(final.missing_evidence),
        "risk": final.risk,
        "review_after_hours": final.review_after_hours,
        "panel_metadata": {
            "comparator_profile": request["comparator"]["profile"],
            "routing_mode": routing_mode,
            "reviewers": reviewer_metadata,
            "tie_breaker": tie_breaker,
        },
    }
    validate_review_result(document, request)
    return document
