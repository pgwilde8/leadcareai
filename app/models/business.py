"""Business (customer) account model."""

from __future__ import annotations

import uuid
from datetime import datetime

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

CUSTOMER_PHONE_CARRIERS = frozenset({
    "verizon",
    "att",
    "t_mobile",
    "metro_tmobile",
    "cricket",
    "boost",
    "consumer_cellular",
    "other",
})

CALL_FORWARDING_STATUSES = frozenset({
    "not_started",
    "instructions_sent",
    "customer_attempted",
    "test_passed",
    "failed_needs_help",
})

if TYPE_CHECKING:
    from app.models.business_compliance_profile import BusinessComplianceProfile
    from app.models.business_user import BusinessUser
    from app.models.lead import Lead
    from app.models.message import Message
    from app.models.phone_number import PhoneNumber


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    main_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notification_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    missed_call_textback_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sms_signature: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lead_intake_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="America/New_York",
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    customer_phone_carrier: Mapped[str | None] = mapped_column(String(80), nullable=True)
    customer_phone_is_mobile: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    customer_phone_forwarding_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="not_started",
        index=True,
    )
    customer_phone_forwarding_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_forwarding_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    launch_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    launch_verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    launch_verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    user_links: Mapped[list[BusinessUser]] = relationship(
        back_populates="business",
    )
    phone_numbers: Mapped[list[PhoneNumber]] = relationship(
        back_populates="business",
    )
    leads: Mapped[list[Lead]] = relationship(
        back_populates="business",
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="business",
    )
    compliance_profile: Mapped[BusinessComplianceProfile | None] = relationship(
        back_populates="business",
        uselist=False,
    )
