"""lead AI qualification fields

Revision ID: 20260527_0010
Revises: 20260527_0009
Create Date: 2026-05-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0010"
down_revision: Union[str, None] = "20260527_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("ai_temperature", sa.String(length=32), nullable=True))
    op.add_column("leads", sa.Column("ai_next_question", sa.String(length=160), nullable=True))
    op.add_column("leads", sa.Column("ai_confidence", sa.Float(), nullable=True))
    op.add_column("leads", sa.Column("ai_last_analyzed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "ai_last_analyzed_at")
    op.drop_column("leads", "ai_confidence")
    op.drop_column("leads", "ai_next_question")
    op.drop_column("leads", "ai_temperature")
