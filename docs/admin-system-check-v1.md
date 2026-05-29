# Admin System Check (V1)

Production readiness audit for admins before live launch. **No secrets are displayed** and **no test SMS, email, Stripe, Twilio, or OpenAI API calls** are made from this page.

## URL

- **`/admin/system-check`** (admin session required)

Also see:

- **`docs/production-launch-checklist-v1.md`** — full pre-launch checklist
- **`/admin/a2p-packet`** — Twilio A2P copy/paste packet
- **`docs/a2p-registration-packet-v1.md`** — same A2P content in documentation form

## Sections

### Core

| Check | Notes |
|-------|--------|
| **APP_ENV** | Expect `production` on prod hosts |
| **APP_BASE_URL** | Application base URL |
| **PUBLIC_BASE_URL / effective public URL** | Used for notification links and webhook URL display |
| **DATABASE_URL** | Masked credentials (`***`); never raw password |
| **Database reachable** | `SELECT 1` against app DB |
| **Alembic revision** | Compares DB to migration head |
| **SECRET_KEY** | Session signing; warns if default `change-me` in production |
| **SESSION_SECRET** | Not used separately — sessions use `SECRET_KEY` |
| **LEGAL_CONTACT_EMAIL** | Public legal/SMS support contact (default `paul@leadcareai.com`) |

### Twilio

| Check | Notes |
|-------|--------|
| **TWILIO_ACCOUNT_SID** | configured yes/no |
| **TWILIO_AUTH_TOKEN** | configured yes/no (never shown) |
| **TWILIO_PHONE_NUMBER** | configured yes/no |
| **TWILIO_WEBHOOK_AUTH_ENABLED** | Should be `true` in production |
| **Webhook URLs** | When base URL is set: `/webhooks/twilio/sms`, `/webhooks/twilio/voice`, `/webhooks/twilio/voice/status` |

Configure these URLs in Twilio Console for each assigned number.

### OpenAI

| Check | Notes |
|-------|--------|
| **OPENAI_ENABLED** | Feature flag |
| **OPENAI_API_KEY** | configured yes/no; last 4 chars only when set |
| **OPENAI_MODEL** | Model name (not secret) |

### Stripe

| Check | Notes |
|-------|--------|
| **STRIPE_SECRET_KEY** | **test** vs **live** from prefix (`sk_test_` / `sk_live_`) |
| **STRIPE_WEBHOOK_SECRET** | configured yes/no |
| **STRIPE_PRICE_ID_GROWTH_MONTHLY** | configured yes/no |
| **STRIPE_PRICE_ID_SETUP_FEE** | or fallback `STRIPE_SETUP_AMOUNT_CENTS` |
| **Webhook URL** | `{base}/webhooks/stripe` when base URL is set |

### Email / SMTP

| Check | Notes |
|-------|--------|
| **SMTP_HOST**, **SMTP_PORT**, **SMTP_USERNAME** | configured / value |
| **SMTP_PASSWORD** | configured only (masked suffix) |
| **SMTP_FROM_EMAIL** | configured yes/no |
| **DEFAULT_SUPPORT_EMAIL** | Contact form destination |

**Reminder:** SPF, DKIM, and DMARC must be verified in your email provider dashboard — this page does not run DNS checks.

### Partner tax (W-9)

| Check | Notes |
|-------|--------|
| **PARTNER_TAX_ENCRYPTION_KEY** | **Error in production if missing** |

### Compliance (public legal pages)

Confirms routes are registered in the application:

- `/privacy`
- `/terms`
- `/sms-terms`
- `/refund-policy`

Verify HTTPS 200 responses in production separately.

### A2P 10DLC

- Route `/admin/a2p-packet` registered
- Packet doc + admin copy page available
- **Reminder:** Twilio/TCR submission is manual; approval not guaranteed

### Security / admin

- **ADMIN_EMAIL** configured yes/no

## Status colors

| Status | Meaning |
|--------|---------|
| ok | Ready or acceptable |
| warn | Review before launch (e.g. test Stripe key, webhook auth off) |
| error | Likely blocking for production |
| info | Informational only |

## Masking rules

Never rendered on this page:

- Full `TWILIO_AUTH_TOKEN`
- Full `OPENAI_API_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- Full `PARTNER_TAX_ENCRYPTION_KEY`, `SMTP_PASSWORD`, `SECRET_KEY`
- Database passwords in `DATABASE_URL`

Safe to show:

- configured yes/no
- Stripe test/live mode from key prefix
- Last 4 characters of long secrets (optional suffix hint)
- Masked database URL host
- Public webhook URL paths

## Related admin tools

- `/admin/notification-logs` — staff alert delivery
- `/admin/a2p-packet` — A2P registration copy
- `/admin/commissions`, `/admin/payouts` — partner payouts

## Limitations

- Does not send test SMS or email
- Does not call Stripe, Twilio, or OpenAI APIs
- Does not verify DNS (SPF/DKIM/DMARC) or TLS certificates
- Route checks confirm registration only, not production HTTP reachability
- Does not validate Twilio number ↔ business mapping

## Implementation

- Service: `app/services/system_check_service.py` → `build_system_check_sections(db)`
- Template: `app/templates/admin/system_check.html`
- Route: `GET /admin/system-check` in `app/routers/admin.py`
