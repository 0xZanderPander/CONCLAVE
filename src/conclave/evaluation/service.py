from typing import Any

from conclave.domain.enums import ReviewStage, ReviewState
from conclave.evaluation.models import (
    AssessmentFingerprint,
    DirectionalEvaluationMetrics,
    DirectionalIndicators,
    EvaluationAcceptance,
    ReviewerEvaluationCandidate,
)
from conclave.ledger.repository import LedgerRepository, canonical_hash
from conclave.packs.registry import PackRegistry, default_pack_registry


def _claim_identity(claim: dict[str, Any]) -> str:
    return canonical_hash(
        {
            "statement": claim["statement"],
            "evidence_references": claim.get("evidence_references", []),
        }
    )


class ReviewerEvaluationService:
    def __init__(
        self,
        repository: LedgerRepository,
        packs: PackRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._packs = packs or default_pack_registry()

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
        snapshot = self._repository.get_snapshot(session_id)
        if snapshot is None:
            raise LookupError("review evaluation requires the request snapshot")
        pack = self._packs.for_document(snapshot.content)
        baseline = pack.assessment_from_output(
            pack.parse_output(
                ReviewStage.INDEPENDENT,
                baseline_record.schema_version,
                baseline_record.assessment_payload,
            )
        )

        baseline_projection = pack.assessment_projection(baseline)
        final_projection = pack.result_projection(result.document)
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
                category=str(baseline.category),
            ),
            final=AssessmentFingerprint(
                assessment_hash=final_hash,
                category=result.document["recommendation"]["category"],
            ),
            indicators=DirectionalIndicators(
                panel_changed=baseline_hash != final_hash,
                category_changed=(
                    str(baseline.category)
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
