"""Partner independent contractor application."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.partner import Partner
    from app.models.partner_signed_document import PartnerSignedDocument
    from app.models.user import User

APPLICATION_STATUSES = frozenset({
    "applied",
    "docs_pending",
    "docs_signed",
    "admin_review",
    "approved",
    "rejected",
})


class PartnerApplication(Base):
    __tablename__ = "partner_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_interested: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="applied", index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    partner: Mapped[Partner | None] = relationship(back_populates="application", uselist=False)
    signed_documents: Mapped[list[PartnerSignedDocument]] = relationship(
        back_populates="application",
    )
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_user_id])
