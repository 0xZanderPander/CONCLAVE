"""Promote audit events into a typed domain-event outbox.

Revision ID: 20260726_0007
Revises: 20260726_0006
"""

import hashlib
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0007"
down_revision: str | None = "20260726_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _event_id(
    stream_type: str,
    stream_id: str,
    sequence: int,
    event_type: str,
) -> str:
    encoded = f"{stream_type}|{stream_id}|{sequence}|{event_type}".encode()
    return f"evt_{hashlib.sha256(encoded).hexdigest()[:24]}"


def _timestamp(value: object) -> object:
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def upgrade() -> None:
    op.create_table(
        "event_streams",
        sa.Column("stream_type", sa.String(length=80), primary_key=True),
        sa.Column("stream_id", sa.String(length=160), primary_key=True),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("event_id", sa.String(length=160)))
        batch.add_column(sa.Column("session_id", sa.String(length=160)))
        batch.add_column(sa.Column("actor_type", sa.String(length=40)))
        batch.add_column(sa.Column("actor_id", sa.String(length=160)))
        batch.add_column(sa.Column("stage", sa.String(length=40)))
        batch.add_column(sa.Column("round", sa.Integer()))
        batch.add_column(sa.Column("summary", sa.String(length=500)))
        batch.add_column(sa.Column("evidence_refs", sa.JSON()))
        batch.add_column(sa.Column("confidence", sa.Float()))
        batch.add_column(sa.Column("correlation_id", sa.String(length=160)))
        batch.add_column(sa.Column("causation_id", sa.String(length=160)))
        batch.add_column(
            sa.Column(
                "schema_version",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )

    connection = op.get_bind()
    rows = list(
        connection.execute(
            sa.text(
                "select audit_event_id, entity_type, entity_id, event_index, "
                "event_type, occurred_at from audit_events "
                "order by entity_type, entity_id, event_index"
            )
        ).mappings()
    )
    last_event_by_stream: dict[tuple[str, str], str] = {}
    stream_state: dict[tuple[str, str], tuple[int, object, object]] = {}
    for row in rows:
        stream_key = (row["entity_type"], row["entity_id"])
        public_id = _event_id(
            row["entity_type"],
            row["entity_id"],
            row["event_index"],
            row["event_type"],
        )
        summary = f"{row['event_type'].replace('_', ' ').capitalize()}."
        connection.execute(
            sa.text(
                "update audit_events set event_id = :event_id, "
                "session_id = :session_id, summary = :summary, "
                "evidence_refs = :evidence_refs, correlation_id = :correlation_id, "
                "causation_id = :causation_id where audit_event_id = :row_id"
            ),
            {
                "event_id": public_id,
                "session_id": (
                    row["entity_id"] if row["entity_type"] == "review_session" else None
                ),
                "summary": summary,
                "evidence_refs": "[]",
                "correlation_id": row["entity_id"],
                "causation_id": last_event_by_stream.get(stream_key),
                "row_id": row["audit_event_id"],
            },
        )
        last_event_by_stream[stream_key] = public_id
        existing = stream_state.get(stream_key)
        occurred_at = _timestamp(row["occurred_at"])
        created_at = occurred_at if existing is None else existing[1]
        stream_state[stream_key] = (
            row["event_index"],
            created_at,
            occurred_at,
        )

    if stream_state:
        event_streams = sa.table(
            "event_streams",
            sa.column("stream_type", sa.String()),
            sa.column("stream_id", sa.String()),
            sa.column("last_sequence", sa.Integer()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            event_streams,
            [
                {
                    "stream_type": stream_type,
                    "stream_id": stream_id,
                    "last_sequence": state[0],
                    "created_at": state[1],
                    "updated_at": state[2],
                }
                for (stream_type, stream_id), state in stream_state.items()
            ],
        )

    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("event_id", existing_type=sa.String(length=160), nullable=False)
        batch.alter_column("summary", existing_type=sa.String(length=500), nullable=False)
        batch.alter_column("evidence_refs", existing_type=sa.JSON(), nullable=False)
        batch.alter_column(
            "correlation_id",
            existing_type=sa.String(length=160),
            nullable=False,
        )
        batch.create_unique_constraint("uq_audit_event_public_id", ["event_id"])
        batch.create_index(
            "ix_audit_events_type_occurred",
            ["event_type", "occurred_at"],
        )
    if connection.dialect.name == "postgresql":
        op.alter_column("audit_events", "schema_version", server_default=None)

    op.create_table(
        "event_subscriptions",
        sa.Column("subscriber_id", sa.String(length=160), primary_key=True),
        sa.Column("stream_type", sa.String(length=80)),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "event_deliveries",
        sa.Column(
            "subscriber_id",
            sa.String(length=160),
            sa.ForeignKey("event_subscriptions.subscriber_id"),
            primary_key=True,
        ),
        sa.Column(
            "event_id",
            sa.String(length=160),
            sa.ForeignKey("audit_events.event_id"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_by", sa.String(length=160)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(length=1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_event_deliveries_claimable",
        "event_deliveries",
        ["subscriber_id", "status", "available_at", "lease_expires_at"],
    )
    op.create_index(
        "ix_event_deliveries_event_id",
        "event_deliveries",
        ["event_id"],
    )

    if connection.dialect.name == "postgresql":
        for table_name in (
            "event_streams",
            "event_subscriptions",
            "event_deliveries",
        ):
            op.execute(sa.text(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f'REVOKE ALL PRIVILEGES ON TABLE public."{table_name}" '
                    "FROM anon, authenticated, service_role"
                )
            )


def downgrade() -> None:
    op.drop_index("ix_event_deliveries_event_id", table_name="event_deliveries")
    op.drop_index("ix_event_deliveries_claimable", table_name="event_deliveries")
    op.drop_table("event_deliveries")
    op.drop_table("event_subscriptions")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_index("ix_audit_events_type_occurred")
        batch.drop_constraint("uq_audit_event_public_id", type_="unique")
        batch.drop_column("schema_version")
        batch.drop_column("causation_id")
        batch.drop_column("correlation_id")
        batch.drop_column("confidence")
        batch.drop_column("evidence_refs")
        batch.drop_column("summary")
        batch.drop_column("round")
        batch.drop_column("stage")
        batch.drop_column("actor_id")
        batch.drop_column("actor_type")
        batch.drop_column("session_id")
        batch.drop_column("event_id")
    op.drop_table("event_streams")
