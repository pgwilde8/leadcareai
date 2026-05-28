"""user_invite_tokens table

Revision ID: 20260528_0013
Revises: 20260527_0012
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0013"
down_revision: Union[str, None] = "20260527_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_invite_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("delivery_status", sa.String(length=32), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_invite_tokens_user_id"), "user_invite_tokens", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_user_invite_tokens_token_hash"),
        "user_invite_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(op.f("ix_user_invite_tokens_purpose"), "user_invite_tokens", ["purpose"], unique=False)
    op.create_index(op.f("ix_user_invite_tokens_expires_at"), "user_invite_tokens", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_invite_tokens_expires_at"), table_name="user_invite_tokens")
    op.drop_index(op.f("ix_user_invite_tokens_purpose"), table_name="user_invite_tokens")
    op.drop_index(op.f("ix_user_invite_tokens_token_hash"), table_name="user_invite_tokens")
    op.drop_index(op.f("ix_user_invite_tokens_user_id"), table_name="user_invite_tokens")
    op.drop_table("user_invite_tokens")
