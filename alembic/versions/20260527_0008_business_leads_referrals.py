"""business_leads and partner referral attribution

Revision ID: 20260527_0008
Revises: 20260527_0007
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0008"
down_revision: Union[str, None] = "20260527_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="demo_form"),
        sa.Column("referral_code", sa.String(length=32), nullable=True),
        sa.Column("partner_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_business_leads_email"), "business_leads", ["email"], unique=False)
    op.create_index(op.f("ix_business_leads_partner_id"), "business_leads", ["partner_id"], unique=False)
    op.create_index(op.f("ix_business_leads_phone"), "business_leads", ["phone"], unique=False)
    op.create_index(op.f("ix_business_leads_referral_code"), "business_leads", ["referral_code"], unique=False)
    op.create_index(op.f("ix_business_leads_status"), "business_leads", ["status"], unique=False)

    op.add_column("partner_customers", sa.Column("business_lead_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_partner_customers_business_lead_id"),
        "partner_customers",
        ["business_lead_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_partner_customers_business_lead_id",
        "partner_customers",
        "business_leads",
        ["business_lead_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_partner_customers_partner_business_lead",
        "partner_customers",
        ["partner_id", "business_lead_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_partner_customers_partner_business_lead", "partner_customers", type_="unique")
    op.drop_constraint("fk_partner_customers_business_lead_id", "partner_customers", type_="foreignkey")
    op.drop_index(op.f("ix_partner_customers_business_lead_id"), table_name="partner_customers")
    op.drop_column("partner_customers", "business_lead_id")
    op.drop_index(op.f("ix_business_leads_status"), table_name="business_leads")
    op.drop_index(op.f("ix_business_leads_referral_code"), table_name="business_leads")
    op.drop_index(op.f("ix_business_leads_phone"), table_name="business_leads")
    op.drop_index(op.f("ix_business_leads_partner_id"), table_name="business_leads")
    op.drop_index(op.f("ix_business_leads_email"), table_name="business_leads")
    op.drop_table("business_leads")
