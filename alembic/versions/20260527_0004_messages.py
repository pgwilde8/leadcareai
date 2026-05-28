"""messages table

Revision ID: 20260527_0004
Revises: 20260527_0003
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0004"
down_revision: Union[str, None] = "20260527_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("from_phone", sa.String(length=50), nullable=True),
        sa.Column("to_phone", sa.String(length=50), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("provider_sid", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="recorded"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_business_id"), "messages", ["business_id"], unique=False)
    op.create_index(op.f("ix_messages_lead_id"), "messages", ["lead_id"], unique=False)
    op.create_index(op.f("ix_messages_provider_sid"), "messages", ["provider_sid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_provider_sid"), table_name="messages")
    op.drop_index(op.f("ix_messages_lead_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_business_id"), table_name="messages")
    op.drop_table("messages")
