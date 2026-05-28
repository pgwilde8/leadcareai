"""Encrypted W-9 / tax information for partner applications."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.partner_application import PartnerApplication

TIN_TYPES = frozenset({"ssn", "ein"})


class PartnerTaxInfo(Base):
    __tablename__ = "partner_tax_info"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("partner_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    tax_classification: Mapped[str] = mapped_column(String(80), nullable=False)
    tin_type: Mapped[str] = mapped_column(String(10), nullable=False)
    tin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    certified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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

    application: Mapped[PartnerApplication] = relationship(back_populates="tax_info")
