"""Add immutable Phase 6 caller feedback storage.

Revision ID: 20260728_0010
Revises: 20260727_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0010"
down_revision: str | None = "20260727_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_feedback_records",
        sa.Column("feedback_id", sa.String(length=160), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=160),
            sa.ForeignKey("review_sessions.session_id"),
            nullable=False,
        ),
        sa.Column("contract_version", sa.String(length=60), nullable=False),
        sa.Column("evidence_version", sa.String(length=200), nullable=False),
        sa.Column("feedback_hash", sa.String(length=71), nullable=False),
        sa.Column("decision_ref", sa.String(length=200), nullable=False),
        sa.Column("decision_disposition", sa.String(length=40), nullable=False),
        sa.Column("relationship_to_panel", sa.String(length=40), nullable=False),
        sa.Column("panel_preference", sa.String(length=40), nullable=False),
        sa.Column("action_ref", sa.String(length=200)),
        sa.Column("outcome_ref", sa.String(length=200)),
        sa.Column("outcome_classification", sa.String(length=40), nullable=False),
        sa.Column("action_executed", sa.Boolean(), nullable=False),
        sa.Column(
            "confounders",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("outcome_evidence_quality", sa.String(length=40)),
        sa.Column("outcome_evaluated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "document",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            name="uq_review_feedback_session",
        ),
    )
    op.create_index(
        "ix_review_feedback_records_session_id",
        "review_feedback_records",
        ["session_id"],
    )
    op.create_index(
        "ix_review_feedback_records_feedback_hash",
        "review_feedback_records",
        ["feedback_hash"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                'ALTER TABLE public."review_feedback_records" '
                "ENABLE ROW LEVEL SECURITY"
            )
        )
        op.execute(
            sa.text(
                'REVOKE ALL PRIVILEGES ON TABLE public."review_feedback_records" '
                "FROM anon, authenticated, service_role"
            )
        )


def downgrade() -> None:
    op.drop_index(
        "ix_review_feedback_records_feedback_hash",
        table_name="review_feedback_records",
    )
    op.drop_index(
        "ix_review_feedback_records_session_id",
        table_name="review_feedback_records",
    )
    op.drop_table("review_feedback_records")
