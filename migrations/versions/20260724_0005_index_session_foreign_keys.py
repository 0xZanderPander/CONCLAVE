"""Index review-session foreign keys used by ledger lookups.

Revision ID: 20260724_0005
Revises: 20260724_0004
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260724_0005"
down_revision: str | None = "20260724_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_review_sessions_occurrence_id",
        "review_sessions",
        ["occurrence_id"],
    )
    op.create_index(
        "ix_review_sessions_plan_revision",
        "review_sessions",
        ["plan_id", "plan_revision"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_review_sessions_plan_revision",
        table_name="review_sessions",
    )
    op.drop_index(
        "ix_review_sessions_occurrence_id",
        table_name="review_sessions",
    )
