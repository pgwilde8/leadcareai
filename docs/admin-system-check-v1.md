# Admin System Check (V1)

Production readiness audit for admins. **No secrets are displayed** and **no test SMS/email/API calls** are made from this page.

## URL

- **`/admin/system-check`** (admin session required)

Also see **`docs/production-launch-checklist-v1.md`** for the full pre-launch checklist.

## Sections

### Core

- **APP_ENV** — `production` expected on prod hosts
- **APP_BASE_URL / PUBLIC_BASE_URL** — HTTPS base for links in notifications and webhooks
- **DATABASE_URL** — masked (`***` credentials); not the raw secret
- **Database reachable** — `SELECT 1` against app DB
- **Alembic revision** — compares DB revision to migration head; suggests `alembic upgrade head` if behind

### Twilio

- Account SID, auth token, phone number — configured yes/no only
- **TWILIO_WEBHOOK_AUTH_ENABLED** — should be `true` in production
- Webhook URL reminders (full URLs when base URL is set):
  - `/webhooks/twilio/sms`
  - `/webhooks/twilio/voice`
  - `/webhooks/twilio/voice/status`

### OpenAI

- **OPENAI_ENABLED** — flag only
- **OPENAI_API_KEY** — configured yes/no; last 4 characters only when set
- **OPENAI_MODEL** — model name (not secret)

### Stripe

- **STRIPE_SECRET_KEY** — test vs live from key prefix (`sk_test_` / `sk_live_`)
- Webhook secret and price IDs — configured yes/no
- **STRIPE_PRICE_ID_SETUP_FEE** — or notes fallback `STRIPE_SETUP_AMOUNT_CENTS`
- Webhook path reminder: `/webhooks/stripe`

### Email / SMTP

- Host, port, username, password (masked), from address
- SPF/DKIM/DMARC reminder — no live DNS check

### Partner tax (W-9)

- **PARTNER_TAX_ENCRYPTION_KEY** — configured yes/no (suffix only); **error in production if missing**

### Security / admin

- **SECRET_KEY** — warns if default `change-me` in production
- **ADMIN_EMAIL** — configured yes/no

## Status colors

| Status | Meaning |
|--------|---------|
| ok | Ready or acceptable |
| warn | Review before launch (e.g. test Stripe key, webhook auth off) |
| error | Likely blocking for production |
| info | Informational only |

## Related admin tools

- `/admin/notification-logs` — debug skipped/failed staff alerts
- `/admin/commissions` — commission ledger
- `/admin/payouts` — manual payout batches

## Security

- Auth tokens, API keys, encryption keys, and passwords are never rendered.
- Use environment/secrets manager for values; system check only reports presence and safe metadata.
