"""Keep the Conclave ledger private on Supabase.

Revision ID: 20260724_0003
Revises: 20260724_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0003"
down_revision: str | None = "20260724_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEDGER_TABLES = (
    "review_plans",
    "review_plan_revisions",
    "reviewer_slots",
    "review_occurrences",
    "review_sessions",
    "request_snapshots",
    "reviewer_invocations",
    "audit_events",
    "scheduler_work_items",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table_name in LEDGER_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table_name}" ENABLE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                f'REVOKE ALL PRIVILEGES ON TABLE public."{table_name}" '
                "FROM anon, authenticated, service_role"
            )
        )

    op.execute(
        sa.text(
            "REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public "
            "FROM anon, authenticated, service_role"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
            "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES "
            "FROM anon, authenticated, service_role"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
            "REVOKE USAGE, SELECT ON SEQUENCES FROM anon, authenticated, service_role"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
            "REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated, service_role"
        )
    )
    op.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
            "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
        )
    )


def downgrade() -> None:
    # Access is intentionally not reopened by a rollback.
    pass
