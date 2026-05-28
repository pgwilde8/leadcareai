"""Prospective business inquiry (demo / interest form — not a paying customer yet)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.partner import Partner
    from app.models.partner_customer import PartnerCustomer

BUSINESS_LEAD_STATUSES = frozenset({
    "new",
    "contacted",
    "qualified",
    "converted",
    "rejected",
})

PAYMENT_STATUSES = frozenset({
    "none",
    "checkout_created",
    "paid",
    "failed",
    "canceled",
})


class BusinessLead(Base):
    __tablename__ = "business_leads"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="demo_form")
    referral_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("partners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="new", index=True)
    payment_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="none",
        index=True,
    )
    converted_business_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("businesses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    partner: Mapped[Partner | None] = relationship()
    partner_attributions: Mapped[list[PartnerCustomer]] = relationship(
        back_populates="business_lead",
    )
