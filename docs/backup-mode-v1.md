# Backup Mode (V1)

Backup Mode is the customer-friendly name for **call forwarding** to LeadCareAI: a mobile missed-call safety net, not a separate phone product.

## What Backup Mode means

When Backup Mode is **on** (call forwarding enabled on the customer’s mobile line), missed, busy, or unreachable calls to the business number are sent to the assigned LeadCareAI/Twilio number. LeadCareAI then:

- Texts the caller
- Captures job details
- Saves the lead in the dashboard
- Alerts the business team

When Backup Mode is **off** (forwarding disabled), calls ring the owner’s phone as usual.

**Plain-language explanation (in-app):**

> Your phone still rings like normal. If you do not answer, your line is busy, or your phone is unreachable, your carrier forwards the call to your LeadCareAI number. LeadCareAI texts the caller, captures the job details, and alerts your team.

## Mobile-first requirement

V1 self-serve onboarding requires a **mobile** customer-facing line with carrier-supported call forwarding. Landlines, PBX, Google Voice, Grasshopper, RingCentral, and similar VoIP may need manual review. See [call-forwarding-requirements-v1.md](./call-forwarding-requirements-v1.md).

## Conditional vs all-calls forwarding

| Type | Behavior | Recommendation |
|------|----------|----------------|
| **Conditional** (no answer / busy / unreachable) | Phone rings first; LeadCareAI gets calls you miss | **Recommended** for Backup Mode |
| **All calls** (`*21` / `*72` style) | Every call goes to LeadCareAI before your phone rings | Optional only when intentional |

Always warn: *Only use all-calls forwarding if you want every call to go to LeadCareAI before your phone rings.*

## Carrier-specific guidance (caveat)

**Every section includes:** *Carrier settings and plan behavior may vary.*

LeadCareAI does not guarantee that any dial code works on every carrier, plan, or phone.

LeadCareAI does not operate carrier APIs and cannot enable or disable forwarding remotely.

## Guidance confidence levels

| Level | Carriers | Meaning |
|-------|----------|---------|
| **Verified** | T-Mobile, Metro by T-Mobile, Verizon | Specific codes match published self-service guidance; plan may still vary |
| **Contact carrier** | AT&T, Consumer Cellular, Cricket, Boost, Other | Prefer phone settings or call carrier; exact codes not verified in-repo |
| **Common examples only** | Cricket, Boost (optional collapsed section) | GSM-style examples shown with “confirm with your carrier” — not guaranteed |

### Carrier support script (phone call)

> Please help me forward unanswered or busy calls from my mobile business line to my LeadCareAI number: [number]. I do not want to forward all calls unless I ask for that.

### T-Mobile / Metro by T-Mobile

*Common T-Mobile / Metro-style codes. Your carrier or plan may vary.*

T-Mobile self-service activation often uses **double-star** codes (examples use 11-digit destination including leading `1`):

| When | Turn on (dial + Call) | Turn off |
|------|----------------------|----------|
| No answer / no reply | `**61*1XXXXXXXXXX#` | `##61#` |
| Busy | `**67*1XXXXXXXXXX#` | `##67#` |
| Not reachable | `**62*1XXXXXXXXXX#` | `##62#` |

Reset conditional (when supported): `##004#`

Optional all calls: `**21*1XXXXXXXXXX#` / off `##21#` — *only if you want every call to go to LeadCareAI before your phone rings.*

### Verizon

- **Recommended:** Conditional / no-answer-busy — `*71` + 10-digit LeadCareAI number (example: `*7118336691335`)
- **Optional all calls:** `*72` + 10-digit number
- **Turn off all calls:** `*73`

### AT&T / Consumer Cellular / Other

**Confidence: contact carrier** — no verified dial codes in-repo.

- Use phone call-forwarding settings first (iPhone / Android paths on the Backup Mode page).
- Or call carrier using the support script above.
- Do not assume AT&T or other dial codes work without carrier confirmation.

### Cricket / Boost

**Confidence: contact carrier** (primary). Optional collapsed section may show **common GSM-style examples only** — not verified for Cricket or Boost. Contact your MVNO or use phone settings before relying on dial codes.

## Setup checklist (customer)

1. My LeadCareAI number is assigned.
2. My customer-facing line is mobile.
3. I enabled missed/busy/unanswered call forwarding.
4. I called my business number from another phone.
5. I did not answer.
6. I received the LeadCareAI text-back.
7. I saw the lead in my dashboard.
8. Admin marked my test passed.

## Support script (for customers calling their carrier)

> Please help me forward unanswered or busy calls from my mobile business line to my LeadCareAI number: [assigned number]. I do not want to forward all calls unless I ask for that.

## Testing steps

1. Call the business line from another phone.
2. Do not answer (or test busy/unreachable as applicable).
3. Confirm LeadCareAI text-back to the caller.
4. Confirm lead in dashboard.
5. Admin sets `customer_phone_forwarding_status = test_passed`.

## Checkout vs activation

- **Checkout acknowledgement** (`BusinessLead.call_forwarding_terms_acknowledged`) is required before Stripe Growth checkout.
- **Backup Mode test passed** is separate; dashboard banner remains until admin marks `test_passed`.

## Routes

| URL | Purpose |
|-----|---------|
| `/business/backup-mode` | Primary Backup Mode page with carrier guide |
| `/business/call-forwarding` | Legacy alias (same page) |
| `/business/backup-mode/attempted` | Customer marks setup attempted |
| `/business/call-forwarding/attempted` | Legacy POST |

## Dashboard banner

> Backup Mode setup is not complete. Leads may not be captured until your call-forwarding test passes.

## Limitations

- No carrier API integration
- No universal code compatibility claims
- No automatic on/off from the LeadCareAI app
- Twilio webhooks and Stripe/partner flows unchanged
