"""Signed partner document record (typed signature V1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.partner_application import PartnerApplication
    from app.models.partner_document_template import PartnerDocumentTemplate

ELECTRONIC_CONSENT_TEXT = (
    "I agree to use electronic records and signatures and intend my typed name "
    "to be my electronic signature."
)


class PartnerSignedDocument(Base):
    __tablename__ = "partner_signed_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("partner_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("partner_document_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_code: Mapped[str] = mapped_column(String(80), nullable=False)
    document_title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_version: Mapped[str] = mapped_column(String(32), nullable=False)
    signer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    signature_text: Mapped[str] = mapped_column(String(255), nullable=False)
    document_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    application: Mapped[PartnerApplication] = relationship(back_populates="signed_documents")
    document_template: Mapped[PartnerDocumentTemplate] = relationship(
        back_populates="signed_documents",
    )
