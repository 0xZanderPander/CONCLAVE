"""Pin review sessions to immutable task-pack revisions.

Revision ID: 20260726_0008
Revises: 20260726_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0008"
down_revision: str | None = "20260726_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_pack_revisions",
        sa.Column("content_hash", sa.String(length=71), primary_key=True),
        sa.Column("task_pack_ref", sa.String(length=160), nullable=False),
        sa.Column(
            "document",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_pack_ref", name="uq_task_pack_revisions_ref"),
    )
    with op.batch_alter_table("review_sessions") as batch:
        batch.add_column(sa.Column("task_pack_hash", sa.String(length=71)))
        batch.create_foreign_key(
            "fk_review_sessions_task_pack_hash",
            "task_pack_revisions",
            ["task_pack_hash"],
            ["content_hash"],
        )
        batch.create_index(
            "ix_review_sessions_task_pack_hash",
            ["task_pack_hash"],
        )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                'ALTER TABLE public."task_pack_revisions" ENABLE ROW LEVEL SECURITY'
            )
        )
        op.execute(
            sa.text(
                'REVOKE ALL PRIVILEGES ON TABLE public."task_pack_revisions" '
                "FROM anon, authenticated, service_role"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("review_sessions") as batch:
        batch.drop_index("ix_review_sessions_task_pack_hash")
        batch.drop_constraint(
            "fk_review_sessions_task_pack_hash",
            type_="foreignkey",
        )
        batch.drop_column("task_pack_hash")
    op.drop_table("task_pack_revisions")
