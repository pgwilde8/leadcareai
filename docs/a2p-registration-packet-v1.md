# A2P 10DLC registration packet (V1)

Copy/paste reference for Twilio (and carrier) campaign registration for LeadCareAI missed-call recovery SMS.

**Not legal advice.** **Does not guarantee approval.** Confirm current Twilio/TCR field labels and carrier rules before submission.

**Admin UI:** `/admin/a2p-packet` (session admin only)  
**Source of truth in code:** `app/services/a2p_packet_service.py`

## Use case / category

| Field | Recommendation |
|-------|----------------|
| **Primary category** | Customer Care |
| **Notes** | Missed-call text-back and service inquiry intake for local businesses. If reviewers suggest a mixed/low-volume label, follow their current dropdown—do not assume approval. |

## Campaign description

```
LeadCareAI missed-call recovery for local service businesses. When a consumer calls a participating business and the call is not answered, the business may send an automated SMS text-back inviting the consumer to describe their service need. Follow-up messages help qualify the inquiry (service type, location, urgency) and may include brief status updates related to that same request. Messages are service-related and tied to the consumer's inquiry with that business—not unsolicited third-party marketing lists.
```

## Sample messages

Replace `[Business Name]` with the business SMS signature or public name.

1. `[Business Name]: Sorry we missed your call. What can we help with today? Reply STOP to opt out.`
2. `[Business Name]: Thanks for your message. What service is needed and what town are you in? Reply STOP to opt out.`
3. `[Business Name]: Thanks for reaching out. This sounds urgent. What service do you need help with? If this is dangerous or life-threatening, call 911. Reply STOP to opt out.`
4. `[Business Name]: Thanks. We shared this with the team. Would you prefer a callback today or tomorrow? Reply STOP to opt out.`
5. `[Business Name]: Thanks for your message. Are you available for a callback this afternoon? Reply STOP to opt out.`

These align with platform templates in `app/services/sms_service.py` (with `[Business Name]` standing in for `{label}`).

## Opt-in explanation

```
End users may receive messages after they call a participating business's published phone number and the call is not answered (missed-call text-back), or after they text the business and continue a service conversation. Consent is obtained in the context of requesting service from that business—not from purchased lead lists or unrelated marketing opt-ins. Businesses must maintain any additional consent records required by applicable law.
```

## Opt-out explanation (STOP)

```
Recipients may reply STOP to opt out of further SMS from that business's conversation thread. After STOP, the recipient may receive one final confirmation message. Opt-out requests must be honored promptly.
```

## HELP explanation

```
Recipients may reply HELP for assistance. HELP responses should identify the business and provide a support path (business phone or email where appropriate). Platform support: paul@leadcareai.com. See SMS Terms at the SMS Terms URL below.
```

## Policy URLs (production)

| Document | URL |
|----------|-----|
| Privacy Policy | https://leadcareai.com/privacy |
| Terms of Service | https://leadcareai.com/terms |
| SMS Terms | https://leadcareai.com/sms-terms |

Staging/dev: use your `PUBLIC_BASE_URL` or `APP_BASE_URL` when testing reachability; submit production URLs to Twilio.

## Third-party marketing (privacy / campaign)

```
Mobile opt-in data and SMS consent are not sold, rented, or shared with third parties for their marketing or promotional purposes.
```

Also published on `/privacy` and `/sms-terms`.

## Message content flags

| Flag | Recommendation | Notes |
|------|----------------|-------|
| **Embedded links** | Usually **No** for default consumer intake | Platform default missed-call/intake SMS do not include URLs. **Yes** only if custom business copy or approved templates include links. Staff dashboard links may need a **separate** staff-notification campaign. |
| **Phone numbers in body** | **Maybe** / case-by-case | Default templates do not embed callback numbers. **Yes** if custom messages include explicit callback numbers. |
| **Lending** | **No** | Not a lending program. |
| **Age-gated** | **No** | Not age-gated content. |

Revisit flags when a business saves custom `missed_call_textback_message` copy.

## Per-business brand / campaign notes

- Register or associate a **brand** for each business legal/DBA name on outbound SMS.
- Use the business's real name in sample messages.
- Ensure public legal URLs match submitted links.
- Complete Backup Mode / forwarding setup and [live launch smoke test](live-launch-smoke-test-v1.md) before production traffic.
- **Staff alert SMS** (to business employees) may require a separate campaign from consumer intake.
- Update message flags if custom templates add links or phone numbers.

## Pre-submission checklist

- [ ] Privacy Policy URL live
- [ ] Terms URL live
- [ ] SMS Terms URL live
- [ ] Campaign description matches live behavior
- [ ] Sample messages include STOP
- [ ] HELP handling documented and tested
- [ ] Opt-in explanation matches call/text-back flow
- [ ] Third-party marketing disclaimer included
- [ ] Message content flags match actual templates
- [ ] Brand identity matches business name on SMS
- [ ] Call forwarding live test passed

## Related docs

- [legal-pages-v1.md](legal-pages-v1.md) — public policies
- [call-forwarding-requirements-v1.md](call-forwarding-requirements-v1.md) — Backup Mode / forwarding
- [business-notifications-v1.md](business-notifications-v1.md) — staff email/SMS (may be separate campaign)

## Limitations

- No Twilio API integration or automated registration in V1
- No change to SMS sending logic or customer templates
- Approval not guaranteed; carriers and Twilio rules change
- Consumer campaign copy may not cover staff-only notification SMS
