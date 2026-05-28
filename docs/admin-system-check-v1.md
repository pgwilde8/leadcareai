# Admin System Check (V1)

This page helps admins quickly confirm production readiness without exposing secrets.

## URLs

- `/admin/notification-logs`
- `/admin/notification-logs/{id}`
- `/admin/system-check`

## What each system check means

- **PUBLIC_BASE_URL configured**: required for links in staff alerts and emails.
- **TWILIO_ACCOUNT_SID configured**: Twilio REST/webhook account identifier present.
- **TWILIO_AUTH_TOKEN configured**: Twilio signature validation + API auth token present.
- **TWILIO_PHONE_NUMBER configured**: sender number set for outbound SMS.
- **TWILIO_WEBHOOK_AUTH_ENABLED**: should be `true` in production.
- **OPENAI_API_KEY configured**: AI provider credentials available.
- **OPENAI_ENABLED**: AI enrichment enabled/disabled flag.
- **SMTP_HOST configured**: SMTP server host present.
- **SMTP_FROM_EMAIL configured**: sender email configured.
- **STRIPE_SECRET_KEY configured**: Stripe API key present.
- **STRIPE_WEBHOOK_SECRET configured**: Stripe webhook signature secret present.
- **STRIPE_PRICE_ID_GROWTH_MONTHLY configured**: recurring plan price configured.
- **STRIPE_PRICE_ID_SETUP_FEE configured**: setup fee price configured.
- **Database reachable**: app can execute a basic DB query.

## Required env vars (core)

- `PUBLIC_BASE_URL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `TWILIO_WEBHOOK_AUTH_ENABLED=true` (production)
- `OPENAI_API_KEY` (if AI is enabled)
- `OPENAI_ENABLED`
- `SMTP_HOST`
- `SMTP_FROM_EMAIL`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID_GROWTH_MONTHLY`
- `STRIPE_PRICE_ID_SETUP_FEE`

## Debugging skipped email

1. Open `/admin/notification-logs`.
2. Filter `channel=email`, `status=skipped`.
3. Check error summary/detail for messages like `SMTP not configured`.
4. Verify `SMTP_HOST` and `SMTP_FROM_EMAIL` in environment.

## Debugging failed staff SMS

1. Open `/admin/notification-logs`.
2. Filter `channel=sms`, `status=failed`.
3. Open log detail to inspect full provider error.
4. Validate Twilio env vars and that sender number belongs to the active Twilio account.

## Security notes

- System Check does not print secret values.
- Notification Logs masks recipients in list views.
- Keep `TWILIO_WEBHOOK_AUTH_ENABLED=true` in production.
