"""commission payout batches and commission.payout_id

Revision ID: 20260528_0017
Revises: 20260528_0016
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0017"
down_revision: Union[str, None] = "20260528_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commission_payouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("total_amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="usd"),
        sa.Column("payment_method_note", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commission_payouts_partner_id"), "commission_payouts", ["partner_id"], unique=False)
    op.create_index(op.f("ix_commission_payouts_status"), "commission_payouts", ["status"], unique=False)

    op.add_column("commissions", sa.Column("payout_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_commissions_payout_id_commission_payouts",
        "commissions",
        "commission_payouts",
        ["payout_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_commissions_payout_id"), "commissions", ["payout_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commissions_payout_id"), table_name="commissions")
    op.drop_constraint("fk_commissions_payout_id_commission_payouts", "commissions", type_="foreignkey")
    op.drop_column("commissions", "payout_id")
    op.drop_index(op.f("ix_commission_payouts_status"), table_name="commission_payouts")
    op.drop_index(op.f("ix_commission_payouts_partner_id"), table_name="commission_payouts")
    op.drop_table("commission_payouts")
