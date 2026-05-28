"""phone_numbers and leads tables

Revision ID: 20260527_0003
Revises: 20260527_0002
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0003"
down_revision: Union[str, None] = "20260527_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "phone_numbers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("provider_sid", sa.String(length=255), nullable=True),
        sa.Column("forward_to_number", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_phone_numbers_business_id"), "phone_numbers", ["business_id"], unique=False)
    op.create_index(op.f("ix_phone_numbers_phone_number"), "phone_numbers", ["phone_number"], unique=False)
    op.create_index(op.f("ix_phone_numbers_provider_sid"), "phone_numbers", ["provider_sid"], unique=False)

    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("service_needed", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("urgency", sa.String(length=100), nullable=True),
        sa.Column("preferred_contact_time", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leads_business_id"), "leads", ["business_id"], unique=False)
    op.create_index(op.f("ix_leads_phone"), "leads", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leads_phone"), table_name="leads")
    op.drop_index(op.f("ix_leads_business_id"), table_name="leads")
    op.drop_table("leads")
    op.drop_index(op.f("ix_phone_numbers_provider_sid"), table_name="phone_numbers")
    op.drop_index(op.f("ix_phone_numbers_phone_number"), table_name="phone_numbers")
    op.drop_index(op.f("ix_phone_numbers_business_id"), table_name="phone_numbers")
    op.drop_table("phone_numbers")
