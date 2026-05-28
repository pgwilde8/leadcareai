"""Approved partner (independent sales contractor)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.partner_application import PartnerApplication
    from app.models.partner_customer import PartnerCustomer
    from app.models.user import User

PARTNER_STATUSES = frozenset({
    "pending",
    "active",
    "suspended",
    "rejected",
})


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("partner_applications.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    referral_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    user: Mapped[User | None] = relationship(foreign_keys=[user_id])
    application: Mapped[PartnerApplication | None] = relationship(back_populates="partner")
    customers: Mapped[list[PartnerCustomer]] = relationship(back_populates="partner")
