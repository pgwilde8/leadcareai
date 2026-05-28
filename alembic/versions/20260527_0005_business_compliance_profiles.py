"""business_compliance_profiles table

Revision ID: 20260527_0005
Revises: 20260527_0004
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0005"
down_revision: Union[str, None] = "20260527_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_compliance_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("legal_business_name", sa.String(length=255), nullable=True),
        sa.Column("dba_name", sa.String(length=255), nullable=True),
        sa.Column("business_type", sa.String(length=120), nullable=True),
        sa.Column("ein", sa.String(length=32), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("business_phone", sa.String(length=50), nullable=True),
        sa.Column("business_email", sa.String(length=255), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="US"),
        sa.Column("authorized_rep_name", sa.String(length=255), nullable=True),
        sa.Column("authorized_rep_title", sa.String(length=120), nullable=True),
        sa.Column("authorized_rep_email", sa.String(length=255), nullable=True),
        sa.Column("sms_use_case", sa.String(length=255), nullable=True),
        sa.Column("opt_in_description", sa.Text(), nullable=True),
        sa.Column("sample_message_1", sa.Text(), nullable=True),
        sa.Column("sample_message_2", sa.Text(), nullable=True),
        sa.Column("privacy_policy_url", sa.String(length=500), nullable=True),
        sa.Column("terms_url", sa.String(length=500), nullable=True),
        sa.Column("twilio_brand_sid", sa.String(length=255), nullable=True),
        sa.Column("twilio_campaign_sid", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="not_started"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", name="uq_business_compliance_profiles_business_id"),
    )
    op.create_index(
        op.f("ix_business_compliance_profiles_business_id"),
        "business_compliance_profiles",
        ["business_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_business_compliance_profiles_twilio_brand_sid"),
        "business_compliance_profiles",
        ["twilio_brand_sid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_compliance_profiles_twilio_campaign_sid"),
        "business_compliance_profiles",
        ["twilio_campaign_sid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_business_compliance_profiles_twilio_campaign_sid"),
        table_name="business_compliance_profiles",
    )
    op.drop_index(
        op.f("ix_business_compliance_profiles_twilio_brand_sid"),
        table_name="business_compliance_profiles",
    )
    op.drop_index(
        op.f("ix_business_compliance_profiles_business_id"),
        table_name="business_compliance_profiles",
    )
    op.drop_table("business_compliance_profiles")
