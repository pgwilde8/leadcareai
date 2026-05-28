"""create commissions ledger table

Revision ID: 20260528_0014
Revises: 20260528_0013
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0014"
down_revision: Union[str, None] = "20260528_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("partner_customer_id", sa.Uuid(), nullable=True),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("commission_type", sa.String(length=64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("eligible_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_customer_id"], ["partner_customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commissions_partner_id"), "commissions", ["partner_id"], unique=False)
    op.create_index(op.f("ix_commissions_business_id"), "commissions", ["business_id"], unique=False)
    op.create_index(op.f("ix_commissions_partner_customer_id"), "commissions", ["partner_customer_id"], unique=False)
    op.create_index(op.f("ix_commissions_stripe_event_id"), "commissions", ["stripe_event_id"], unique=False)
    op.create_index(op.f("ix_commissions_stripe_invoice_id"), "commissions", ["stripe_invoice_id"], unique=False)
    op.create_index(
        op.f("ix_commissions_stripe_checkout_session_id"),
        "commissions",
        ["stripe_checkout_session_id"],
        unique=False,
    )
    op.create_index(op.f("ix_commissions_commission_type"), "commissions", ["commission_type"], unique=False)
    op.create_index(op.f("ix_commissions_status"), "commissions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commissions_status"), table_name="commissions")
    op.drop_index(op.f("ix_commissions_commission_type"), table_name="commissions")
    op.drop_index(op.f("ix_commissions_stripe_checkout_session_id"), table_name="commissions")
    op.drop_index(op.f("ix_commissions_stripe_invoice_id"), table_name="commissions")
    op.drop_index(op.f("ix_commissions_stripe_event_id"), table_name="commissions")
    op.drop_index(op.f("ix_commissions_partner_customer_id"), table_name="commissions")
    op.drop_index(op.f("ix_commissions_business_id"), table_name="commissions")
    op.drop_index(op.f("ix_commissions_partner_id"), table_name="commissions")
    op.drop_table("commissions")
