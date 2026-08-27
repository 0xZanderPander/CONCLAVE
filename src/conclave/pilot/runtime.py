from datetime import UTC, datetime, timedelta

from conclave.domain.enums import RecommendationCategory, ReviewerSlot, ReviewStage
from conclave.pilot.models import Phase7PilotCase
from conclave.reviewers.runtime import (
    Assessment,
    AssessmentClaim,
    CrossReviewResponse,
    ExperimentDefinition,
    PeerClaimReview,
    ProviderAttempt,
    ProviderUsage,
    RecommendedAction,
    ReviewCall,
    ReviewerCJudgment,
    ReviewerExecution,
    ReviewerProviderExhaustedError,
)

_PILOT_CLOCK = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def _claim_ids(assessment: Assessment) -> tuple[str, ...]:
    return tuple(
        claim.claim_id
        for claim in assessment.claims
        if isinstance(claim, AssessmentClaim) and claim.claim_id is not None
    )


class Phase7PilotRuntime:
    """Deterministic assessment-v2 runtime with synthetic safe telemetry."""

    def __init__(self, case: Phase7PilotCase) -> None:
        self.case = case
        self.calls: list[ReviewCall] = []
        self.fault_used = False

    def review(self, call: ReviewCall) -> ReviewerExecution:
        self.calls.append(call)
        output = self._output(call)
        if self._fault_applies(call) and not self.fault_used:
            self.fault_used = True
            if self.case.fault.startswith("malformed"):
                attempt = self._failed_attempt(
                    call,
                    status="invalid_output",
                    error_type="invalid_output",
                )
                raise ReviewerProviderExhaustedError(
                    "synthetic provider output failed the reviewer contract",
                    (attempt,),
                )
            if self.case.fault == "cross_failure_once":
                attempt = self._failed_attempt(
                    call,
                    status="permanent_failure",
                    error_type="synthetic_provider_failure",
                )
                raise ReviewerProviderExhaustedError(
                    "synthetic cross-review provider failure",
                    (attempt,),
                )
            timeout = self._failed_attempt(
                call,
                status="retryable_failure",
                error_type="synthetic_timeout",
            )
            succeeded = self._succeeded_attempt(
                call,
                attempt_number=call.attempt_number + 1,
            )
            return ReviewerExecution(output=output, attempts=(timeout, succeeded))
        return ReviewerExecution(
            output=output,
            attempts=(self._succeeded_attempt(call),),
        )

    def _output(
        self,
        call: ReviewCall,
    ) -> Assessment | CrossReviewResponse | ReviewerCJudgment:
        if call.stage == ReviewStage.JUDGING:
            return self._judgment(call)
        assessment = self._assessment(self._assessment_code(call), call)
        if call.stage != ReviewStage.CROSS_REVIEW:
            return assessment
        peer_claims = tuple(
            claim
            for peer in call.peer_assessments
            for claim in peer.assessment.claims
            if isinstance(claim, AssessmentClaim) and claim.claim_id is not None
        )
        own_category = (
            call.own_assessment.assessment.category
            if call.own_assessment is not None
            else None
        )
        return CrossReviewResponse(
            disposition=(
                "affirm" if own_category == assessment.category else "revise"
            ),
            peer_claim_reviews=tuple(
                PeerClaimReview(
                    claim_id=claim.claim_id or "",
                    position=(
                        "accept"
                        if claim.statement == self._claim_statement(
                            self._assessment_code(call)
                        )
                        else "challenge"
                    ),
                    summary=(
                        "The peer claim was checked against the same immutable "
                        "evidence before this response was formed."
                    ),
                    evidence_references=("quality.optimization_eligible",),
                )
                for claim in peer_claims
            ),
            assessment=assessment,
        )

    def _assessment_code(self, call: ReviewCall) -> str:
        scenario = self.case.scenario
        if scenario == "a_observe":
            return "observe"
        if scenario in {"a_collect", "ab_collect", "failed_goal_collect"}:
            return "collect"
        if scenario == "ab_tracking":
            return "tracking"
        if scenario == "ab_pause":
            return "pause"
        if scenario == "ab_experiment":
            return "experiment"
        if scenario == "cross_collect":
            if call.stage == ReviewStage.CROSS_REVIEW:
                return "collect"
            return "pause" if call.slot == ReviewerSlot.A else "collect"
        if scenario == "cross_pause":
            if call.stage == ReviewStage.CROSS_REVIEW:
                return "pause"
            return "pause" if call.slot == ReviewerSlot.A else "collect"
        if scenario in {
            "c_select_a",
            "c_select_b",
            "c_synthesize",
            "c_insufficient",
        }:
            if call.slot == ReviewerSlot.A:
                return "pause"
            if call.slot == ReviewerSlot.B:
                return "collect"
            return "experiment" if scenario == "c_synthesize" else "collect"
        raise ValueError(f"scenario {scenario!r} does not invoke a reviewer")

    @staticmethod
    def _claim_statement(code: str) -> str:
        return {
            "observe": (
                "The submitted performance evidence is healthy and does not "
                "support an immediate operational change."
            ),
            "collect": (
                "The submitted evidence requires another complete measurement "
                "window before an operational change is justified."
            ),
            "tracking": (
                "The submitted conversion record shows unhealthy tracking that "
                "must be diagnosed before performance is interpreted."
            ),
            "pause": (
                "Creative cr_b has weaker submitted efficiency than creative cr_a "
                "and is the bounded target for caller review."
            ),
            "experiment": (
                "The submitted evidence supports a bounded experiment rather than "
                "a broad operational change."
            ),
        }[code]

    def _assessment(self, code: str, call: ReviewCall) -> Assessment:
        stage_prefix = (
            "After bounded cross-review, "
            if call.stage == ReviewStage.CROSS_REVIEW
            else ""
        )
        subject = (
            "the panel should"
            if call.stage == ReviewStage.CROSS_REVIEW
            else "The review should"
        )
        quality = call.snapshot["quality"]
        common = {
            "claims": (
                AssessmentClaim(
                    statement=self._claim_statement(code),
                    evidence_references=(
                        "sections.evidence.metrics.impressions",
                        "quality.optimization_eligible",
                    ),
                    alternative_explanations=(
                        "Attribution lag may change the next complete evidence window.",
                    ),
                ),
            ),
            "material": False,
            "tracking_health": quality["tracking_health"],
            "optimization_eligible": quality["optimization_eligible"],
            "primary_conversion": call.snapshot["sections"]["goal"][
                "primary_conversion"
            ],
        }
        if code == "observe":
            return Assessment(
                category=RecommendationCategory.OBSERVE,
                summary=(
                    f"{stage_prefix}{subject} maintain the current "
                    "configuration because submitted evidence is healthy and "
                    "within the decision threshold."
                ),
                risk="low",
                confidence=0.82,
                evidence_quality=quality["evidence_quality_label"],
                expected_goal_impact="neutral",
                **common,
            )
        if code == "collect":
            return Assessment(
                category=RecommendationCategory.COLLECT_MORE_DATA,
                summary=(
                    f"{stage_prefix}{subject} collect another complete "
                    "evidence window before changing delivery."
                ),
                risk="low",
                confidence=0.74,
                evidence_quality=quality["evidence_quality_label"],
                expected_goal_impact="uncertain",
                missing_evidence=("one complete attribution window",),
                review_after_hours=12,
                **common,
            )
        if code == "tracking":
            return Assessment(
                category=RecommendationCategory.TRACKING_OR_DATA_PROBLEM,
                summary=(
                    f"{stage_prefix}{subject} diagnose the submitted "
                    "conversion-tracking gap before interpreting performance."
                ),
                actions=(
                    RecommendedAction(
                        type="diagnose_tracking",
                        target_id="conv_eligible_giveaway_entry_completed",
                        urgency="high",
                        confidence=0.9,
                    ),
                ),
                risk="high",
                confidence=0.9,
                evidence_quality="weak",
                expected_goal_impact="uncertain",
                missing_evidence=("restored server-event receipts",),
                **common,
            )
        if code == "pause":
            return Assessment(
                category=RecommendationCategory.OPERATIONAL_CHANGE,
                summary=(
                    f"{stage_prefix}{subject} pause creative cr_b for "
                    "caller approval because its submitted efficiency is weaker "
                    "than creative cr_a."
                ),
                actions=(
                    RecommendedAction(
                        type="pause_creative",
                        target_id="cr_b",
                        urgency="normal",
                        confidence=0.84,
                    ),
                ),
                risk="medium",
                confidence=0.84,
                evidence_quality=quality["evidence_quality_label"],
                expected_goal_impact="positive",
                **common,
            )
        if code == "experiment":
            return Assessment(
                category=RecommendationCategory.EXPERIMENT,
                summary=(
                    f"{stage_prefix}{subject} run a bounded creative-message "
                    "experiment before any broader campaign change."
                ),
                actions=(
                    RecommendedAction(
                        type="propose_experiment",
                        target_id="bc_glm_giveaway_2026_07",
                        urgency="normal",
                        confidence=0.78,
                    ),
                ),
                experiment=ExperimentDefinition(
                    hypothesis=(
                        "A clearer eligibility message improves completed entries "
                        "without exceeding the submitted CPA target."
                    ),
                    control="current creative message",
                    isolated_change="eligibility message only",
                    success_metric="eligible_giveaway_entry_completed",
                    minimum_evidence="at least 50 conversions per arm",
                    exposure_limit="no more than half of eligible traffic",
                    stop_conditions=(
                        "tracking health degrades",
                        "CPA exceeds the submitted stop threshold",
                    ),
                    review_after_hours=48,
                ),
                risk="medium",
                confidence=0.78,
                evidence_quality=quality["evidence_quality_label"],
                expected_goal_impact="positive",
                review_after_hours=48,
                **common,
            )
        raise ValueError(f"unknown synthetic assessment code {code!r}")

    def _judgment(self, call: ReviewCall) -> ReviewerCJudgment:
        own_ids = (
            _claim_ids(call.own_assessment.assessment)
            if call.own_assessment is not None
            else ()
        )
        response_ids = {
            response.slot: _claim_ids(response.response.assessment)
            for response in call.cross_review_responses
        }
        all_ids = tuple(
            claim_id
            for ids in (*response_ids.values(), own_ids)
            for claim_id in ids
        )
        if self.case.scenario in {"c_select_a", "c_select_b"}:
            selected = (
                ReviewerSlot.A
                if self.case.scenario == "c_select_a"
                else ReviewerSlot.B
            )
            rejected = (
                ReviewerSlot.B if selected == ReviewerSlot.A else ReviewerSlot.A
            )
            return ReviewerCJudgment(
                verdict=f"select_{selected.value.lower()}",
                selected_slot=selected.value,
                summary=(
                    f"Reviewer C selected Reviewer {selected.value}'s complete "
                    "cross-review assessment after classifying every submitted claim."
                ),
                confidence=0.8,
                evidence_quality="adequate",
                supporting_claim_ids=response_ids.get(selected, ()),
                rejected_claim_ids=response_ids.get(rejected, ()),
                unresolved_claim_ids=own_ids,
            )
        if self.case.scenario == "c_synthesize":
            return ReviewerCJudgment(
                verdict="synthesize",
                summary=(
                    "Reviewer C synthesized a bounded experiment after neither "
                    "cross-review assessment fully resolved the submitted evidence."
                ),
                resolution_assessment=self._assessment("experiment", call),
                confidence=0.76,
                evidence_quality="adequate",
                supporting_claim_ids=all_ids,
            )
        if self.case.scenario == "c_insufficient":
            return ReviewerCJudgment(
                verdict="insufficient_evidence",
                summary=(
                    "Reviewer C found the submitted evidence insufficient for "
                    "either operational recommendation."
                ),
                resolution_assessment=self._assessment("collect", call),
                confidence=0.72,
                evidence_quality="adequate",
                unresolved_claim_ids=all_ids,
            )
        raise ValueError(f"scenario {self.case.scenario!r} has no judgment")

    def _fault_applies(self, call: ReviewCall) -> bool:
        return {
            "none": False,
            "timeout_a": (
                call.slot == ReviewerSlot.A
                and call.stage == ReviewStage.INDEPENDENT
            ),
            "timeout_b": (
                call.slot == ReviewerSlot.B
                and call.stage == ReviewStage.INDEPENDENT
            ),
            "timeout_cross": (
                call.slot == ReviewerSlot.A
                and call.stage == ReviewStage.CROSS_REVIEW
            ),
            "malformed_a": (
                call.slot == ReviewerSlot.A
                and call.stage == ReviewStage.INDEPENDENT
            ),
            "malformed_cross": (
                call.slot == ReviewerSlot.A
                and call.stage == ReviewStage.CROSS_REVIEW
            ),
            "cross_failure_once": (
                call.slot == ReviewerSlot.A
                and call.stage == ReviewStage.CROSS_REVIEW
            ),
        }[self.case.fault]

    def _attempt_start(self, call: ReviewCall, attempt_number: int) -> datetime:
        case_offset = int(self.case.case_id[-3:]) * 60
        stage_offset = {
            ReviewStage.INDEPENDENT: 0,
            ReviewStage.CROSS_REVIEW: 10,
            ReviewStage.JUDGING: 20,
        }[call.stage]
        slot_offset = {
            ReviewerSlot.A: 1,
            ReviewerSlot.B: 2,
            ReviewerSlot.C: 3,
        }[call.slot]
        return _PILOT_CLOCK + timedelta(
            seconds=case_offset + stage_offset + slot_offset + attempt_number
        )

    @staticmethod
    def _latency(call: ReviewCall) -> int:
        return {
            (ReviewerSlot.A, ReviewStage.INDEPENDENT): 120,
            (ReviewerSlot.B, ReviewStage.INDEPENDENT): 145,
            (ReviewerSlot.A, ReviewStage.CROSS_REVIEW): 175,
            (ReviewerSlot.B, ReviewStage.CROSS_REVIEW): 185,
            (ReviewerSlot.C, ReviewStage.INDEPENDENT): 155,
            (ReviewerSlot.C, ReviewStage.JUDGING): 205,
        }[(call.slot, call.stage)]

    def _succeeded_attempt(
        self,
        call: ReviewCall,
        *,
        attempt_number: int | None = None,
    ) -> ProviderAttempt:
        attempt_number = attempt_number or call.attempt_number
        latency = self._latency(call)
        started = self._attempt_start(call, attempt_number)
        input_tokens = 110 + latency // 10
        output_tokens = 48 + call.round * 2
        total_tokens = input_tokens + output_tokens
        return ProviderAttempt(
            attempt_number=attempt_number,
            status="succeeded",
            started_at=started,
            completed_at=started + timedelta(milliseconds=latency),
            latency_ms=latency,
            provider_request_id=(
                f"synthetic-request-{self.case.case_id}-{call.slot.value}-"
                f"{call.stage.value}-{attempt_number}"
            ),
            provider_response_id=(
                f"synthetic-response-{self.case.case_id}-{call.slot.value}-"
                f"{call.stage.value}-{attempt_number}"
            ),
            finish_status="completed",
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=round(total_tokens * 0.0000012, 8),
                pricing_version="synthetic-phase7-v1",
            ),
        )

    def _failed_attempt(
        self,
        call: ReviewCall,
        *,
        status: str,
        error_type: str,
    ) -> ProviderAttempt:
        latency = 90
        started = self._attempt_start(call, call.attempt_number)
        return ProviderAttempt(
            attempt_number=call.attempt_number,
            status=status,
            started_at=started,
            completed_at=started + timedelta(milliseconds=latency),
            latency_ms=latency,
            error_type=error_type,
            error_message="synthetic pilot failure",
        )
