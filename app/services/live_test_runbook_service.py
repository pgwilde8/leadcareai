"""End-to-end launch test runbook for admin (DB state only — no external API calls)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, joinedload

from app.models.business import Business
from app.models.business_lead import BusinessLead
from app.models.business_user import BusinessUser
from app.models.commission import Commission
from app.models.lead import Lead
from app.models.message import Message
from app.models.notification_log import NotificationLog
from app.models.partner_customer import PartnerCustomer
from app.models.payment_event import PaymentEvent
from app.services import business_onboarding_service, phone_number_service, user_invite_service
from app.services.business_service import get_business, list_businesses
from app.services.system_check_service import build_system_check_sections


@dataclass(frozen=True)
class RunbookLink:
    label: str
    href: str


@dataclass(frozen=True)
class RunbookCheck:
    label: str
    status: str  # complete | missing | warning | manual | info
    detail: str


@dataclass(frozen=True)
class RunbookSection:
    id: str
    title: str
    intro: str
    checks: tuple[RunbookCheck, ...] = ()
    manual_steps: tuple[str, ...] = ()
    links: tuple[RunbookLink, ...] = ()


@dataclass(frozen=True)
class LiveTestRunbook:
    business: Business | None
    business_lead: BusinessLead | None
    system_critical_issues: tuple[str, ...]
    sections: tuple[RunbookSection, ...]
    business_choices: tuple[tuple[str, str], ...]  # (id, label)


def _check(label: str, ok: bool, *, detail_ok: str, detail_missing: str, warn: bool = False) -> RunbookCheck:
    if ok:
        return RunbookCheck(label, "complete", detail_ok)
    if warn:
        return RunbookCheck(label, "warning", detail_missing)
    return RunbookCheck(label, "missing", detail_missing)


def _summarize_critical_system_issues(db: Session) -> tuple[str, ...]:
    issues: list[str] = []
    for section in build_system_check_sections(db):
        for item in section.items:
            if item.status == "error":
                issues.append(f"{section.title}: {item.name} — {item.value}")
    return tuple(issues)


def _business_lead_for_business(db: Session, business_id: uuid.UUID) -> BusinessLead | None:
    return (
        db.query(BusinessLead)
        .options(joinedload(BusinessLead.partner))
        .filter(BusinessLead.converted_business_id == business_id)
        .order_by(BusinessLead.created_at.desc())
        .first()
    )


def _payment_event_exists(
    db: Session,
    *,
    event_type: str,
    business_id: uuid.UUID | None = None,
    business_lead_id: uuid.UUID | None = None,
) -> bool:
    q = db.query(PaymentEvent.id).filter(PaymentEvent.event_type == event_type)
    if business_id is not None:
        q = q.filter(PaymentEvent.business_id == business_id)
    if business_lead_id is not None:
        q = q.filter(PaymentEvent.business_lead_id == business_lead_id)
    return q.limit(1).first() is not None


def _latest_operational_lead(db: Session, business_id: uuid.UUID) -> Lead | None:
    return (
        db.query(Lead)
        .filter(Lead.business_id == business_id)
        .order_by(Lead.created_at.desc())
        .first()
    )


def _build_business_setup_checks(
    db: Session,
    business: Business | None,
    lead: BusinessLead | None,
) -> tuple[RunbookCheck, ...]:
    if business is None:
        return (
            RunbookCheck(
                "Select a test business",
                "info",
                "Choose a business in the selector above to auto-check pipeline records.",
            ),
        )

    user_link = (
        db.query(BusinessUser)
        .options(joinedload(BusinessUser.user))
        .filter(BusinessUser.business_id == business.id)
        .order_by(BusinessUser.created_at)
        .first()
    )
    invite_status = None
    if user_link is not None:
        invite_status = user_invite_service.latest_invite_status(
            db,
            user_id=user_link.user_id,
            purpose=user_invite_service.BUSINESS_INVITE,
        ).status

    checks: list[RunbookCheck] = []

    if lead is None:
        checks.append(
            RunbookCheck(
                "BusinessLead linked to business",
                "missing",
                "No business_leads row with converted_business_id — create via demo/checkout pipeline.",
            )
        )
    else:
        checks.append(
            _check(
                "BusinessLead exists",
                True,
                detail_ok=f"Lead {lead.id} ({lead.source}, status={lead.status})",
                detail_missing="",
            )
        )
        checks.append(
            _check(
                "Call forwarding terms acknowledged",
                lead.call_forwarding_terms_acknowledged,
                detail_ok="call_forwarding_terms_acknowledged is true",
                detail_missing="Acknowledge on lead detail or demo/checkout before Stripe",
            )
        )
        checks.append(
            _check(
                "Stripe checkout session created",
                bool(lead.stripe_checkout_session_id) or lead.payment_status in {"checkout_created", "paid"},
                detail_ok=f"payment_status={lead.payment_status}",
                detail_missing="Create checkout from admin lead detail or /checkout/growth",
            )
        )
        checkout_completed = _payment_event_exists(
            db,
            event_type="checkout.session.completed",
            business_lead_id=lead.id,
        ) or _payment_event_exists(
            db,
            event_type="checkout.session.completed",
            business_id=business.id,
        )
        checks.append(
            _check(
                "checkout.session.completed processed",
                checkout_completed,
                detail_ok="PaymentEvent recorded",
                detail_missing="Complete Stripe test checkout; confirm webhook to /webhooks/stripe",
            )
        )

    checks.append(
        _check(
            "Business active",
            business.status == "active",
            detail_ok=f"status={business.status}",
            detail_missing=f"status={business.status} — expected active after paid checkout",
            warn=business.status != "active" and business.status not in {"", "pending"},
        )
    )
    checks.append(
        _check(
            "Business user linked",
            user_link is not None,
            detail_ok=f"User {user_link.user.email}" if user_link else "",
            detail_missing="Invite/create business user from admin",
        )
    )
    if user_link is None:
        checks.append(
            RunbookCheck(
                "Business user accepted invite",
                "missing",
                "No linked user yet",
            )
        )
    else:
        accepted = invite_status == "accepted"
        checks.append(
            _check(
                "Business user accepted invite",
                accepted,
                detail_ok="Invite token used or not required",
                detail_missing=f"Invite status: {invite_status or 'unknown'} — resend from business detail",
                warn=invite_status in {"sent", "pending"} if invite_status else False,
            )
        )

    return tuple(checks)


def _build_twilio_backup_checks(db: Session, business: Business | None) -> tuple[RunbookCheck, ...]:
    if business is None:
        return (
            RunbookCheck("Select a test business", "info", "Required for Twilio/Backup Mode checks."),
        )

    onboarding = business_onboarding_service.build_business_onboarding_checklist(db, business)
    key_map = {
        "twilio_number_assigned": "Active Twilio number assigned",
        "mobile_carrier_recorded": "Mobile carrier recorded",
        "forwarding_instructions_sent_or_attempted": "Backup Mode instructions sent/attempted",
        "forwarding_test_passed": "Forwarding test passed",
        "live_launch_verified": "Launch verified",
    }
    checks: list[RunbookCheck] = []
    for item in onboarding.items:
        if item.key not in key_map:
            continue
        status = item.status
        if status == "complete":
            st = "complete"
        elif status == "manual":
            st = "warning"
        elif status == "warning":
            st = "warning"
        else:
            st = "missing"
        checks.append(RunbookCheck(key_map[item.key], st, item.description))

    active_number = None
    for pn in phone_number_service.list_phone_numbers_for_business(db, business.id):
        if pn.status == "active":
            active_number = pn.phone_number
            break
    if active_number:
        checks.append(RunbookCheck("Active number (detail)", "info", active_number))

    return tuple(checks)


def _build_live_call_checks(db: Session, business: Business | None) -> tuple[RunbookCheck, ...]:
    if business is None:
        return ()

    lead = _latest_operational_lead(db, business.id)
    has_inbound = (
        db.query(Message.id)
        .filter(Message.business_id == business.id, Message.direction == "inbound")
        .limit(1)
        .first()
        is not None
    )
    has_notification = (
        db.query(NotificationLog.id)
        .filter(NotificationLog.business_id == business.id)
        .limit(1)
        .first()
        is not None
    )
    ai_ok = False
    ai_detail = "No operational lead yet"
    if lead is not None:
        ai_ok = bool(
            lead.ai_last_analyzed_at
            or lead.summary
            or lead.ai_next_question
            or lead.ai_temperature
        )
        ai_detail = (
            f"lead {lead.id}: ai_last_analyzed_at={lead.ai_last_analyzed_at}, "
            f"summary={'set' if lead.summary else 'empty'}, next_q={'set' if lead.ai_next_question else 'empty'}"
        )

    return (
        _check("Operational lead captured", lead is not None, detail_ok=ai_detail, detail_missing="Run live call/SMS test"),
        _check(
            "Inbound SMS on timeline",
            has_inbound,
            detail_ok="Inbound Message row exists",
            detail_missing='Reply "I need help with a leak." after text-back',
        ),
        _check(
            "AI fields updated",
            ai_ok,
            detail_ok=ai_detail,
            detail_missing="Confirm OPENAI_ENABLED and inbound SMS webhook; check lead detail",
            warn=has_inbound and not ai_ok,
        ),
        _check(
            "Staff notification attempted",
            has_notification,
            detail_ok="notification_logs row for this business",
            detail_missing="Set notification_email/phone; check SMTP/Twilio staff SMS config",
            warn=not has_notification,
        ),
    )


def _build_partner_checks(
    db: Session,
    business: Business | None,
    lead: BusinessLead | None,
) -> tuple[RunbookCheck, ...]:
    if business is None:
        return (
            RunbookCheck(
                "Partner referral test",
                "info",
                "Optional — only if test customer used a partner referral link.",
            ),
        )

    if lead is None or lead.partner_id is None:
        return (
            RunbookCheck(
                "Referred partner attached",
                "info",
                "No partner on BusinessLead — skip partner/commission section for direct signups.",
            ),
        )

    partner_name = lead.partner.display_name if lead.partner else str(lead.partner_id)
    pc = (
        db.query(PartnerCustomer)
        .filter(
            PartnerCustomer.partner_id == lead.partner_id,
            PartnerCustomer.business_lead_id == lead.id,
        )
        .first()
    )
    commissions = (
        db.query(Commission)
        .filter(Commission.business_id == business.id, Commission.partner_id == lead.partner_id)
        .all()
    )
    invoice_paid = _payment_event_exists(db, event_type="invoice.paid", business_id=business.id)

    return (
        _check(
            "PartnerCustomer record",
            pc is not None,
            detail_ok=f"status={pc.status}" if pc else "",
            detail_missing="Expected partner_customers row from referred checkout",
        ),
        _check(
            "Referred partner attached",
            True,
            detail_ok=f"{partner_name} ({lead.referral_code})",
            detail_missing="",
        ),
        _check(
            "invoice.paid processed",
            invoice_paid,
            detail_ok="PaymentEvent invoice.paid recorded",
            detail_missing="Stripe subscription first invoice must pay; webhook /webhooks/stripe",
        ),
        _check(
            "Commission rows created",
            len(commissions) > 0,
            detail_ok=f"{len(commissions)} commission(s); statuses: {', '.join({c.status for c in commissions})}",
            detail_missing="Commissions created on invoice.paid when partner attribution exists",
        ),
    )


def build_live_test_runbook(db: Session, *, business_id: uuid.UUID | None = None) -> LiveTestRunbook:
    business: Business | None = None
    lead: BusinessLead | None = None
    if business_id is not None:
        try:
            business = get_business(db, business_id)
            lead = _business_lead_for_business(db, business_id)
        except ValueError:
            business = None

    choices: list[tuple[str, str]] = []
    for b in list_businesses(db)[:40]:
        choices.append((str(b.id), b.name))

    system_issues = _summarize_critical_system_issues(db)

    sections: list[RunbookSection] = [
        RunbookSection(
            id="prerequisites",
            title="1. System prerequisites",
            intro="Resolve platform configuration before testing a customer. This page does not call Stripe, Twilio, or OpenAI.",
            checks=tuple(
                [
                    RunbookCheck(
                        "System Check errors",
                        "complete" if not system_issues else "missing",
                        "No error-level checks" if not system_issues else "; ".join(system_issues[:5])
                        + ("…" if len(system_issues) > 5 else ""),
                    ),
                ]
            ),
            links=(
                RunbookLink("Open System Check", "/admin/system-check"),
                RunbookLink("Open A2P Packet", "/admin/a2p-packet"),
            ),
        ),
        RunbookSection(
            id="business-setup",
            title="2. Test business setup",
            intro="Stripe test card: 4242 4242 4242 4242, any future expiry, any CVC. Use Stripe test mode keys.",
            checks=_build_business_setup_checks(db, business, lead),
            links=(
                RunbookLink("Prospect pipeline", "/admin/business-leads"),
                RunbookLink("Businesses", "/admin/businesses"),
            )
            + (
                (RunbookLink("This business detail", f"/admin/businesses/{business.id}"),)
                if business
                else ()
            )
            + (
                (RunbookLink("Business lead detail", f"/admin/business-leads/{lead.id}"),)
                if lead
                else ()
            ),
        ),
        RunbookSection(
            id="twilio-backup",
            title="3. Twilio & Backup Mode setup",
            intro="Assign Twilio number in admin; customer enables carrier forwarding (Backup Mode). Mark forwarding test passed after live test.",
            checks=_build_twilio_backup_checks(db, business),
            links=(
                RunbookLink("Phone numbers (via business detail)", f"/admin/businesses/{business.id}")
                if business
                else RunbookLink("Businesses", "/admin/businesses"),
            ),
        ),
        RunbookSection(
            id="live-call-sms",
            title="4. Live call & SMS test",
            intro="Manual steps — perform on a real phone. DB checks below update when you select a business.",
            manual_steps=(
                "Call the customer-facing business mobile number from a separate phone.",
                "Do not answer the business line.",
                "Confirm the caller receives the LeadCareAI missed-call text-back SMS.",
                'Reply as the customer: "I need help with a leak."',
                "Confirm lead in business dashboard and admin operational leads.",
                "Confirm inbound SMS on lead message timeline.",
                "Confirm AI summary / next question on lead detail.",
                "Confirm staff email/SMS notification attempted (notification_logs).",
            ),
            checks=_build_live_call_checks(db, business),
            links=(
                (
                    RunbookLink(
                        "Mark launch verified",
                        f"/admin/businesses/{business.id}#live-launch-test",
                    ),
                )
                if business
                else ()
            ),
        ),
        RunbookSection(
            id="partner-commission",
            title="5. Partner & commission test (if referred)",
            intro="Only when the test signup used a partner referral link (?ref= or /r/CODE).",
            checks=_build_partner_checks(db, business, lead),
            links=(
                RunbookLink("Commissions", "/admin/commissions"),
                RunbookLink("Partners", "/admin/partners"),
            ),
        ),
        RunbookSection(
            id="final",
            title="6. Final verification",
            intro="Review records and mark launch verified on the business detail page when the full path succeeds.",
            manual_steps=(
                "Confirm onboarding checklist shows Ready for launch: Yes.",
                "Complete live launch test section on business detail; add notes; Mark launch verified.",
                "Do not mark verified until forwarding test passed and notifications configured.",
            ),
            links=_final_links(business, lead),
        ),
    ]

    return LiveTestRunbook(
        business=business,
        business_lead=lead,
        system_critical_issues=system_issues,
        sections=tuple(sections),
        business_choices=tuple(choices),
    )


def _final_links(
    business: Business | None,
    lead: BusinessLead | None,
) -> tuple[RunbookLink, ...]:
    links: list[RunbookLink] = [
        RunbookLink("Notification logs", "/admin/notification-logs"),
        RunbookLink("Commissions", "/admin/commissions"),
        RunbookLink("User access", "/admin/user-access"),
        RunbookLink("Partners", "/admin/partners"),
    ]
    if business is not None:
        links.insert(0, RunbookLink("Business detail", f"/admin/businesses/{business.id}"))
        links.insert(1, RunbookLink("Launch test on business", f"/admin/businesses/{business.id}#live-launch-test"))
    if lead is not None and lead.partner_id is not None:
        links.append(RunbookLink("Partner dashboard", "/partner/dashboard"))
    return tuple(links)
