"""Persist reviewer provider attempts and aggregate telemetry.

Revision ID: 20260727_0009
Revises: 20260726_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0009"
down_revision: str | None = "20260726_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reviewer_invocations") as batch:
        batch.add_column(
            sa.Column(
                "attempt_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(sa.Column("provider_request_id", sa.String(length=200)))
        batch.add_column(sa.Column("provider_response_id", sa.String(length=200)))
        batch.add_column(sa.Column("input_tokens", sa.Integer()))
        batch.add_column(sa.Column("cached_input_tokens", sa.Integer()))
        batch.add_column(sa.Column("output_tokens", sa.Integer()))
        batch.add_column(sa.Column("reasoning_tokens", sa.Integer()))
        batch.add_column(sa.Column("total_tokens", sa.Integer()))
        batch.add_column(sa.Column("latency_ms", sa.Integer()))
        batch.add_column(sa.Column("cost_usd", sa.Float()))
        batch.add_column(sa.Column("finish_status", sa.String(length=80)))
        batch.add_column(sa.Column("pricing_version", sa.String(length=100)))

    op.create_table(
        "reviewer_provider_attempts",
        sa.Column("attempt_id", sa.String(length=160), primary_key=True),
        sa.Column(
            "invocation_id",
            sa.String(length=160),
            sa.ForeignKey("reviewer_invocations.invocation_id"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("provider_request_id", sa.String(length=200)),
        sa.Column("provider_response_id", sa.String(length=200)),
        sa.Column("finish_status", sa.String(length=80)),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("pricing_version", sa.String(length=100)),
        sa.Column("error_type", sa.String(length=100)),
        sa.Column("error_message", sa.String(length=1000)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "invocation_id",
            "attempt_number",
            name="uq_reviewer_provider_attempt",
        ),
    )
    op.create_index(
        "ix_reviewer_provider_attempts_invocation_id",
        "reviewer_provider_attempts",
        ["invocation_id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                'ALTER TABLE public."reviewer_provider_attempts" '
                "ENABLE ROW LEVEL SECURITY"
            )
        )
        op.execute(
            sa.text(
                'REVOKE ALL PRIVILEGES ON TABLE public."reviewer_provider_attempts" '
                "FROM anon, authenticated, service_role"
            )
        )


def downgrade() -> None:
    op.drop_index(
        "ix_reviewer_provider_attempts_invocation_id",
        table_name="reviewer_provider_attempts",
    )
    op.drop_table("reviewer_provider_attempts")
    with op.batch_alter_table("reviewer_invocations") as batch:
        batch.drop_column("pricing_version")
        batch.drop_column("finish_status")
        batch.drop_column("cost_usd")
        batch.drop_column("latency_ms")
        batch.drop_column("total_tokens")
        batch.drop_column("reasoning_tokens")
        batch.drop_column("output_tokens")
        batch.drop_column("cached_input_tokens")
        batch.drop_column("input_tokens")
        batch.drop_column("provider_response_id")
        batch.drop_column("provider_request_id")
        batch.drop_column("attempt_count")
