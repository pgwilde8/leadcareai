# Twilio voice missed-call text-back (Phase 1M)

LeadCareAI answers inbound calls with short TwiML, records the call as a voice-channel message, creates or reuses a lead, and sends one SMS text-back per unique `CallSid`.

## Twilio Console — Voice URLs

Configure the Twilio phone number (Voice & Fax):

| Setting | URL | Method |
|--------|-----|--------|
| **A call comes in** | `https://leadcareai.com/webhooks/twilio/voice` | HTTP POST |
| **Call status changes** | `https://leadcareai.com/webhooks/twilio/voice/status` | HTTP POST |

Production should keep `TWILIO_WEBHOOK_AUTH_ENABLED=true` so Twilio request signatures are validated.

## Inbound voice webhook

`POST /webhooks/twilio/voice`

Expected form fields:

- `CallSid`, `From`, `To`, `CallStatus`, `Direction`
- Optional: `AccountSid`, `Caller`, `Called`, `CallerName`, `ForwardedFrom`

Response: TwiML (`application/xml`):

```xml
<Response>
  <Say>Thanks for calling. We will text you now.</Say>
  <Hangup/>
</Response>
```

## Call status webhook

`POST /webhooks/twilio/voice/status`

Expected form fields:

- `CallSid`, `CallStatus`
- Optional: `From`, `To`, `CallDuration`, `Direction`

Returns HTTP 200 with empty body. Updates the stored voice message status when a matching `CallSid` exists.

## Business routing

Same rule as inbound SMS:

- `To` must match an **active** row in `phone_numbers.phone_number`
- Unknown or inactive numbers: HTTP 200 TwiML, no lead, no SMS (logged)

## Lead and message storage

On first sight of a `CallSid`:

| Record | Values |
|--------|--------|
| Lead | `source=missed_call`, phone = caller `From`, summary e.g. `Inbound call from +15551234567` |
| Message (inbound) | `channel=voice`, `provider=twilio`, `provider_sid=CallSid`, `status=CallStatus` |

Duplicate `CallSid`: no second inbound message, no second SMS.

## Outbound SMS (text-back)

One SMS per new call event:

```
{business.name}: Sorry we missed your call. What can we help you with today? Reply STOP to opt out.
```

If `business.name` is empty:

```
Sorry we missed your call. What can we help you with today? Reply STOP to opt out.
```

Sent via `sms_service` / Twilio REST (mocked in tests). Uses `TWILIO_PHONE_NUMBER` as the sender when configured.

## Manual curl (auth disabled)

Set in `.env` for local smoke tests:

```bash
TWILIO_WEBHOOK_AUTH_ENABLED=false
```

```bash
curl -sS -X POST "http://127.0.0.1:8788/webhooks/twilio/voice" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "From=+15551234567" \
  --data-urlencode "To=+15559876543" \
  --data-urlencode "CallSid=CA_SMOKE_001" \
  --data-urlencode "CallStatus=ringing" \
  --data-urlencode "Direction=inbound"
```

Status callback:

```bash
curl -sS -X POST "http://127.0.0.1:8788/webhooks/twilio/voice/status" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "CallSid=CA_SMOKE_001" \
  --data-urlencode "CallStatus=completed" \
  --data-urlencode "CallDuration=10"
```

Replace `To` with a number that exists as **active** in `phone_numbers` for your test business.

## Expected DB result (happy path)

1. One `leads` row: `source=missed_call`, caller phone, summary mentions inbound call
2. One inbound `messages` row: `channel=voice`, `provider_sid=CallSid`
3. One outbound `messages` row: `channel=sms`, missed-call text body
4. After status webhook: voice message `status` updated (e.g. `completed`)

## Out of scope (1M)

- Voice AI / OpenAI on calls
- Call forwarding (except future use of `forward_to_number`)
- Stripe, partner commissions, A2P automation
