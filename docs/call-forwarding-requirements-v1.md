# Call forwarding requirements (V1)

> **Product UI:** Businesses see this as **[Backup Mode](./backup-mode-v1.md)** (`/business/backup-mode`). This document describes technical/onboarding requirements; Backup Mode is the customer-facing name.

LeadCareAI captures missed and unanswered business calls by having the customer forward those calls from their existing customer-facing number to an assigned LeadCareAI/Twilio number. V1 onboarding is **mobile-first**: we guide, track, and verify setup; we do **not** enable forwarding programmatically.

## Mobile-first requirement

For V1 self-serve onboarding, the business must:

1. Use a **mobile** customer-facing line (the number customers dial today).
2. Use a carrier that supports **call forwarding** on that line.
3. Complete activation only after a **forwarding test passes** (`customer_phone_forwarding_status = test_passed`).

Businesses answer in settings:

- Is the number your customers call today a mobile phone?
- Mobile carrier (Verizon, AT&T, T-Mobile, Metro by T-Mobile, Cricket, Boost, Consumer Cellular, Other / Not sure)
- Whether they can access the phone during onboarding for a test call

## Why call forwarding is carrier-controlled

Carriers and phone plans control conditional forwarding (unanswered, busy, unreachable). LeadCareAI cannot dial carrier APIs or change forwarding on behalf of the customer. The product:

- Shows carrier-specific **Backup Mode** guides on `/business/backup-mode` with the disclaimer: *Carrier settings and plan behavior may vary.*
- Documents conditional forwarding (recommended) vs all-calls forwarding (optional, with warning)
- Tracks status: `not_started` → `instructions_sent` → `customer_attempted` → `test_passed` (or `failed_needs_help`)
- Lets admins mark `test_passed` after a live test call

## Supported V1 target

- Mobile business lines on major US prepaid/postpaid carriers where the customer can set forwarding on the handset or via carrier support.

## Unsupported / needs manual review

Do not promise self-serve setup for:

- Landlines
- Office PBX / multi-extension systems
- Google Voice, Grasshopper, RingCentral, and similar VoIP
- Complex call trees or shared main lines without a single mobile destination

These may require manual onboarding review.

## Successful test required

- Dashboard and business pages show a warning banner until `test_passed`.
- Login is **not** blocked.
- Leads may not be captured reliably until forwarding is verified.

Admin marks `test_passed` on the business detail page after a live forwarding test; `call_forwarding_tested_at` is set automatically.

## Data model (Business)

| Field | Purpose |
|-------|---------|
| `customer_phone_carrier` | Selected carrier key |
| `customer_phone_is_mobile` | Mobile vs not |
| `customer_phone_forwarding_status` | Onboarding state |
| `customer_phone_forwarding_notes` | Support notes |
| `call_forwarding_tested_at` | When test passed |

## Business lead / checkout terms

Demo/signup form includes a required checkbox:

> I understand LeadCareAI requires a mobile business line that supports call forwarding, and activation is complete only after a successful forwarding test.

Stored on `BusinessLead.call_forwarding_terms_acknowledged`.

**Stripe Growth checkout:** Admin-created checkout and public `/checkout/growth` both require acknowledgement before a Stripe session is created. Admin may record acknowledgement manually on the business lead detail page if collected by phone. Payment does **not** replace the live forwarding test (`test_passed`).

## Sample customer-facing terms language

Use in agreements, demo forms, and checkout:

> I understand that LeadCareAI requires a mobile business phone line capable of call forwarding from my existing customer-facing number to my assigned LeadCareAI number. I am responsible for configuring forwarding with my carrier. Activation is not complete until LeadCareAI verifies that a forwarding test has passed. Office phone systems, landlines, and some VoIP providers may not be supported in self-serve onboarding.

## Carrier guides (Phase 3D)

In-app guides are keyed off `Business.customer_phone_carrier`:

| Carrier key | Confidence | Guide style |
|-------------|------------|-------------|
| `t_mobile`, `metro_tmobile` | verified | T-Mobile double-star conditional codes (`**61*`, `**67*`, `**62*`) |
| `verizon` | verified | `*71` conditional, `*72` all-calls warning, `*73` off |
| `cricket`, `boost` | contact_carrier (+ optional common_but_unverified examples) | Phone settings / carrier script first; optional GSM examples in collapsed section |
| `att`, `consumer_cellular`, `other` | contact_carrier | Phone settings + carrier support script; no guaranteed codes |

Full copy and support script: [backup-mode-v1.md](./backup-mode-v1.md).

## Product limitations (V1)

- No carrier API integrations
- No universal compatibility claims for dial codes
- No PBX/landline/VoIP setup wizards
- No automatic activation from forwarding status alone (unless existing activation rules already require it elsewhere)
