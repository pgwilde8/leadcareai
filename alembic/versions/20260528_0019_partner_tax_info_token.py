"""partner application tax info collection token

Revision ID: 20260528_0019
Revises: 20260528_0018
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0019"
down_revision: Union[str, None] = "20260528_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "partner_applications",
        sa.Column("tax_info_token_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "partner_applications",
        sa.Column("tax_info_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_partner_applications_tax_info_token_hash"),
        "partner_applications",
        ["tax_info_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_partner_applications_tax_info_token_hash"),
        table_name="partner_applications",
    )
    op.drop_column("partner_applications", "tax_info_token_expires_at")
    op.drop_column("partner_applications", "tax_info_token_hash")
