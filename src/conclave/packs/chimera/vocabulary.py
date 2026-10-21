"""Chimera's recommendation vocabulary.

Re-exported from ``conclave.domain.enums`` for import compatibility; the
vocabulary itself belongs to the marketing pack, not the engine.
"""

from enum import StrEnum


class RecommendationCategory(StrEnum):
    OBSERVE = "observe"
    COLLECT_MORE_DATA = "collect_more_data"
    EXPERIMENT = "experiment"
    OPERATIONAL_CHANGE = "operational_change"
    TRACKING_OR_DATA_PROBLEM = "tracking_or_data_problem"
    FREEZE = "freeze"
