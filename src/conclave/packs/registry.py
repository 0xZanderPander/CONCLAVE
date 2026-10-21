"""Pack registry: resolves which pack a request, session or reviewer call belongs to."""

from collections.abc import Iterable
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from conclave.contracts.errors import ContractValidationError
from conclave.packs.base import ReviewPack

if TYPE_CHECKING:
    from conclave.reviewers.runtime import ReviewCall


class PackRegistry:
    def __init__(self, packs: Iterable[ReviewPack], *, default_pack_id: str | None = None) -> None:
        packs = tuple(packs)
        self._by_ref = {pack.task_pack_ref: pack for pack in packs}
        self._by_id = {pack.pack_id: pack for pack in packs}
        if len(self._by_ref) != len(packs) or len(self._by_id) != len(packs):
            raise ValueError("pack identifiers and task-pack references must be unique")
        if default_pack_id is not None and default_pack_id not in self._by_id:
            raise ValueError(f"unknown default pack {default_pack_id!r}")
        self._default_pack_id = default_pack_id

    def get(self, task_pack_ref: str) -> ReviewPack:
        try:
            return self._by_ref[task_pack_ref]
        except KeyError as exc:
            raise ContractValidationError(f"unknown task_pack_ref {task_pack_ref!r}") from exc

    def by_id(self, pack_id: str) -> ReviewPack:
        try:
            return self._by_id[pack_id]
        except KeyError as exc:
            raise LookupError(f"unknown pack {pack_id!r}") from exc

    def for_document(self, document: dict[str, Any]) -> ReviewPack:
        task_pack_ref = document.get("task_pack_ref")
        if not isinstance(task_pack_ref, str):
            raise ContractValidationError("request is missing task_pack_ref")
        return self.get(task_pack_ref)

    def for_call(self, call: "ReviewCall") -> ReviewPack:
        """Resolve the pack for a reviewer call.

        The orchestrator stamps ``task_pack_ref`` on every call. Legacy
        callers that build calls by hand fall back to the snapshot, then to the
        registry's declared default pack.
        """

        if call.task_pack_ref is not None:
            return self.get(call.task_pack_ref)
        snapshot_ref = call.snapshot.get("task_pack_ref")
        if isinstance(snapshot_ref, str):
            return self.get(snapshot_ref)
        if self._default_pack_id is None:
            raise LookupError("reviewer call does not identify its pack")
        return self._by_id[self._default_pack_id]

    @property
    def packs(self) -> tuple[ReviewPack, ...]:
        return tuple(self._by_ref.values())


@lru_cache(maxsize=1)
def default_pack_registry() -> PackRegistry:
    from conclave.packs.chimera import chimera_pack

    return PackRegistry((chimera_pack(),), default_pack_id="chimera")
