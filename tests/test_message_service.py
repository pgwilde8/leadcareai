"""Message service tests (SQLite)."""

from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy.orm import Session

from app.services.business_service import create_business
from app.services.lead_service import create_lead
from app.services.message_service import (
    MESSAGE_CHANNELS,
    MESSAGE_DIRECTIONS,
    MESSAGE_STATUSES,
    create_message,
    list_messages_for_lead,
)


def test_create_message_internal(db_session: Session) -> None:
    business = create_business(db_session, name="Msg Co")
    lead = create_lead(db_session, business.id, name="Lead One")
    msg = create_message(
        db_session,
        business.id,
        lead.id,
        body="  Internal note  ",
        direction="internal",
    )
    assert msg.body == "Internal note"
    assert msg.direction == "internal"
    assert msg.channel == "manual"
    assert msg.status == "recorded"


def test_create_message_rejects_empty_body(db_session: Session) -> None:
    business = create_business(db_session, name="Empty Msg Co")
    lead = create_lead(db_session, business.id, name="Lead")
    with pytest.raises(ValueError, match="must not be empty"):
        create_message(db_session, business.id, lead.id, body="   ")


def test_create_message_rejects_missing_business(db_session: Session) -> None:
    business = create_business(db_session, name="Biz")
    lead = create_lead(db_session, business.id, name="Lead")
    with pytest.raises(ValueError, match="not found"):
        create_message(db_session, uuid.uuid4(), lead.id, body="Hi")


def test_create_message_rejects_missing_lead(db_session: Session) -> None:
    business = create_business(db_session, name="Biz2")
    with pytest.raises(ValueError, match="not found"):
        create_message(db_session, business.id, uuid.uuid4(), body="Hi")


def test_create_message_rejects_lead_from_different_business(db_session: Session) -> None:
    biz_a = create_business(db_session, name="A")
    biz_b = create_business(db_session, name="B")
    lead = create_lead(db_session, biz_a.id, name="Lead A")
    with pytest.raises(ValueError, match="does not belong"):
        create_message(db_session, biz_b.id, lead.id, body="Wrong biz")


@pytest.mark.parametrize("direction", sorted(MESSAGE_DIRECTIONS))
def test_valid_directions(db_session: Session, direction: str) -> None:
    business = create_business(db_session, name=f"Dir {direction}")
    lead = create_lead(db_session, business.id, name="L")
    msg = create_message(db_session, business.id, lead.id, body="ok", direction=direction)
    assert msg.direction == direction


def test_invalid_direction_raises(db_session: Session) -> None:
    business = create_business(db_session, name="Bad Dir")
    lead = create_lead(db_session, business.id, name="L")
    with pytest.raises(ValueError, match="Invalid message direction"):
        create_message(db_session, business.id, lead.id, body="x", direction="sideways")


@pytest.mark.parametrize("channel", sorted(MESSAGE_CHANNELS))
def test_valid_channels(db_session: Session, channel: str) -> None:
    business = create_business(db_session, name=f"Ch {channel}")
    lead = create_lead(db_session, business.id, name="L")
    msg = create_message(db_session, business.id, lead.id, body="ok", channel=channel)
    assert msg.channel == channel


def test_invalid_channel_raises(db_session: Session) -> None:
    business = create_business(db_session, name="Bad Ch")
    lead = create_lead(db_session, business.id, name="L")
    with pytest.raises(ValueError, match="Invalid message channel"):
        create_message(db_session, business.id, lead.id, body="x", channel="fax")


@pytest.mark.parametrize("status", sorted(MESSAGE_STATUSES))
def test_valid_statuses(db_session: Session, status: str) -> None:
    business = create_business(db_session, name=f"St {status}")
    lead = create_lead(db_session, business.id, name="L")
    msg = create_message(db_session, business.id, lead.id, body="ok", status=status)
    assert msg.status == status


def test_invalid_status_raises(db_session: Session) -> None:
    business = create_business(db_session, name="Bad St")
    lead = create_lead(db_session, business.id, name="L")
    with pytest.raises(ValueError, match="Invalid message status"):
        create_message(db_session, business.id, lead.id, body="x", status="unknown")


def test_list_messages_for_lead_stable_order(db_session: Session) -> None:
    from datetime import datetime, timedelta, timezone

    business = create_business(db_session, name="Order Co")
    lead = create_lead(db_session, business.id, name="Lead")
    base = datetime.now(timezone.utc)
    first = create_message(db_session, business.id, lead.id, body="First")
    first.created_at = base
    second = create_message(db_session, business.id, lead.id, body="Second")
    second.created_at = base + timedelta(seconds=1)
    third = create_message(db_session, business.id, lead.id, body="Third")
    third.created_at = base + timedelta(seconds=2)
    db_session.commit()

    bodies = [m.body for m in list_messages_for_lead(db_session, lead.id)]
    assert bodies == ["First", "Second", "Third"]
    assert list_messages_for_lead(db_session, lead.id) == list_messages_for_lead(
        db_session, lead.id
    )
