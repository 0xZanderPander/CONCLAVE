"""Create the Phase 1A review ledger.

Revision ID: 20260724_0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_plans",
        sa.Column("plan_id", sa.String(length=160), primary_key=True),
        sa.Column("deployment_id", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "review_plan_revisions",
        sa.Column("revision_id", sa.String(length=200), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(length=160),
            sa.ForeignKey("review_plans.plan_id"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=71), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_id", "revision", name="uq_review_plan_revision"),
    )
    op.create_index(
        "ix_review_plan_revisions_plan_id",
        "review_plan_revisions",
        ["plan_id"],
    )
    op.create_table(
        "reviewer_slots",
        sa.Column("reviewer_slot_id", sa.String(length=220), primary_key=True),
        sa.Column("plan_id", sa.String(length=160), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(length=1), nullable=False),
        sa.Column("reviewer_type", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=100)),
        sa.Column("model", sa.String(length=160)),
        sa.Column("role_version", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["review_plan_revisions.plan_id", "review_plan_revisions.revision"],
        ),
        sa.UniqueConstraint(
            "plan_id",
            "plan_revision",
            "slot",
            name="uq_reviewer_slot_revision",
        ),
    )
    op.create_table(
        "review_occurrences",
        sa.Column("occurrence_id", sa.String(length=160), primary_key=True),
        sa.Column("plan_id", sa.String(length=160), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger_kind", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["review_plan_revisions.plan_id", "review_plan_revisions.revision"],
        ),
        sa.UniqueConstraint(
            "plan_id",
            "plan_revision",
            "due_at",
            "trigger_kind",
            name="uq_review_occurrence_schedule",
        ),
    )
    op.create_table(
        "review_sessions",
        sa.Column("session_id", sa.String(length=160), primary_key=True),
        sa.Column("caller_id", sa.String(length=160), nullable=False),
        sa.Column(
            "occurrence_id",
            sa.String(length=160),
            sa.ForeignKey("review_occurrences.occurrence_id"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("evidence_version", sa.String(length=200), nullable=False),
        sa.Column("plan_id", sa.String(length=160), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("current_state", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["review_plan_revisions.plan_id", "review_plan_revisions.revision"],
        ),
        sa.UniqueConstraint(
            "caller_id",
            "occurrence_id",
            "evidence_version",
            "plan_revision",
            name="uq_review_session_identity",
        ),
    )
    op.create_table(
        "request_snapshots",
        sa.Column("snapshot_id", sa.String(length=160), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=160),
            sa.ForeignKey("review_sessions.session_id"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=71), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_request_snapshot_session"),
    )
    op.create_index(
        "ix_request_snapshots_content_hash",
        "request_snapshots",
        ["content_hash"],
    )
    op.create_table(
        "reviewer_invocations",
        sa.Column("invocation_id", sa.String(length=160), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=160),
            sa.ForeignKey("review_sessions.session_id"),
            nullable=False,
        ),
        sa.Column("reviewer_slot", sa.String(length=1), nullable=False),
        sa.Column("reviewer_type", sa.String(length=40), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=71), nullable=False),
        sa.Column("provider", sa.String(length=100)),
        sa.Column("model", sa.String(length=160)),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "reviewer_slot",
            "stage",
            "round",
            name="uq_reviewer_invocation_stage",
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("audit_event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "event_index",
            name="uq_audit_entity_event_index",
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("reviewer_invocations")
    op.drop_index(
        "ix_request_snapshots_content_hash",
        table_name="request_snapshots",
    )
    op.drop_table("request_snapshots")
    op.drop_table("review_sessions")
    op.drop_table("review_occurrences")
    op.drop_table("reviewer_slots")
    op.drop_index(
        "ix_review_plan_revisions_plan_id",
        table_name="review_plan_revisions",
    )
    op.drop_table("review_plan_revisions")
    op.drop_table("review_plans")
