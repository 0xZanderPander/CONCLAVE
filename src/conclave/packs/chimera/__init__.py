"""Chimera — Conclave configured for marketing ad-performance review.

Attributes resolve lazily so ``conclave.domain.enums`` can re-export the pack
vocabulary without an import cycle.
"""

from typing import Any

TASK_PACK_REF = "marketing-ads/v1"

__all__ = ["TASK_PACK_REF", "ChimeraPack", "chimera_pack"]


def __getattr__(name: str) -> Any:
    if name in {"ChimeraPack", "chimera_pack"}:
        from conclave.packs.chimera import pack as _pack

        return getattr(_pack, name)
    raise AttributeError(name)
