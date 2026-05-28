"""A2P 10DLC / SMS compliance profile per business (manual tracking until Twilio API)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.business import Business

# TODO: Encrypt EIN and other sensitive identifiers at rest before production.


class BusinessComplianceProfile(Base):
    __tablename__ = "business_compliance_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    legal_business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dba_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ein: Mapped[str | None] = mapped_column(String(32), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    business_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="US")
    authorized_rep_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authorized_rep_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    authorized_rep_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sms_use_case: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opt_in_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_message_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_message_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_policy_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    terms_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    twilio_brand_sid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    twilio_campaign_sid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="not_started")
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

    business: Mapped[Business] = relationship(back_populates="compliance_profile")
