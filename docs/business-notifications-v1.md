# Business lead notifications (Phase 1P)

Staff alerts when a new missed-call lead or inbound SMS reply is recorded.

## Channels

| Channel | Field | Behavior |
|---------|-------|----------|
| Email | `business.notification_email` | Plain-text alert when SMTP is configured |
| Staff SMS | `business.notification_phone` | Twilio SMS to staff (not the customer) |

If a field is blank, that channel is skipped (no error).

## Event triggers

| Event | When | Duplicate protection |
|-------|------|----------------------|
| `missed_call` | After new voice `CallSid` is stored and customer text-back is attempted | Same as voice webhook (`CallSid` dedupe) |
| `inbound_sms` | After new inbound SMS is stored, AI reply, and customer auto-response | Same as SMS webhook (`MessageSid` dedupe) |

## Email

**Subject examples:**

- `New missed-call lead: {business.name}`
- `New SMS reply: {business.name}`

**Body includes:** business name, customer phone, lead status, source, summary, urgency, latest message, dashboard URL (when `PUBLIC_BASE_URL` or `APP_BASE_URL` is set).

**SMTP env vars (optional):**

- `SMTP_HOST`
- `SMTP_PORT` (default `587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL` (default `no-reply@leadcareai.com`)

If SMTP is not configured, email attempts are logged as `skipped` in `notification_logs` and the webhook continues.

## Staff SMS

Template:

`LeadCare AI: New lead for {business} from {phone}. {summary}. View dashboard: {url}`

Rules:

- Max 320 characters
- Not sent to the same number as the customer phone (logged as `skipped`)
- Dashboard URL omitted when no public base URL is configured
- Twilio failures are logged; webhooks still return 200

Uses `TWILIO_PHONE_NUMBER` as the sender (via `twilio_service.send_sms`), separate from customer `sms_service` text-backs.

## Audit log

Table `notification_logs`: `channel`, `recipient`, `event_type`, `status` (`sent` / `failed` / `skipped`), `error_message`, `provider_sid`.

## Failure behavior

Notification code never raises to webhook handlers. Errors are logged and recorded.

## Limitations (V1)

- No quiet hours or scheduling
- No per-event notification preferences
- No push notifications
- Email is best-effort SMTP only
- Staff SMS requires Twilio credentials
- Customer text-back settings are separate from staff alerts

## Settings UI

`/business/settings` explains notification_email vs notification_phone and that alerts are best-effort.
