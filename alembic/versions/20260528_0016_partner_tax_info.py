"""partner_tax_info table

Revision ID: 20260528_0016
Revises: 20260528_0015
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0016"
down_revision: Union[str, None] = "20260528_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partner_tax_info",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("business_name", sa.String(length=255), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("tax_classification", sa.String(length=80), nullable=False),
        sa.Column("tin_type", sa.String(length=10), nullable=False),
        sa.Column("tin_encrypted", sa.Text(), nullable=False),
        sa.Column("certified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["partner_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_partner_tax_info_application_id"),
        "partner_tax_info",
        ["application_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_tax_info_application_id"), table_name="partner_tax_info")
    op.drop_table("partner_tax_info")
