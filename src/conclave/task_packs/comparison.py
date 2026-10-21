"""Compatibility shim. The comparison envelope is engine-level in
``conclave.packs.comparison``; chimera's comparator lives in
``conclave.packs.chimera.comparison``."""

from conclave.packs.chimera.comparison import compare_assessments  # noqa: F401
from conclave.packs.comparison import (  # noqa: F401
    ComparisonResult,
    ComparisonRound,
    comparison_trigger_labels,
    ordered_unique,
)
