"""Twilio A2P 10DLC registration copy packet (admin reference only — no API calls)."""

from __future__ import annotations

from dataclasses import dataclass

PRODUCTION_SITE_BASE = "https://leadcareai.com"

THIRD_PARTY_MARKETING_WORDING = (
    "Mobile opt-in data and SMS consent are not sold, rented, or shared with third parties "
    "for their marketing or promotional purposes."
)

CAMPAIGN_DESCRIPTION = (
    "LeadCareAI missed-call recovery for local service businesses. When a consumer calls a "
    "participating business and the call is not answered, the business may send an automated SMS "
    "text-back inviting the consumer to describe their service need. Follow-up messages help qualify "
    "the inquiry (service type, location, urgency) and may include brief status updates related to "
    "that same request. Messages are service-related and tied to the consumer's inquiry with that "
    "business—not unsolicited third-party marketing lists."
)

USE_CASE_CATEGORY = "Customer Care"
USE_CASE_CATEGORY_NOTES = (
    "Twilio/TCR categories vary by carrier review. Customer Care fits missed-call follow-up and "
    "service inquiry intake. If reviewers request a mixed/low-volume label, use their current "
    "dropdown guidance—do not assume approval."
)

SAMPLE_MESSAGES: tuple[str, ...] = (
    "[Business Name]: Sorry we missed your call. What can we help with today? Reply STOP to opt out.",
    "[Business Name]: Thanks for your message. What service is needed and what town are you in? Reply STOP to opt out.",
    "[Business Name]: Thanks for reaching out. This sounds urgent. What service do you need help with? "
    "If this is dangerous or life-threatening, call 911. Reply STOP to opt out.",
    "[Business Name]: Thanks. We shared this with the team. Would you prefer a callback today or tomorrow? "
    "Reply STOP to opt out.",
    "[Business Name]: Thanks for your message. Are you available for a callback this afternoon? Reply STOP to opt out.",
)

OPT_IN_EXPLANATION = (
    "End users may receive messages after they call a participating business's published phone number "
    "and the call is not answered (missed-call text-back), or after they text the business and continue "
    "a service conversation. Consent is obtained in the context of requesting service from that business—not "
    "from purchased lead lists or unrelated marketing opt-ins. Businesses must maintain any additional consent "
    "records required by applicable law."
)

OPT_OUT_EXPLANATION = (
    "Recipients may reply STOP to opt out of further SMS from that business's conversation thread. "
    "After STOP, the recipient may receive one final confirmation message. Opt-out requests must be honored promptly."
)

HELP_EXPLANATION = (
    "Recipients may reply HELP for assistance. HELP responses should identify the business and provide a "
    "support path (business phone or email where appropriate). Platform support: paul@leadcareai.com. "
    "See SMS Terms at the SMS Terms URL below."
)

SUBMISSION_WARNING = (
    "Confirm field labels, campaign types, and brand/campaign rules with Twilio and your current carrier "
    "requirements before live submission. Registration approval is not guaranteed. This packet is a V1 draft "
    "for copy consistency—not legal advice."
)

PER_BUSINESS_NOTES: tuple[str, ...] = (
    "Register or associate a brand for each business legal/DBA name used on outbound SMS.",
    "Use the business's public name in sample messages (replace [Business Name]).",
    "Ensure Privacy, Terms, and SMS Terms URLs are live and match what you submit.",
    "Complete Backup Mode / call-forwarding setup and live launch verification before production traffic.",
    "Staff alert SMS to business employees may require a separate campaign or use case—consumer intake is the primary campaign described here.",
    "If a business uses a custom missed-call message with URLs or phone numbers, update message content flags accordingly.",
)

REGISTRATION_CHECKLIST: tuple[str, ...] = (
    "Privacy Policy URL submitted and publicly reachable",
    "Terms of Service URL submitted and publicly reachable",
    "SMS Terms URL submitted and publicly reachable",
    "Campaign description matches live message behavior",
    "All sample messages include STOP opt-out language",
    "HELP handling documented and tested",
    "Opt-in explanation matches call/text-back flow",
    "Third-party marketing sharing disclaimer included (not sold/shared for third-party marketing)",
    "Message content flags match actual templates (links, phone numbers)",
    "Brand displays correct business identity to end users",
    "Call forwarding live test passed for the business line",
)


@dataclass(frozen=True)
class MessageContentFlags:
    embedded_links: str
    phone_numbers: str
    lending: str
    age_gated: str
    notes: str


@dataclass(frozen=True)
class A2PPacket:
    site_base: str
    campaign_description: str
    use_case_category: str
    use_case_category_notes: str
    sample_messages: tuple[str, ...]
    opt_in_explanation: str
    opt_out_explanation: str
    help_explanation: str
    privacy_url: str
    terms_url: str
    sms_terms_url: str
    third_party_marketing_wording: str
    message_flags: MessageContentFlags
    per_business_notes: tuple[str, ...]
    registration_checklist: tuple[str, ...]
    submission_warning: str


def build_a2p_packet(*, site_base: str | None = None) -> A2PPacket:
    base = (site_base or PRODUCTION_SITE_BASE).rstrip("/")
    return A2PPacket(
        site_base=base,
        campaign_description=CAMPAIGN_DESCRIPTION,
        use_case_category=USE_CASE_CATEGORY,
        use_case_category_notes=USE_CASE_CATEGORY_NOTES,
        sample_messages=SAMPLE_MESSAGES,
        opt_in_explanation=OPT_IN_EXPLANATION,
        opt_out_explanation=OPT_OUT_EXPLANATION,
        help_explanation=HELP_EXPLANATION,
        privacy_url=f"{base}/privacy",
        terms_url=f"{base}/terms",
        sms_terms_url=f"{base}/sms-terms",
        third_party_marketing_wording=THIRD_PARTY_MARKETING_WORDING,
        message_flags=MessageContentFlags(
            embedded_links=(
                "Usually **No** for default consumer missed-call and intake templates (no URLs in platform defaults). "
                "Select **Yes** only if approved templates or custom business messages include links (for example a "
                "booking page). Staff-only alert SMS may include dashboard links—those may belong in a separate campaign."
            ),
            phone_numbers=(
                "**Maybe / case-by-case.** Default platform templates do not embed callback phone numbers in the SMS body. "
                "Select **Yes** if custom business messages include a click-to-call number or explicit callback number."
            ),
            lending="**No** — not a lending or loan solicitation program.",
            age_gated="**No** — not age-gated content.",
            notes=(
                "Align flags with the exact messages the business will send after onboarding. Revisit flags if custom "
                "missed-call text-back copy changes."
            ),
        ),
        per_business_notes=PER_BUSINESS_NOTES,
        registration_checklist=REGISTRATION_CHECKLIST,
        submission_warning=SUBMISSION_WARNING,
    )
