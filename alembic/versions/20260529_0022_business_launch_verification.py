"""Business live launch verification fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_0022"
down_revision = "20260529_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("launch_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("launch_verified_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("launch_verification_notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_businesses_launch_verified_by_user_id",
        "businesses",
        "users",
        ["launch_verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_businesses_launch_verified_by_user_id",
        "businesses",
        type_="foreignkey",
    )
    op.drop_column("businesses", "launch_verification_notes")
    op.drop_column("businesses", "launch_verified_by_user_id")
    op.drop_column("businesses", "launch_verified_at")
