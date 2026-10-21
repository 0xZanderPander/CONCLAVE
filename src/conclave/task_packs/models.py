"""Compatibility shim. Chimera's task-pack configuration lives in
``conclave.packs.chimera.config``; the eligibility models are engine-level in
``conclave.packs.base``."""

from conclave.packs.base import RequestEligibility, RequestMateriality  # noqa: F401
from conclave.packs.chimera.config import (  # noqa: F401
    ComparatorDimension,
    ComparatorProfile,
    DimensionWeight,
    HardTrigger,
    TaskPack,
)
