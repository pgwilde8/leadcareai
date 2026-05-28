"""business settings columns

Revision ID: 20260527_0011
Revises: 20260527_0010
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0011"
down_revision: Union[str, None] = "20260527_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("contact_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("notification_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("notification_phone", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("missed_call_textback_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("sms_signature", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("lead_intake_prompt", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("businesses", "lead_intake_prompt")
    op.drop_column("businesses", "sms_signature")
    op.drop_column("businesses", "missed_call_textback_message")
    op.drop_column("businesses", "notification_phone")
    op.drop_column("businesses", "notification_email")
    op.drop_column("businesses", "contact_email")
