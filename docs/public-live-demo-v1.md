# Public Live Missed-Call Demo (Phase 3A)

## Public URLs

| URL | Purpose |
|-----|---------|
| `/demo` | Instructions to call the demo number and try SMS intake |
| `/demo/dashboard` | Read-only masked lead list (no login) |
| `/demo/book` | Sales/demo request form (former `/demo` form) |

## Configuration

Set in environment:

- `DEMO_ENABLED=true`
- `DEMO_BUSINESS_ID=<uuid>` — demo business (Joe's Plumbing Demo / LeadCare AI Demo)
- `DEMO_TWILIO_NUMBER=+18336691335`

Seed script: `scripts/seed_demo_twilio_number.py`

## Flow

1. Caller dials demo number → Twilio voice webhook returns demo TwiML and sends scripted missed-call SMS.
2. Caller replies → scripted intake (no OpenAI) collects issue, urgency/town, name, email, callback preference.
3. Anyone opens `/demo/dashboard` → sees masked leads for the demo business only.

## Privacy

- Dashboard masks phone numbers (last 4 digits).
- No admin/business settings links on public demo pages.
- No POST actions on the dashboard (read-only).
