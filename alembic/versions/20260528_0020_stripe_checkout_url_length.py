"""Widen business_leads.stripe_checkout_url for long Stripe Checkout URLs."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260528_0020"
down_revision = "20260528_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "business_leads",
        "stripe_checkout_url",
        existing_type=sa.String(length=500),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "business_leads",
        "stripe_checkout_url",
        existing_type=sa.String(length=2048),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
