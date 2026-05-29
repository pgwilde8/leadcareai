"""Admin customer onboarding checklist per business."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.business import Business
from app.models.business_lead import BusinessLead
from app.models.business_user import BusinessUser
from app.models.lead import Lead
from app.models.message import Message
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.services import phone_number_service, user_invite_service
from app.services.business_service import get_business
from app.services.call_forwarding_service import is_forwarding_setup_complete

CHECKLIST_STATUSES = frozenset({"complete", "warning", "missing", "manual"})

LAUNCH_REQUIRED_KEYS = frozenset({
    "stripe_paid_or_active",
    "business_user_access",
    "twilio_number_assigned",
    "backup_mode_acknowledged",
    "forwarding_test_passed",
    "notification_contact_set",
})

POST_LAUNCH_KEYS = frozenset({
    "first_lead_captured",
    "first_customer_reply_captured",
    "live_launch_verified",
})

LAUNCH_MARK_REQUIRED_MESSAGES = {
    "forwarding_test_passed": "Forwarding test must be marked passed before launch verification.",
    "twilio_number_assigned": "Assign an active Twilio number before launch verification.",
    "notification_contact_set": "Set notification email or phone before launch verification.",
}


@dataclass(frozen=True)
class OnboardingChecklistItem:
    key: str
    label: str
    status: str
    description: str
    action_url: str | None = None
    action_hint: str | None = None
    is_launch_required: bool = False
    is_post_launch: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "description": self.description,
            "action_url": self.action_url,
            "action_hint": self.action_hint,
            "is_launch_required": self.is_launch_required,
            "is_post_launch": self.is_post_launch,
        }


@dataclass(frozen=True)
class LaunchVerificationContext:
    can_mark_verified: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    has_lead: bool
    has_inbound_message: bool
    has_notification_log: bool
    active_twilio_number: str | None
    customer_facing_phone: str | None


@dataclass(frozen=True)
class BusinessOnboardingChecklist:
    items: tuple[OnboardingChecklistItem, ...]
    ready_for_launch: bool
    launch_verified: bool
    launch_missing_labels: tuple[str, ...]
    launch_items: tuple[OnboardingChecklistItem, ...]
    post_launch_items: tuple[OnboardingChecklistItem, ...]
    setup_items: tuple[OnboardingChecklistItem, ...]
    launch_verification: LaunchVerificationContext

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "ready_for_launch": self.ready_for_launch,
            "launch_verified": self.launch_verified,
            "launch_missing_labels": list(self.launch_missing_labels),
            "launch_items": [item.to_dict() for item in self.launch_items],
            "post_launch_items": [item.to_dict() for item in self.post_launch_items],
            "setup_items": [item.to_dict() for item in self.setup_items],
        }


def _item(
    *,
    key: str,
    label: str,
    status: str,
    description: str,
    action_url: str | None = None,
    action_hint: str | None = None,
    launch_required: bool = False,
    post_launch: bool = False,
) -> OnboardingChecklistItem:
    return OnboardingChecklistItem(
        key=key,
        label=label,
        status=status,
        description=description,
        action_url=action_url,
        action_hint=action_hint,
        is_launch_required=launch_required,
        is_post_launch=post_launch,
    )


def _launch_item_satisfied(item: OnboardingChecklistItem) -> bool:
    """Whether a launch-required step counts toward ready-for-launch."""
    if item.key == "business_user_access":
        return item.status in {"complete", "warning"}
    return item.status == "complete"


def _business_lead_for_business(db: Session, business_id: uuid.UUID) -> BusinessLead | None:
    return (
        db.query(BusinessLead)
        .filter(BusinessLead.converted_business_id == business_id)
        .order_by(BusinessLead.created_at.desc())
        .first()
    )


def _primary_business_user_invite(db: Session, business_id: uuid.UUID) -> tuple[BusinessUser | None, str | None]:
    link = (
        db.query(BusinessUser)
        .options(joinedload(BusinessUser.user))
        .filter(BusinessUser.business_id == business_id)
        .order_by(BusinessUser.created_at)
        .first()
    )
    if link is None:
        return None, None
    invite = user_invite_service.latest_invite_status(
        db,
        user_id=link.user_id,
        purpose=user_invite_service.BUSINESS_INVITE,
    )
    return link, invite.status


def _has_active_twilio_number(db: Session, business_id: uuid.UUID) -> bool:
    numbers = phone_number_service.list_phone_numbers_for_business(db, business_id)
    return any(record.status == "active" for record in numbers)


def _has_lead(db: Session, business_id: uuid.UUID) -> bool:
    return (
        db.query(Lead.id).filter(Lead.business_id == business_id).limit(1).first()
        is not None
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _notification_configured(business: Business) -> bool:
    return bool(
        (business.notification_email or "").strip() or (business.notification_phone or "").strip()
    )


def _active_twilio_number(db: Session, business_id: uuid.UUID) -> str | None:
    for record in phone_number_service.list_phone_numbers_for_business(db, business_id):
        if record.status == "active":
            return record.phone_number
    return None


def _launch_mark_blockers(db: Session, business: Business) -> list[str]:
    blockers: list[str] = []
    if not is_forwarding_setup_complete(business):
        blockers.append(LAUNCH_MARK_REQUIRED_MESSAGES["forwarding_test_passed"])
    if _active_twilio_number(db, business.id) is None:
        blockers.append(LAUNCH_MARK_REQUIRED_MESSAGES["twilio_number_assigned"])
    if not _notification_configured(business):
        blockers.append(LAUNCH_MARK_REQUIRED_MESSAGES["notification_contact_set"])
    return blockers


def build_launch_verification_context(db: Session, business: Business) -> LaunchVerificationContext:
    business_id = business.id
    blockers = tuple(_launch_mark_blockers(db, business))
    warnings: list[str] = []
    has_lead = _has_lead(db, business_id)
    has_inbound = _has_inbound_customer_message(db, business_id)
    if not has_lead:
        warnings.append("No operational lead captured yet — confirm manually if you still verify launch.")
    if has_lead and not has_inbound:
        warnings.append("Lead exists but no inbound customer SMS detected yet.")
    has_notification_log = (
        db.query(NotificationLog.id).filter(NotificationLog.business_id == business_id).limit(1).first()
        is not None
    )
    if not has_notification_log:
        warnings.append("No notification_logs row yet — staff alert may not have fired.")

    return LaunchVerificationContext(
        can_mark_verified=len(blockers) == 0 and business.launch_verified_at is None,
        blockers=blockers,
        warnings=tuple(warnings),
        has_lead=has_lead,
        has_inbound_message=has_inbound,
        has_notification_log=has_notification_log,
        active_twilio_number=_active_twilio_number(db, business_id),
        customer_facing_phone=(business.main_phone or "").strip() or None,
    )


def mark_launch_verified(
    db: Session,
    business_id: uuid.UUID,
    *,
    verified_by_user_id: uuid.UUID,
    notes: str | None = None,
) -> Business:
    business = get_business(db, business_id)
    blockers = _launch_mark_blockers(db, business)
    if blockers:
        raise ValueError(" ".join(blockers))
    if business.launch_verified_at is not None:
        raise ValueError("Launch is already verified for this business.")

    business.launch_verified_at = _now()
    business.launch_verified_by_user_id = verified_by_user_id
    if notes is not None:
        stripped = notes.strip()
        business.launch_verification_notes = stripped or None
    db.flush()
    return business


def _has_inbound_customer_message(db: Session, business_id: uuid.UUID) -> bool:
    return (
        db.query(Message.id)
        .filter(
            Message.business_id == business_id,
            Message.direction == "inbound",
        )
        .limit(1)
        .first()
        is not None
    )


def build_business_onboarding_checklist(db: Session, business: Business) -> BusinessOnboardingChecklist:
    """Aggregate activation readiness for admin business detail."""
    business_id = business.id
    admin_base = f"/admin/businesses/{business_id}"
    lead_record = _business_lead_for_business(db, business_id)
    user_link, invite_status = _primary_business_user_invite(db, business_id)

    paid_or_active = business.status == "active" or bool(business.stripe_subscription_id)
    has_active_number = _has_active_twilio_number(db, business_id)
    forwarding_complete = is_forwarding_setup_complete(business)
    forwarding_status = business.customer_phone_forwarding_status
    forwarding_progress = forwarding_status in {
        "instructions_sent",
        "customer_attempted",
        "test_passed",
        "failed_needs_help",
    }
    mobile_carrier_ok = bool(business.customer_phone_carrier) and business.customer_phone_is_mobile is not None
    notification_ok = bool(
        (business.notification_email or "").strip() or (business.notification_phone or "").strip()
    )
    lead_ack = bool(lead_record and lead_record.call_forwarding_terms_acknowledged)
    has_lead = _has_lead(db, business_id)
    has_inbound = _has_inbound_customer_message(db, business_id)

    items: list[OnboardingChecklistItem] = []

    items.append(
        _item(
            key="business_created",
            label="Business record created",
            status="complete",
            description=f"Business “{business.name}” exists in LeadCareAI.",
            action_url=admin_base,
        )
    )

    items.append(
        _item(
            key="stripe_paid_or_active",
            label="Stripe paid / account active",
            status="complete" if paid_or_active else "missing",
            description=(
                f"Business status is {business.status!r}."
                + (" Stripe subscription on file." if business.stripe_subscription_id else "")
                if paid_or_active
                else "Business is not active and has no Stripe subscription on file."
            ),
            action_hint="Complete Growth checkout or activate after payment.",
            launch_required=True,
        )
    )

    if user_link is None:
        invited_status = "missing"
        invited_desc = "No business dashboard user is linked yet."
        invited_url = f"{admin_base}#link-user"
    else:
        invited_status = "complete"
        invited_desc = f"User {user_link.user.email} is linked ({user_link.role})."
        invited_url = f"{admin_base}/resend-invite"
    items.append(
        _item(
            key="business_user_invited",
            label="Business user invited",
            status=invited_status,
            description=invited_desc,
            action_url=invited_url if user_link else None,
            action_hint="Link user or resend invite from Linked users.",
        )
    )

    if user_link is None:
        accepted_status = "missing"
        accepted_desc = "No linked user — invite not sent yet."
        accepted_url = None
    elif invite_status == "accepted":
        accepted_status = "complete"
        accepted_desc = "Invite accepted (password set via invite link)."
        accepted_url = None
    elif invite_status == "sent":
        accepted_status = "warning"
        accepted_desc = "Invite sent; waiting for customer to accept."
        accepted_url = f"{admin_base}/resend-invite"
    elif invite_status == "expired":
        accepted_status = "warning"
        accepted_desc = "Latest invite expired — resend invite."
        accepted_url = f"{admin_base}/resend-invite"
    elif invite_status == "not needed":
        accepted_status = "complete"
        accepted_desc = "User can log in without a pending invite."
        accepted_url = None
    else:
        accepted_status = "warning"
        accepted_desc = f"Invite status: {invite_status or 'unknown'}."
        accepted_url = f"{admin_base}/resend-invite"
    items.append(
        _item(
            key="business_user_accepted_invite",
            label="Business user accepted invite",
            status=accepted_status,
            description=accepted_desc,
            action_url=accepted_url,
            action_hint="Resend business invite if needed.",
        )
    )

    if user_link is None:
        access_status = "missing"
        access_desc = "Customer cannot access the business dashboard yet."
    elif invite_status in {"accepted", "not needed"}:
        access_status = "complete"
        access_desc = "Customer can access the business dashboard."
    elif invite_status == "sent":
        access_status = "warning"
        access_desc = "User linked; invite pending acceptance (counts as invited for launch)."
    else:
        access_status = "warning"
        access_desc = "User linked; invite may need attention (resend if expired)."
    items.append(
        _item(
            key="business_user_access",
            label="Business dashboard access",
            status=access_status,
            description=access_desc,
            action_url=f"{admin_base}/resend-invite" if user_link else f"{admin_base}#link-user",
            launch_required=True,
        )
    )

    items.append(
        _item(
            key="twilio_number_assigned",
            label="Twilio number assigned (active)",
            status="complete" if has_active_number else "missing",
            description=(
                "At least one active LeadCareAI/Twilio number is assigned."
                if has_active_number
                else "No active inbound number — Backup Mode and SMS need a number."
            ),
            action_url=f"{admin_base}/phone-numbers/new",
            launch_required=True,
        )
    )

    if lead_ack:
        ack_status = "complete"
        ack_desc = "Mobile call-forwarding terms acknowledged on business lead."
        ack_url = f"/admin/business-leads/{lead_record.id}" if lead_record else None
    elif lead_record:
        ack_status = "missing"
        ack_desc = "Converted lead exists but terms are not acknowledged."
        ack_url = f"/admin/business-leads/{lead_record.id}"
    else:
        ack_status = "missing"
        ack_desc = "No linked business lead with acknowledgement on file."
        ack_url = "/admin/business-leads"
    items.append(
        _item(
            key="backup_mode_acknowledged",
            label="Backup Mode terms acknowledged",
            status=ack_status,
            description=ack_desc,
            action_url=ack_url,
            action_hint="Record on business lead detail after phone confirmation.",
            launch_required=True,
        )
    )

    if mobile_carrier_ok:
        carrier_status = "complete"
        carrier_desc = (
            f"Mobile: {'yes' if business.customer_phone_is_mobile else 'no'}; "
            f"carrier: {business.customer_phone_carrier}."
        )
    elif business.customer_phone_carrier or business.customer_phone_is_mobile is not None:
        carrier_status = "warning"
        carrier_desc = "Partial mobile/carrier info in business settings."
    else:
        carrier_status = "missing"
        carrier_desc = "Mobile line and carrier not recorded in settings."
    items.append(
        _item(
            key="mobile_carrier_recorded",
            label="Mobile line & carrier recorded",
            status=carrier_status,
            description=carrier_desc,
            action_hint="Customer completes fields in business settings / Backup Mode.",
        )
    )

    if forwarding_progress:
        fwd_status = "complete" if forwarding_status != "failed_needs_help" else "warning"
        fwd_desc = f"Backup Mode status: {forwarding_status.replace('_', ' ')}."
    else:
        fwd_status = "missing"
        fwd_desc = "Customer has not progressed past not_started for Backup Mode."
    items.append(
        _item(
            key="forwarding_instructions_sent_or_attempted",
            label="Backup Mode instructions sent / attempted",
            status=fwd_status,
            description=fwd_desc,
            action_url=f"{admin_base}#call-forwarding",
            action_hint="Mark instructions_sent or customer opens Backup Mode page.",
        )
    )

    items.append(
        _item(
            key="forwarding_test_passed",
            label="Forwarding test passed",
            status="complete" if forwarding_complete else "manual",
            description=(
                f"Live test passed ({business.call_forwarding_tested_at})."
                if forwarding_complete and business.call_forwarding_tested_at
                else "Live forwarding test passed."
                if forwarding_complete
                else "Admin must verify live call-forwarding test before launch."
            ),
            action_url=f"{admin_base}#call-forwarding",
            action_hint="Mark test_passed after live test.",
            launch_required=True,
        )
    )

    items.append(
        _item(
            key="notification_contact_set",
            label="Notification email or phone set",
            status="complete" if notification_ok else "missing",
            description=(
                "Staff notification email or phone is configured."
                if notification_ok
                else "Set notification_email or notification_phone for lead alerts."
            ),
            launch_required=True,
        )
    )

    items.append(
        _item(
            key="first_lead_captured",
            label="First lead captured (post-launch)",
            status="complete" if has_lead else "missing",
            description=(
                "At least one operational lead exists."
                if has_lead
                else "No leads yet — verify after Backup Mode is live."
            ),
            action_url=f"{admin_base}/leads",
            post_launch=True,
        )
    )

    items.append(
        _item(
            key="first_customer_reply_captured",
            label="First customer reply captured (post-launch)",
            status="complete" if has_inbound else "missing",
            description=(
                "Inbound customer SMS/message detected."
                if has_inbound
                else "No inbound customer reply yet."
            ),
            action_url=f"/admin/notification-logs?business_id={business_id}",
            post_launch=True,
        )
    )

    launch_ctx = build_launch_verification_context(db, business)
    if business.launch_verified_at:
        verified_status = "complete"
        verified_desc = f"Live launch smoke test verified at {business.launch_verified_at}."
    else:
        verified_status = "manual"
        verified_desc = "Complete the live launch test script, then mark launch verified."
    items.append(
        _item(
            key="live_launch_verified",
            label="Live launch verified",
            status=verified_status,
            description=verified_desc,
            action_url=f"{admin_base}#live-launch-test",
            action_hint="Run end-to-end call/SMS test before marking verified.",
            post_launch=True,
        )
    )

    tuple_items = tuple(items)
    launch_items = tuple(i for i in tuple_items if i.is_launch_required)
    post_launch_items = tuple(i for i in tuple_items if i.is_post_launch)
    setup_items = tuple(i for i in tuple_items if not i.is_post_launch)

    missing_launch = [item.label for item in launch_items if not _launch_item_satisfied(item)]
    ready = len(missing_launch) == 0

    return BusinessOnboardingChecklist(
        items=tuple_items,
        ready_for_launch=ready,
        launch_verified=business.launch_verified_at is not None,
        launch_missing_labels=tuple(missing_launch),
        launch_items=launch_items,
        post_launch_items=post_launch_items,
        setup_items=setup_items,
        launch_verification=launch_ctx,
    )
