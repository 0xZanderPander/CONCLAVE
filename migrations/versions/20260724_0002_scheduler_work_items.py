"""Add persistent scheduler work items.

Revision ID: 20260724_0002
Revises: 20260724_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0002"
down_revision: str | None = "20260724_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reviewer_invocations",
        sa.Column("assessment_payload", sa.JSON()),
    )
    op.add_column(
        "reviewer_invocations",
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "reviewer_invocations",
        sa.Column("last_error", sa.String(length=1000)),
    )
    op.create_table(
        "scheduler_work_items",
        sa.Column("work_item_id", sa.String(length=160), primary_key=True),
        sa.Column(
            "occurrence_id",
            sa.String(length=160),
            sa.ForeignKey("review_occurrences.occurrence_id"),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("claimed_by", sa.String(length=160)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(length=1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "occurrence_id",
            name="uq_scheduler_work_item_occurrence",
        ),
    )
    op.create_index(
        "ix_scheduler_work_items_due_at",
        "scheduler_work_items",
        ["due_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scheduler_work_items_due_at",
        table_name="scheduler_work_items",
    )
    op.drop_table("scheduler_work_items")
    op.drop_column("reviewer_invocations", "last_error")
    op.drop_column("reviewer_invocations", "completed_at")
    op.drop_column("reviewer_invocations", "assessment_payload")
