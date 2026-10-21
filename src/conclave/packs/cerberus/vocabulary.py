"""Cerberus's verdict vocabulary.

Four verdicts, ordered from most to least cautious. When two seats agree within
tolerance the merged verdict is the more cautious of the two.
"""

from enum import StrEnum


class VentureVerdict(StrEnum):
    NOT_VIABLE = "not_viable"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    NEEDS_REVISION = "needs_revision"
    VIABLE = "viable"


CAUTION_ORDER: dict[VentureVerdict, int] = {
    VentureVerdict.NOT_VIABLE: 0,
    VentureVerdict.INSUFFICIENT_INFORMATION: 1,
    VentureVerdict.NEEDS_REVISION: 2,
    VentureVerdict.VIABLE: 3,
}

SCORE_DIMENSIONS: tuple[str, ...] = (
    "problem_clarity",
    "market_opportunity",
    "differentiation",
    "feasibility",
    "team_capability",
    "risk_exposure",
)
"""Rubric dimensions scored 1-5. ``risk_exposure`` is inverted: 5 is most risk."""
