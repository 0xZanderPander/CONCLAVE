import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from conclave.events.models import DomainEvent
from conclave.ledger.repository import LedgerRepository

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    """Extension point implemented by a future transport adapter."""

    def publish(self, event: DomainEvent) -> None:
        """Handle one committed event. Implementations must deduplicate by event_id."""


class NoOpEventPublisher:
    def publish(self, event: DomainEvent) -> None:
        del event


class LoggingEventPublisher:
    def publish(self, event: DomainEvent) -> None:
        logger.info(
            event.summary,
            extra={
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "stream_id": event.stream_id,
                "sequence": event.sequence,
            },
        )


class InMemoryEventPublisher:
    """Deterministic duplicate-safe publisher for tests and local projections."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []
        self._seen_event_ids: set[str] = set()

    def publish(self, event: DomainEvent) -> None:
        if event.event_id in self._seen_event_ids:
            return
        self._seen_event_ids.add(event.event_id)
        self.events.append(event)


@dataclass(frozen=True, slots=True)
class DispatchResult:
    subscriber_id: str
    event_id: str | None
    status: str
    error: str | None = None


class EventDispatcher:
    """Reads committed events and updates delivery state after publishing."""

    def __init__(
        self,
        repository: LedgerRepository,
        publishers: dict[str, EventPublisher],
    ) -> None:
        self._repository = repository
        self._publishers = dict(publishers)

    def dispatch_once(
        self,
        *,
        subscriber_id: str,
        worker_id: str,
        now: datetime,
        lease_seconds: int = 60,
        retry_delay_seconds: int = 30,
    ) -> DispatchResult:
        try:
            publisher = self._publishers[subscriber_id]
        except KeyError as exc:
            raise LookupError(f"no publisher registered for {subscriber_id!r}") from exc

        claimed = self._repository.claim_next_event_delivery(
            subscriber_id=subscriber_id,
            worker_id=worker_id,
            now=now,
            lease_seconds=lease_seconds,
        )
        if claimed is None:
            return DispatchResult(
                subscriber_id=subscriber_id,
                event_id=None,
                status="empty",
            )
        event, _delivery = claimed
        try:
            publisher.publish(event)
        except Exception as exc:
            self._repository.fail_event_delivery(
                subscriber_id=subscriber_id,
                event_id=event.event_id,
                worker_id=worker_id,
                now=now,
                error=str(exc),
                retry_delay_seconds=retry_delay_seconds,
            )
            return DispatchResult(
                subscriber_id=subscriber_id,
                event_id=event.event_id,
                status="retry",
                error=str(exc),
            )

        self._repository.complete_event_delivery(
            subscriber_id=subscriber_id,
            event_id=event.event_id,
            worker_id=worker_id,
            now=now,
        )
        return DispatchResult(
            subscriber_id=subscriber_id,
            event_id=event.event_id,
            status="delivered",
        )
