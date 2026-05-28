"""Business (customer) account model."""

from __future__ import annotations

import uuid
from datetime import datetime

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

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
