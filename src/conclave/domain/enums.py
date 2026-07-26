from enum import StrEnum


class ReviewerSlot(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class ReviewerType(StrEnum):
    MODEL = "model"
    DETERMINISTIC_CHECKER = "deterministic_checker"
    HUMAN = "human"


class ReviewStage(StrEnum):
    INDEPENDENT = "independent"
    CROSS_REVIEW = "cross_review"
    JUDGING = "judging"


class ReviewState(StrEnum):
    REQUESTED = "requested"
    VALIDATED = "validated"
    SNAPSHOTTED = "snapshotted"
    REVIEWER_A = "reviewer_a"
    BASELINE_RECORDED = "baseline_recorded"
    REVIEWER_B = "reviewer_b"
    COMPARING = "comparing"
    CROSS_REVIEW = "cross_review"
    REVIEWER_C_INDEPENDENT = "reviewer_c_independent"
    REVIEWER_C_JUDGING = "reviewer_c_judging"
    REVIEWER_ADJUDICATION = "reviewer_adjudication"
    AUTO_RESOLVED = "auto_resolved"
    CALLER_DECISION_REQUIRED = "caller_decision_required"
    RESULT_RETURNED = "result_returned"
    FEEDBACK_PENDING = "feedback_pending"
    EVALUATED = "evaluated"
    INVALID_REQUEST = "invalid_request"
    STALE_OR_INELIGIBLE_EVIDENCE = "stale_or_ineligible_evidence"
    REVIEWER_A_FAILED = "reviewer_a_failed"
    REVIEWER_B_FAILED = "reviewer_b_failed"
    REVIEWER_C_FAILED = "reviewer_c_failed"
    AWAITING_EVIDENCE = "awaiting_evidence"
    RESULT_DELIVERY_FAILED = "result_delivery_failed"
    CANCELLED = "cancelled"


class TriggerKind(StrEnum):
    SCHEDULED_A = "scheduled_a"
    SCHEDULED_B = "scheduled_b"
    FAILED_GOAL = "failed_goal"
    MANUAL = "manual"


class RecommendationCategory(StrEnum):
    OBSERVE = "observe"
    COLLECT_MORE_DATA = "collect_more_data"
    EXPERIMENT = "experiment"
    OPERATIONAL_CHANGE = "operational_change"
    TRACKING_OR_DATA_PROBLEM = "tracking_or_data_problem"
    FREEZE = "freeze"


class ResultStatus(StrEnum):
    AUTO_RESOLVED = "auto_resolved"
    CALLER_DECISION_REQUIRED = "caller_decision_required"
    STALE_OR_INELIGIBLE_EVIDENCE = "stale_or_ineligible_evidence"
    FAILED = "failed"
