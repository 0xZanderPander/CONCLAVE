"""Add immutable directional reviewer-evaluation candidates.

Revision ID: 20260728_0011
Revises: 20260728_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0011"
down_revision: str | None = "20260728_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reviewer_evaluation_candidates",
        sa.Column("candidate_id", sa.String(length=160), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=160),
            sa.ForeignKey("review_sessions.session_id"),
            nullable=False,
        ),
        sa.Column("contract_version", sa.String(length=80), nullable=False),
        sa.Column("candidate_hash", sa.String(length=71), nullable=False),
        sa.Column("result_hash", sa.String(length=71), nullable=False),
        sa.Column("feedback_hash", sa.String(length=71), nullable=False),
        sa.Column("route", sa.String(length=40), nullable=False),
        sa.Column("panel_changed", sa.Boolean(), nullable=False),
        sa.Column("category_changed", sa.Boolean(), nullable=False),
        sa.Column("caller_preference", sa.String(length=40), nullable=False),
        sa.Column("additional_issue_count", sa.Integer(), nullable=False),
        sa.Column("cross_review_invoked", sa.Boolean(), nullable=False),
        sa.Column("cross_review_resolved", sa.Boolean(), nullable=False),
        sa.Column("reviewer_c_invoked", sa.Boolean(), nullable=False),
        sa.Column("caller_override", sa.Boolean(), nullable=False),
        sa.Column("total_latency_ms", sa.Integer(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(18, 8), nullable=False),
        sa.Column("outcome_classification", sa.String(length=40), nullable=False),
        sa.Column("outcome_evidence_quality", sa.String(length=40)),
        sa.Column("confounder_count", sa.Integer(), nullable=False),
        sa.Column(
            "document",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            name="uq_reviewer_evaluation_candidate_session",
        ),
        sa.CheckConstraint(
            "additional_issue_count >= 0",
            name="ck_reviewer_evaluation_additional_issue_count",
        ),
        sa.CheckConstraint(
            "total_latency_ms >= 0",
            name="ck_reviewer_evaluation_total_latency",
        ),
        sa.CheckConstraint(
            "total_cost_usd >= 0",
            name="ck_reviewer_evaluation_total_cost",
        ),
        sa.CheckConstraint(
            "confounder_count >= 0",
            name="ck_reviewer_evaluation_confounder_count",
        ),
        sa.CheckConstraint(
            "route in ('a_only', 'ab_agreement', "
            "'cross_review_resolved', 'c_tie_broken')",
            name="ck_reviewer_evaluation_route",
        ),
    )
    op.create_index(
        "ix_reviewer_evaluation_candidates_candidate_hash",
        "reviewer_evaluation_candidates",
        ["candidate_hash"],
    )
    op.create_index(
        "ix_reviewer_evaluation_candidates_route_created",
        "reviewer_evaluation_candidates",
        ["route", "created_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                'ALTER TABLE public."reviewer_evaluation_candidates" '
                "ENABLE ROW LEVEL SECURITY"
            )
        )
        op.execute(
            sa.text(
                "REVOKE ALL PRIVILEGES ON TABLE "
                'public."reviewer_evaluation_candidates" '
                "FROM anon, authenticated, service_role"
            )
        )


def downgrade() -> None:
    op.drop_index(
        "ix_reviewer_evaluation_candidates_route_created",
        table_name="reviewer_evaluation_candidates",
    )
    op.drop_index(
        "ix_reviewer_evaluation_candidates_candidate_hash",
        table_name="reviewer_evaluation_candidates",
    )
    op.drop_table("reviewer_evaluation_candidates")
