"""initial users and businesses tables

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="business_user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "businesses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("main_phone", sa.String(length=50), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="America/New_York",
        ),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_businesses_stripe_customer_id"),
        "businesses",
        ["stripe_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_businesses_stripe_subscription_id"),
        "businesses",
        ["stripe_subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_businesses_stripe_subscription_id"), table_name="businesses")
    op.drop_index(op.f("ix_businesses_stripe_customer_id"), table_name="businesses")
    op.drop_table("businesses")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
