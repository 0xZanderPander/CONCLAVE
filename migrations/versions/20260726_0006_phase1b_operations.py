"""Persist results, retries, and runtime process health.

Revision ID: 20260726_0006
Revises: 20260724_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0006"
down_revision: str | None = "20260724_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scheduler_work_items",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text("UPDATE scheduler_work_items SET available_at = due_at WHERE available_at IS NULL")
    )
    with op.batch_alter_table("scheduler_work_items") as batch:
        batch.alter_column(
            "available_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch.add_column(
            sa.Column(
                "max_attempts",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("3"),
            )
        )
        batch.add_column(sa.Column("dead_lettered_at", sa.DateTime(timezone=True)))
        batch.create_index(
            "ix_scheduler_work_items_claimable",
            ["status", "available_at", "due_at", "work_item_id"],
        )
        batch.create_index(
            "ix_scheduler_work_items_lease",
            ["status", "lease_expires_at"],
        )
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "scheduler_work_items",
            "max_attempts",
            server_default=None,
        )

    op.create_table(
        "review_results",
        sa.Column("result_id", sa.String(length=160), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=160),
            sa.ForeignKey("review_sessions.session_id"),
            nullable=False,
        ),
        sa.Column("path", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("contract_version", sa.String(length=60), nullable=False),
        sa.Column("result_hash", sa.String(length=71), nullable=False),
        sa.Column(
            "document",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_review_result_session"),
    )
    op.create_index(
        "ix_review_results_session_id",
        "review_results",
        ["session_id"],
    )
    op.create_index(
        "ix_review_results_result_hash",
        "review_results",
        ["result_hash"],
    )

    op.create_table(
        "runtime_processes",
        sa.Column("process_id", sa.String(length=160), primary_key=True),
        sa.Column("process_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column(
            "process_metadata",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_runtime_processes_status_heartbeat",
        "runtime_processes",
        ["status", "heartbeat_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        for table_name in ("review_results", "runtime_processes"):
            op.execute(sa.text(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f'REVOKE ALL PRIVILEGES ON TABLE public."{table_name}" '
                    "FROM anon, authenticated, service_role"
                )
            )


def downgrade() -> None:
    op.drop_index(
        "ix_runtime_processes_status_heartbeat",
        table_name="runtime_processes",
    )
    op.drop_table("runtime_processes")
    op.drop_index("ix_review_results_result_hash", table_name="review_results")
    op.drop_index("ix_review_results_session_id", table_name="review_results")
    op.drop_table("review_results")
    with op.batch_alter_table("scheduler_work_items") as batch:
        batch.drop_index("ix_scheduler_work_items_lease")
        batch.drop_index("ix_scheduler_work_items_claimable")
        batch.drop_column("dead_lettered_at")
        batch.drop_column("max_attempts")
        batch.drop_column("available_at")
