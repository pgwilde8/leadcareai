"""Mobile-first call forwarding onboarding (guide, track, verify — no carrier API)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.business import (
    CALL_FORWARDING_STATUSES,
    CUSTOMER_PHONE_CARRIERS,
    Business,
)
from app.models.phone_number import PhoneNumber
from app.services.business_service import get_business
from app.services.phone_number_service import list_phone_numbers_for_business

CARRIER_LABELS: dict[str, str] = {
    "verizon": "Verizon",
    "att": "AT&T",
    "t_mobile": "T-Mobile",
    "metro_tmobile": "Metro by T-Mobile",
    "cricket": "Cricket",
    "boost": "Boost Mobile",
    "consumer_cellular": "Consumer Cellular",
    "other": "Other / Not sure",
}

CARRIER_CAVEAT = "Carrier settings and plan behavior may vary."

TMOBILE_METRO_CAVEAT = "Common T-Mobile / Metro-style codes. Your carrier or plan may vary."

CONFIDENCE_VERIFIED = "verified"
CONFIDENCE_COMMON_UNVERIFIED = "common_but_unverified"
CONFIDENCE_CONTACT_CARRIER = "contact_carrier"

CONFIDENCE_LABELS: dict[str, str] = {
    CONFIDENCE_VERIFIED: (
        "Carrier-specific codes from published self-service guidance. Your plan may still vary."
    ),
    CONFIDENCE_COMMON_UNVERIFIED: (
        "Common examples only — confirm with your carrier before relying on these."
    ),
    CONFIDENCE_CONTACT_CARRIER: (
        "Use your phone settings or contact your carrier — exact codes are not verified here."
    ),
}

COMMON_EXAMPLES_DISCLAIMER = (
    "Common examples only — confirm with your carrier before relying on these."
)

NO_UNIVERSAL_COMPATIBILITY = (
    "LeadCareAI does not guarantee that any dial code works on every carrier, plan, or phone."
)

CONTACT_CARRIER_RECOMMENDATION = (
    "Use your phone's call forwarding settings first, or contact your carrier and ask them "
    "to forward unanswered or busy calls to your LeadCareAI number."
)

INCOMPLETE_BANNER_MESSAGE = (
    "Backup Mode setup is not complete. Leads may not be captured until "
    "your call-forwarding test passes."
)

BACKUP_MODE_SUBTITLE = (
    "Use your phone's built-in call forwarding to catch missed calls with LeadCareAI."
)

BACKUP_MODE_PLAIN_LANGUAGE = (
    "Your phone still rings like normal. If you do not answer, your line is busy, "
    "or your phone is unreachable, your carrier forwards the call to your LeadCareAI "
    "number. LeadCareAI texts the caller, captures the job details, and alerts your team."
)

SETUP_CHECKLIST_ITEMS: tuple[str, ...] = (
    "My LeadCareAI number is assigned.",
    "My customer-facing line is mobile.",
    "I enabled missed/busy/unanswered call forwarding.",
    "I called my business number from another phone.",
    "I did not answer.",
    "I received the LeadCareAI text-back.",
    "I saw the lead in my dashboard.",
    "Admin marked my test passed.",
)

ALL_CALLS_FORWARDING_WARNING = (
    "Only use all-calls forwarding if you want every call to go to LeadCareAI "
    "before your phone rings."
)

TESTING_STEPS: tuple[str, ...] = (
    "Call your customer-facing business number from another phone.",
    "Let it ring without answering (or test while on another call for busy forwarding).",
    "Confirm the caller receives a LeadCareAI text-back.",
    "Confirm a new lead appears in your LeadCareAI dashboard.",
    "Ask support to mark your forwarding test passed when verified.",
)

CAUTIOUS_PHONE_SETTINGS: tuple[str, ...] = (
    "iPhone: Settings → Phone → Call Forwarding",
    "Android: Phone app → Settings → Calls → Call forwarding",
)

CARRIER_SUPPORT_SCRIPT = (
    "Please help me forward unanswered or busy calls from my mobile business line to my "
    "LeadCareAI number: {number}. I do not want to forward all calls unless I ask for that."
)


def _carrier_support_script(display_number: str | None) -> str:
    number = display_number or "[LeadCareAI number]"
    return CARRIER_SUPPORT_SCRIPT.format(number=number)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _leadcare_digits(phone_number: str | None) -> tuple[str | None, str | None]:
    """Return (11-digit with leading 1, 10-digit NANP) for dial-code examples."""
    if not phone_number:
        return None, None
    digits = "".join(character for character in phone_number if character.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return digits, digits[1:]
    if len(digits) == 10:
        return "1" + digits, digits
    if digits:
        return digits, digits
    return None, None


def validate_carrier(carrier: str | None) -> str | None:
    if carrier is None:
        return None
    key = carrier.strip().lower()
    if not key:
        return None
    if key not in CUSTOMER_PHONE_CARRIERS:
        raise ValueError("Please select a valid mobile carrier")
    return key


def validate_forwarding_status(status: str) -> str:
    value = status.strip().lower()
    if value not in CALL_FORWARDING_STATUSES:
        raise ValueError(f"Invalid call forwarding status: {status!r}")
    return value


def is_forwarding_setup_complete(business: Business) -> bool:
    return business.customer_phone_forwarding_status == "test_passed"


def carrier_display_label(carrier: str | None) -> str:
    if not carrier:
        return "Not selected"
    return CARRIER_LABELS.get(carrier, carrier.replace("_", " ").title())


def format_phone_for_display(phone_number: str) -> str:
    """Format E.164 for business-facing display (e.g. +1 555 987 6543)."""
    digits = "".join(character for character in phone_number if character.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return f"+1 {digits[1:4]} {digits[4:7]} {digits[7:]}"
    if len(digits) == 10:
        return f"+1 {digits[0:3]} {digits[3:6]} {digits[6:]}"
    return phone_number.strip()


def get_assigned_leadcare_number(db: Session, business_id: uuid.UUID) -> PhoneNumber | None:
    """Primary active LeadCareAI/Twilio number for this business."""
    numbers = list_phone_numbers_for_business(db, business_id)
    for record in numbers:
        if record.status == "active":
            return record
    return numbers[0] if numbers else None


def _gsm_activation_code(feature: str, eleven: str | None, *, double_star: bool) -> str:
    """Build GSM activation dial string (single- or double-star per carrier guidance)."""
    if eleven:
        prefix = "**" if double_star else "*"
        return f"{prefix}{feature}*{eleven}#"
    prefix = "**" if double_star else "*"
    return f"{prefix}{feature}*1XXXXXXXXXX#"


def _gsm_conditional_guide(
    *,
    carrier_key: str,
    carrier_label: str,
    eleven: str | None,
    display_number: str | None,
    mvno_note: str | None = None,
    double_star_activation: bool = False,
    caveat: str | None = None,
) -> dict[str, Any]:
    placeholder = "your LeadCareAI number (11 digits, usually starting with 1)"
    no_answer_on = _gsm_activation_code("61", eleven, double_star=double_star_activation)
    busy_on = _gsm_activation_code("67", eleven, double_star=double_star_activation)
    unreachable_on = _gsm_activation_code("62", eleven, double_star=double_star_activation)
    all_calls_on = _gsm_activation_code("21", eleven, double_star=double_star_activation)

    notes = [
        "Open the phone dialer on the mobile line your customers call.",
        "Dial each code, then press Call. Wait for a confirmation tone or message.",
    ]
    if mvno_note:
        notes.insert(0, mvno_note)

    return {
        "carrier_key": carrier_key,
        "carrier_label": carrier_label,
        "style": "gsm_conditional",
        "confidence_level": CONFIDENCE_VERIFIED,
        "confidence_label": CONFIDENCE_LABELS[CONFIDENCE_VERIFIED],
        "no_universal_compatibility": NO_UNIVERSAL_COMPATIBILITY,
        "caveat": caveat or CARRIER_CAVEAT,
        "recommended_approach": (
            "Set up conditional forwarding for no answer, busy, and unreachable. "
            "Your phone rings first; LeadCareAI only receives calls you miss."
        ),
        "activation_note": (
            "T-Mobile self-service codes often start with two asterisks (for example **61*). "
            "Dial the full code, then press Call."
            if double_star_activation
            else None
        ),
        "conditional_codes": [
            {"label": "No answer", "on": no_answer_on, "off": "##61#"},
            {"label": "Busy", "on": busy_on, "off": "##67#"},
            {"label": "Unreachable", "on": unreachable_on, "off": "##62#"},
        ],
        "reset_code": "##004#",
        "optional_all_calls": {
            "on": all_calls_on,
            "off": "##21#",
            "warning": ALL_CALLS_FORWARDING_WARNING,
        },
        "testing_steps": list(TESTING_STEPS),
        "display_number": display_number,
        "number_placeholder": placeholder,
        "notes": notes,
    }


def _verizon_guide(*, ten: str | None, display_number: str | None) -> dict[str, Any]:
    if ten:
        conditional_example = f"*71{ten}"
        all_calls_example = f"*72{ten}"
    else:
        conditional_example = "*71XXXXXXXXXX"
        all_calls_example = "*72XXXXXXXXXX"

    return {
        "carrier_key": "verizon",
        "carrier_label": "Verizon",
        "style": "verizon",
        "confidence_level": CONFIDENCE_VERIFIED,
        "confidence_label": CONFIDENCE_LABELS[CONFIDENCE_VERIFIED],
        "no_universal_compatibility": NO_UNIVERSAL_COMPATIBILITY,
        "caveat": CARRIER_CAVEAT,
        "recommended_approach": (
            "Use Verizon conditional forwarding (no-answer/busy transfer) so your phone "
            "rings first. Dial from the mobile line customers call."
        ),
        "verizon_conditional": {
            "label": "Conditional / no-answer-busy transfer (recommended)",
            "code": conditional_example,
            "detail": "Dial *71 plus your 10-digit LeadCareAI number (no spaces), then press Call.",
        },
        "optional_all_calls": {
            "on": all_calls_example,
            "off": "*73",
            "warning": ALL_CALLS_FORWARDING_WARNING,
        },
        "testing_steps": list(TESTING_STEPS),
        "display_number": display_number,
        "notes": [
            "You can also use the My Verizon app under call forwarding settings.",
            "Business and prepaid plans may use different menus — contact Verizon if codes fail.",
        ],
    }


def _cautious_guide(
    *,
    carrier_key: str,
    carrier_label: str,
    display_number: str | None,
) -> dict[str, Any]:
    script = _carrier_support_script(display_number)
    return {
        "carrier_key": carrier_key,
        "carrier_label": carrier_label,
        "style": "cautious",
        "confidence_level": CONFIDENCE_CONTACT_CARRIER,
        "confidence_label": CONFIDENCE_LABELS[CONFIDENCE_CONTACT_CARRIER],
        "no_universal_compatibility": NO_UNIVERSAL_COMPATIBILITY,
        "caveat": CARRIER_CAVEAT,
        "recommended_approach": CONTACT_CARRIER_RECOMMENDATION,
        "phone_settings": list(CAUTIOUS_PHONE_SETTINGS),
        "carrier_support_script": script,
        "testing_steps": list(TESTING_STEPS),
        "display_number": display_number,
        "notes": [script],
    }


def _mvno_cautious_guide(
    *,
    carrier_key: str,
    carrier_label: str,
    eleven: str | None,
    display_number: str | None,
    mvno_note: str,
) -> dict[str, Any]:
    """MVNOs without verified official codes in-repo — settings/carrier first, optional examples."""
    script = _carrier_support_script(display_number)
    optional_codes = [
        {"label": "No answer", "on": _gsm_activation_code("61", eleven, double_star=False), "off": "##61#"},
        {"label": "Busy", "on": _gsm_activation_code("67", eleven, double_star=False), "off": "##67#"},
        {"label": "Unreachable", "on": _gsm_activation_code("62", eleven, double_star=False), "off": "##62#"},
    ]
    return {
        "carrier_key": carrier_key,
        "carrier_label": carrier_label,
        "style": "mvno_cautious",
        "confidence_level": CONFIDENCE_CONTACT_CARRIER,
        "confidence_label": CONFIDENCE_LABELS[CONFIDENCE_CONTACT_CARRIER],
        "no_universal_compatibility": NO_UNIVERSAL_COMPATIBILITY,
        "caveat": CARRIER_CAVEAT,
        "recommended_approach": CONTACT_CARRIER_RECOMMENDATION,
        "phone_settings": list(CAUTIOUS_PHONE_SETTINGS),
        "carrier_support_script": script,
        "optional_common_codes": {
            "confidence_level": CONFIDENCE_COMMON_UNVERIFIED,
            "confidence_label": CONFIDENCE_LABELS[CONFIDENCE_COMMON_UNVERIFIED],
            "disclaimer": COMMON_EXAMPLES_DISCLAIMER,
            "codes": optional_codes,
            "reset_code": "##004#",
            "mvno_note": mvno_note,
        },
        "testing_steps": list(TESTING_STEPS),
        "display_number": display_number,
        "notes": [mvno_note, script],
    }


def get_carrier_guidance(
    carrier: str | None,
    leadcare_number: str | None = None,
) -> dict[str, Any]:
    """Carrier-specific Backup Mode guide for templates (not universal guarantees)."""
    eleven, ten = _leadcare_digits(leadcare_number)
    display = format_phone_for_display(leadcare_number) if leadcare_number else None

    if carrier == "t_mobile":
        return _gsm_conditional_guide(
            carrier_key="t_mobile",
            carrier_label="T-Mobile",
            eleven=eleven,
            display_number=display,
            double_star_activation=True,
            caveat=TMOBILE_METRO_CAVEAT,
        )
    if carrier == "metro_tmobile":
        return _gsm_conditional_guide(
            carrier_key="metro_tmobile",
            carrier_label="Metro by T-Mobile",
            eleven=eleven,
            display_number=display,
            mvno_note="Metro uses T-Mobile's network; these are common T-Mobile-style codes but not guaranteed.",
            double_star_activation=True,
            caveat=TMOBILE_METRO_CAVEAT,
        )
    if carrier == "cricket":
        return _mvno_cautious_guide(
            carrier_key="cricket",
            carrier_label="Cricket",
            eleven=eleven,
            display_number=display,
            mvno_note=(
                "Cricket is an MVNO. We have not verified Cricket-specific dial codes in our docs — "
                "contact Cricket or use phone settings."
            ),
        )
    if carrier == "boost":
        return _mvno_cautious_guide(
            carrier_key="boost",
            carrier_label="Boost Mobile",
            eleven=eleven,
            display_number=display,
            mvno_note=(
                "Boost is an MVNO. We have not verified Boost-specific dial codes in our docs — "
                "contact Boost or use phone settings."
            ),
        )
    if carrier == "verizon":
        return _verizon_guide(ten=ten, display_number=display)
    if carrier == "att":
        return _cautious_guide(
            carrier_key="att",
            carrier_label="AT&T",
            display_number=display,
        )
    if carrier == "consumer_cellular":
        return _cautious_guide(
            carrier_key="consumer_cellular",
            carrier_label="Consumer Cellular",
            display_number=display,
        )
    return _cautious_guide(
        carrier_key=carrier or "other",
        carrier_label=carrier_display_label(carrier),
        display_number=display,
    )


def update_call_forwarding_profile(
    db: Session,
    business_id: uuid.UUID,
    *,
    customer_phone_is_mobile: bool | None,
    customer_phone_carrier: str | None,
    can_access_phone_during_onboarding: bool | None = None,
) -> Business:
    business = get_business(db, business_id)
    if customer_phone_is_mobile is False:
        raise ValueError(
            "LeadCareAI V1 requires a mobile customer-facing line that supports call forwarding. "
            "Office phone systems and unsupported carriers need manual review."
        )

    carrier = validate_carrier(customer_phone_carrier)
    business.customer_phone_is_mobile = customer_phone_is_mobile
    business.customer_phone_carrier = carrier

    if can_access_phone_during_onboarding is False:
        note = "Customer reported they cannot access the mobile line during onboarding."
        existing = (business.customer_phone_forwarding_notes or "").strip()
        if note not in existing:
            business.customer_phone_forwarding_notes = (
                f"{existing}\n{note}".strip() if existing else note
            )

    if carrier and business.customer_phone_forwarding_status == "not_started":
        business.customer_phone_forwarding_status = "instructions_sent"

    db.flush()
    return business


def mark_instructions_sent(db: Session, business_id: uuid.UUID) -> Business:
    business = get_business(db, business_id)
    if business.customer_phone_forwarding_status == "not_started":
        business.customer_phone_forwarding_status = "instructions_sent"
        db.flush()
    return business


def mark_customer_attempted(db: Session, business_id: uuid.UUID) -> Business:
    business = get_business(db, business_id)
    if business.customer_phone_forwarding_status == "test_passed":
        return business
    business.customer_phone_forwarding_status = "customer_attempted"
    db.flush()
    return business


def admin_update_forwarding(
    db: Session,
    business_id: uuid.UUID,
    *,
    status: str,
    notes: str | None = None,
) -> Business:
    business = get_business(db, business_id)
    new_status = validate_forwarding_status(status)
    business.customer_phone_forwarding_status = new_status
    if notes is not None:
        business.customer_phone_forwarding_notes = _strip(notes)
    if new_status == "test_passed":
        business.call_forwarding_tested_at = _now()
    db.flush()
    return business
