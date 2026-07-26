# Conclave Domain Event Stream

## Purpose

Conclave has one canonical, append-only event history. The existing
`audit_events` ledger is also the durable event stream and outbox for future
projections and transport adapters.

A completed Conclave operation writes its state change and event in the same
database transaction. A committed event remains valid even if a later
subscriber is unavailable.

Discord, Telegram, Slack, webhooks, and other presentation adapters are not
implemented. They may consume this same transport-neutral stream later.

## Stable Event Envelope

Every event exposed to a consumer has these stable contract fields:

```json
{
  "event_id": "evt_...",
  "stream_type": "review_session",
  "stream_id": "rs_...",
  "session_id": "rs_...",
  "sequence": 12,
  "occurred_at": "2026-07-26T12:00:00Z",
  "event_type": "reviewer_invocation_completed",
  "actor": {
    "type": "reviewer",
    "id": "B"
  },
  "stage": "cross_review",
  "round": 1,
  "summary": "Reviewer B submitted a cross-review assessment.",
  "evidence_refs": [],
  "confidence": 0.84,
  "payload": {},
  "correlation_id": "rs_...",
  "causation_id": "evt_...",
  "schema_version": 1
}
```

The stable public fields are:

- `event_id`: durable public identity used for deduplication
- `stream_type` and `stream_id`: event-stream identity
- `session_id`: review-session reference when applicable
- `sequence`: strictly increasing position within one stream
- `occurred_at`: domain occurrence time
- `event_type`: value from the central `DomainEventType` registry
- `actor`: typed actor and stable actor identifier when applicable
- `stage` and `round`: review lifecycle position when applicable
- `summary`: concise, safe text for light presentation
- `evidence_refs`: references only, never a copied evidence package
- `confidence`: reviewer confidence when supported by the operation
- `correlation_id`: groups related work
- `causation_id`: normally the preceding event in the stream
- `schema_version`: envelope contract version

`payload` is a small, event-specific projection. Its contents may evolve under
`schema_version`; consumers should ignore unknown payload fields. It must not
contain hidden chain-of-thought, full ORM records, credentials, full request
snapshots, or complete assessment bodies.

## Current Event Types

The central typed registry covers lifecycle operations that exist now:

- plan revision creation
- occurrence creation
- work-item enqueue, claim, completion, retry, dead letter, lease extension,
  manual retry, and cancellation
- review-session creation
- immutable snapshot storage
- reviewer invocation creation, completion, and failure
- state transition
- result creation
- runtime process start and stop

New event names are added only when the matching domain behavior exists.
External consumers should use `event_type` and structured metadata rather than
parsing summaries.

## Storage and Ordering

Migration `20260726_0007` evolves `audit_events`; it does not create a second
event history.

- `audit_events` stores immutable event envelopes.
- `event_streams` allocates the next per-stream sequence with one atomic
  database update.
- The existing unique stream-sequence constraint remains in place.
- Legacy audit rows receive stable event IDs, summaries, causation links, and
  stream sequence state during migration.

Two writers may append to different streams independently. Writers targeting
the same stream are serialized by the `event_streams` row, so sequence numbers
cannot silently collide.

## Delivery and Retry

`event_subscriptions` registers a named consumer and an optional stream-type
filter. `event_deliveries` stores that consumer's delivery state.

The dispatcher:

1. claims the earliest eligible event with a database lease;
2. commits the claim;
3. calls the subscriber outside the Conclave domain transaction;
4. marks success, or records an error and retry time.

Delivery is at least once. A subscriber may process an event and fail before
the success checkpoint is written, so every subscriber must deduplicate by
`event_id`.

Ordering is preserved within each stream. A failed earlier event blocks later
events from that same stream for the subscriber, but it does not corrupt the
review or roll back the committed event. Database row locking and
`SKIP LOCKED` allow multiple dispatcher workers to handle separate eligible
streams safely.

The durable `audit_events` ledger is the source of truth. Delivery rows can be
backfilled from it, so subscriber registration or dispatcher downtime cannot
lose a committed event.

## Reading Events

Repository API:

```python
repository.list_events(
    stream_id,
    stream_type="review_session",
    after_sequence=0,
    limit=100,
)
```

Read-only HTTP API:

```text
GET /review-sessions/{session_id}/events?after_sequence=0&limit=100
```

Results use stable sequence ordering. `after_sequence` is the polling cursor.
The endpoint returns structured envelopes and never transport-specific
rendering.

## Adding a Future Transport Adapter

A future adapter implements exactly this transport-neutral interface:

```python
class EventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...
```

The adapter is registered under a durable `subscriber_id` and run through
`EventDispatcher`. It must:

- deduplicate by `event.event_id`;
- render only safe envelope and payload fields;
- raise on retryable delivery failure;
- avoid changing Conclave review state;
- keep platform credentials and SDK imports outside Conclave domain and
  orchestration modules.

For Discord, the future implementation would translate `DomainEvent` into a
Discord message inside an adapter package. No Discord concept belongs in the
event models, ledger, review protocol, or orchestration service.
