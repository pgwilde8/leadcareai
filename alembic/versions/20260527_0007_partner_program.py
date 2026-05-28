"""partner program tables

Revision ID: 20260527_0007
Revises: 20260527_0006
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0007"
down_revision: Union[str, None] = "20260527_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partner_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("experience_summary", sa.Text(), nullable=True),
        sa.Column("why_interested", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="applied"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_partner_applications_email"), "partner_applications", ["email"], unique=False)
    op.create_index(op.f("ix_partner_applications_status"), "partner_applications", ["status"], unique=False)

    op.create_table(
        "partner_document_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_partner_document_templates_code"),
    )
    op.create_index(
        op.f("ix_partner_document_templates_code"),
        "partner_document_templates",
        ["code"],
        unique=True,
    )

    op.create_table(
        "partners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("application_id", sa.Uuid(), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("referral_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["partner_applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_partners_application_id"),
        sa.UniqueConstraint("referral_code", name="uq_partners_referral_code"),
        sa.UniqueConstraint("user_id", name="uq_partners_user_id"),
    )
    op.create_index(op.f("ix_partners_email"), "partners", ["email"], unique=False)
    op.create_index(op.f("ix_partners_referral_code"), "partners", ["referral_code"], unique=True)
    op.create_index(op.f("ix_partners_status"), "partners", ["status"], unique=False)
    op.create_index(op.f("ix_partners_user_id"), "partners", ["user_id"], unique=True)

    op.create_table(
        "partner_signed_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("document_template_id", sa.Uuid(), nullable=False),
        sa.Column("document_code", sa.String(length=80), nullable=False),
        sa.Column("document_title", sa.String(length=255), nullable=False),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("signer_name", sa.String(length=255), nullable=False),
        sa.Column("signer_email", sa.String(length=255), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("consent_text", sa.Text(), nullable=False),
        sa.Column("signature_text", sa.String(length=255), nullable=False),
        sa.Column("document_snapshot", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["partner_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_template_id"], ["partner_document_templates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_partner_signed_documents_application_id"),
        "partner_signed_documents",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_signed_documents_document_template_id"),
        "partner_signed_documents",
        ["document_template_id"],
        unique=False,
    )

    op.create_table(
        "partner_customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("referral_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="referred"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_partner_customers_business_id"), "partner_customers", ["business_id"], unique=False)
    op.create_index(op.f("ix_partner_customers_partner_id"), "partner_customers", ["partner_id"], unique=False)
    op.create_index(op.f("ix_partner_customers_referral_code"), "partner_customers", ["referral_code"], unique=False)
    op.create_index(op.f("ix_partner_customers_status"), "partner_customers", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_partner_customers_status"), table_name="partner_customers")
    op.drop_index(op.f("ix_partner_customers_referral_code"), table_name="partner_customers")
    op.drop_index(op.f("ix_partner_customers_partner_id"), table_name="partner_customers")
    op.drop_index(op.f("ix_partner_customers_business_id"), table_name="partner_customers")
    op.drop_table("partner_customers")
    op.drop_index(op.f("ix_partner_signed_documents_document_template_id"), table_name="partner_signed_documents")
    op.drop_index(op.f("ix_partner_signed_documents_application_id"), table_name="partner_signed_documents")
    op.drop_table("partner_signed_documents")
    op.drop_index(op.f("ix_partners_user_id"), table_name="partners")
    op.drop_index(op.f("ix_partners_status"), table_name="partners")
    op.drop_index(op.f("ix_partners_referral_code"), table_name="partners")
    op.drop_index(op.f("ix_partners_email"), table_name="partners")
    op.drop_table("partners")
    op.drop_index(op.f("ix_partner_document_templates_code"), table_name="partner_document_templates")
    op.drop_table("partner_document_templates")
    op.drop_index(op.f("ix_partner_applications_status"), table_name="partner_applications")
    op.drop_index(op.f("ix_partner_applications_email"), table_name="partner_applications")
    op.drop_table("partner_applications")
