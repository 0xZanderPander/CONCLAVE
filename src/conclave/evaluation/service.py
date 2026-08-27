from typing import Any

from conclave.domain.enums import ReviewState
from conclave.evaluation.models import (
    AssessmentFingerprint,
    DirectionalEvaluationMetrics,
    DirectionalIndicators,
    EvaluationAcceptance,
    ReviewerEvaluationCandidate,
)
from conclave.ledger.repository import LedgerRepository, canonical_hash
from conclave.reviewers.runtime import Assessment, AssessmentClaim


def _public_claim(claim: str | AssessmentClaim) -> dict[str, Any]:
    if isinstance(claim, str):
        return {
            "statement": claim,
            "evidence_references": [],
            "alternative_explanations": [],
        }
    return {
        "statement": claim.statement,
        "evidence_references": list(claim.evidence_references),
        "alternative_explanations": list(claim.alternative_explanations),
    }


def _baseline_projection(assessment: Assessment) -> dict[str, Any]:
    return {
        "recommendation": {
            "category": assessment.category.value,
            "summary": assessment.summary,
            "actions": [
                action.model_dump(mode="json", exclude_none=False)
                for action in assessment.actions
            ],
            "experiment": (
                assessment.experiment.model_dump(mode="json")
                if assessment.experiment is not None
                else None
            ),
        },
        "claims": [_public_claim(claim) for claim in assessment.claims],
        "confidence": assessment.confidence,
        "evidence_quality": assessment.evidence_quality,
        "risk": assessment.risk,
        "missing_evidence": list(assessment.missing_evidence),
        "review_after_hours": assessment.review_after_hours,
    }


def _final_projection(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "recommendation": result["recommendation"],
        "claims": result["claims"],
        "confidence": result["confidence"],
        "evidence_quality": result["evidence_quality"],
        "risk": result["risk"],
        "missing_evidence": result.get("missing_evidence", []),
        "review_after_hours": result.get("review_after_hours"),
    }


def _claim_identity(claim: dict[str, Any]) -> str:
    return canonical_hash(
        {
            "statement": claim["statement"],
            "evidence_references": claim.get("evidence_references", []),
        }
    )


class ReviewerEvaluationService:
    def __init__(self, repository: LedgerRepository) -> None:
        self._repository = repository

    def evaluate(self, session_id: str) -> EvaluationAcceptance:
        session = self._repository.get_session(session_id)
        if session is None:
            raise LookupError(f"unknown review session {session_id!r}")
        result = self._repository.get_result(session_id)
        feedback = self._repository.get_feedback(session_id)
        if result is None or feedback is None:
            raise LookupError("review evaluation requires result and feedback")
        invocations = self._repository.list_invocations(session_id)
        baseline_record = next(
            (
                invocation
                for invocation in invocations
                if invocation.reviewer_slot == "A"
                and invocation.stage == "independent"
                and invocation.round == 1
            ),
            None,
        )
        if baseline_record is None or baseline_record.assessment_payload is None:
            raise LookupError("review evaluation requires Reviewer A's baseline")
        baseline = Assessment.model_validate(baseline_record.assessment_payload)

        baseline_projection = _baseline_projection(baseline)
        final_projection = _final_projection(result.document)
        baseline_hash = canonical_hash(baseline_projection)
        final_hash = canonical_hash(final_projection)
        baseline_claims = {
            _claim_identity(claim) for claim in baseline_projection["claims"]
        }
        final_claims = {
            _claim_identity(claim) for claim in final_projection["claims"]
        }
        route = result.path
        relationship = feedback.relationship_to_panel
        total_latency_ms = sum(invocation.latency_ms or 0 for invocation in invocations)
        total_cost_usd = round(
            sum(invocation.cost_usd or 0 for invocation in invocations),
            8,
        )
        candidate = ReviewerEvaluationCandidate(
            contract_version="reviewer-evaluation-candidate/v1",
            review_session_id=session_id,
            evidence_version=session.evidence_version,
            result_hash=result.result_hash,
            feedback_hash=feedback.feedback_hash,
            route=route,
            interpretation="directional_only",
            baseline=AssessmentFingerprint(
                assessment_hash=baseline_hash,
                category=baseline.category.value,
            ),
            final=AssessmentFingerprint(
                assessment_hash=final_hash,
                category=result.document["recommendation"]["category"],
            ),
            indicators=DirectionalIndicators(
                panel_changed=baseline_hash != final_hash,
                category_changed=(
                    baseline.category.value
                    != result.document["recommendation"]["category"]
                ),
                caller_preference=feedback.panel_preference,
                additional_issue_count=len(final_claims - baseline_claims),
                cross_review_invoked=route
                in {"cross_review_resolved", "c_tie_broken"},
                cross_review_resolved=route == "cross_review_resolved",
                reviewer_c_invoked=route == "c_tie_broken",
                caller_override=relationship
                in {"accepted_with_changes", "rejected"},
                outcome_classification=feedback.outcome_classification,
                outcome_evidence_quality=feedback.outcome_evidence_quality,
                action_executed=feedback.action_executed,
                confounder_count=len(feedback.confounders),
                provider_attempt_count=sum(
                    invocation.attempt_count for invocation in invocations
                ),
                total_latency_ms=total_latency_ms,
                total_cost_usd=total_cost_usd,
            ),
        )
        record = self._repository.record_evaluation_candidate(
            session_id=session_id,
            document=candidate.model_dump(mode="json"),
        )
        return EvaluationAcceptance(
            candidate_id=record.candidate_id,
            candidate_hash=record.candidate_hash,
            session_id=session_id,
            state=ReviewState.EVALUATED,
        )

    def metrics(self) -> DirectionalEvaluationMetrics:
        return self._repository.directional_evaluation_metrics()
