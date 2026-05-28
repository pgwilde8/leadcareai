"""Unique phone_numbers.phone_number for Twilio routing

Revision ID: 20260527_0006
Revises: 20260527_0005
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260527_0006"
down_revision: Union[str, None] = "20260527_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_phone_numbers_phone_number"), table_name="phone_numbers")
    op.create_index(
        op.f("ix_phone_numbers_phone_number"),
        "phone_numbers",
        ["phone_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_phone_numbers_phone_number"), table_name="phone_numbers")
    op.create_index(
        op.f("ix_phone_numbers_phone_number"),
        "phone_numbers",
        ["phone_number"],
        unique=False,
    )
