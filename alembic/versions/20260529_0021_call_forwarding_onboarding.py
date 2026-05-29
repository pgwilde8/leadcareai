"""Business call-forwarding onboarding fields (mobile-first V1)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_0021"
down_revision = "20260528_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("customer_phone_carrier", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("customer_phone_is_mobile", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column(
            "customer_phone_forwarding_status",
            sa.String(length=50),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column(
        "businesses",
        sa.Column("customer_phone_forwarding_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column("call_forwarding_tested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "business_leads",
        sa.Column(
            "call_forwarding_terms_acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("business_leads", "call_forwarding_terms_acknowledged")
    op.drop_column("businesses", "call_forwarding_tested_at")
    op.drop_column("businesses", "customer_phone_forwarding_notes")
    op.drop_column("businesses", "customer_phone_forwarding_status")
    op.drop_column("businesses", "customer_phone_is_mobile")
    op.drop_column("businesses", "customer_phone_carrier")
