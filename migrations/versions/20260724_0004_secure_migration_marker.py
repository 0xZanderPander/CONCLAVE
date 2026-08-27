"""Keep Alembic's migration marker private on Supabase.

Revision ID: 20260724_0004
Revises: 20260724_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0004"
down_revision: str | None = "20260724_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(sa.text("ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "REVOKE ALL PRIVILEGES ON TABLE public.alembic_version "
            "FROM anon, authenticated, service_role"
        )
    )


def downgrade() -> None:
    # Access is intentionally not reopened by a rollback.
    pass
