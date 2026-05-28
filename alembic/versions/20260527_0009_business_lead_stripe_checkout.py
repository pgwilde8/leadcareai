"""business lead stripe checkout fields and payment_events

Revision ID: 20260527_0009
Revises: 20260527_0008
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0009"
down_revision: Union[str, None] = "20260527_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "business_leads",
        sa.Column("payment_status", sa.String(length=50), nullable=False, server_default="none"),
    )
    op.add_column("business_leads", sa.Column("converted_business_id", sa.Uuid(), nullable=True))
    op.add_column("business_leads", sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True))
    op.add_column("business_leads", sa.Column("stripe_checkout_url", sa.String(length=500), nullable=True))
    op.add_column("business_leads", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.add_column("business_leads", sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        op.f("ix_business_leads_converted_business_id"),
        "business_leads",
        ["converted_business_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_leads_payment_status"),
        "business_leads",
        ["payment_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_leads_stripe_checkout_session_id"),
        "business_leads",
        ["stripe_checkout_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_leads_stripe_customer_id"),
        "business_leads",
        ["stripe_customer_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_business_leads_converted_business_id",
        "business_leads",
        "businesses",
        ["converted_business_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("business_lead_id", sa.Uuid(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(length=255), nullable=True),
        sa.Column("amount_paid_cents", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id", name="uq_payment_events_stripe_event_id"),
    )
    op.create_index(op.f("ix_payment_events_business_id"), "payment_events", ["business_id"], unique=False)
    op.create_index(
        op.f("ix_payment_events_business_lead_id"),
        "payment_events",
        ["business_lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_events_stripe_event_id"),
        "payment_events",
        ["stripe_event_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_events_stripe_event_id"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_business_lead_id"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_business_id"), table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_constraint("fk_business_leads_converted_business_id", "business_leads", type_="foreignkey")
    op.drop_index(op.f("ix_business_leads_stripe_customer_id"), table_name="business_leads")
    op.drop_index(op.f("ix_business_leads_stripe_checkout_session_id"), table_name="business_leads")
    op.drop_index(op.f("ix_business_leads_payment_status"), table_name="business_leads")
    op.drop_index(op.f("ix_business_leads_converted_business_id"), table_name="business_leads")
    op.drop_column("business_leads", "converted_at")
    op.drop_column("business_leads", "stripe_customer_id")
    op.drop_column("business_leads", "stripe_checkout_url")
    op.drop_column("business_leads", "stripe_checkout_session_id")
    op.drop_column("business_leads", "converted_business_id")
    op.drop_column("business_leads", "payment_status")
