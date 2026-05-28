"""notification_logs table

Revision ID: 20260527_0012
Revises: 20260527_0011
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0012"
down_revision: Union[str, None] = "20260527_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("business_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("lead_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_sid", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_logs_business_id"),
        "notification_logs",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_logs_lead_id"),
        "notification_logs",
        ["lead_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_lead_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_business_id"), table_name="notification_logs")
    op.drop_table("notification_logs")
