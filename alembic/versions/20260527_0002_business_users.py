"""business_users table

Revision ID: 20260527_0002
Revises: 20260527_0001
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0002"
down_revision: Union[str, None] = "20260527_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "user_id", name="uq_business_users_business_id_user_id"),
    )
    op.create_index(op.f("ix_business_users_business_id"), "business_users", ["business_id"], unique=False)
    op.create_index(op.f("ix_business_users_user_id"), "business_users", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_business_users_user_id"), table_name="business_users")
    op.drop_index(op.f("ix_business_users_business_id"), table_name="business_users")
    op.drop_table("business_users")
