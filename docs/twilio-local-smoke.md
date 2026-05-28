# Twilio SMS — inbound + outbound auto-response

## Inbound (Phase 1I)

`POST /webhooks/twilio/sms` stores inbound SMS when **To** matches an **active** `phone_numbers` row.

## Outbound auto-response (Phase 1K)

After a **new** inbound message (not a duplicate `MessageSid`), LeadCare sends one SMS via Twilio REST API:

> Thanks — this is {business.name}. We received your message and will follow up shortly.

Uses **`TWILIO_PHONE_NUMBER`** as `from_` (not Messaging Service, not Phone Number SID).

## Required `.env` for outbound SMS

| Variable | Required | Notes |
|----------|----------|--------|
| `TWILIO_ACCOUNT_SID` | Yes | REST API |
| `TWILIO_AUTH_TOKEN` | Yes | REST API + webhook signature when auth enabled |
| `TWILIO_PHONE_NUMBER` | Yes | E.164, e.g. `+18336691335` — used as SMS `from_` |
| `TWILIO_WEBHOOK_AUTH_ENABLED` | Yes | Keep **`true`** in production |
| `TWILIO_MESSAGING_SERVICE_SID` | No | Not used in V1 |

Install dependency after pull:

```bash
pip install -r requirements.txt
sudo systemctl restart leadcareai
```

## Tests

All Twilio REST calls are **mocked** in pytest. Tests do not send real SMS.

```bash
pytest -q tests/test_twilio_outbound_sms.py tests/test_twilio_inbound_sms.py
```

## Seed demo business + number

```bash
cd /srv/projects/leadcareai
source .venv/bin/activate
python scripts/seed_demo_twilio_number.py
sudo systemctl restart leadcareai
```

## Inbound webhook smoke (`curl`)

Unsigned `curl` returns **403** when `TWILIO_WEBHOOK_AUTH_ENABLED=true`. For manual curl only, temporarily set `false`, restart, test, restore `true`.

```bash
curl -i -X POST "https://leadcareai.com/webhooks/twilio/sms" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "From=+15551234567" \
  --data-urlencode "To=+18336691335" \
  --data-urlencode "Body=Need help with a roof leak" \
  --data-urlencode "MessageSid=SM_TEST_001"
```

### Expected HTTP response

- **200** with `<Response></Response>` (empty TwiML; reply is via REST, not TwiML)

### Expected database (new inbound)

| Row | Fields |
|-----|--------|
| Lead | `phone=+15551234567`, `source=sms` |
| Message (inbound) | `direction=inbound`, `status=received`, `provider_sid=SM_TEST_001` |
| Message (outbound) | `direction=outbound`, `status=queued` or `sent`, `provider_sid=SM...` from Twilio |

Duplicate `MessageSid` → no second inbound, **no second outbound**.

## Live SMS test (real Twilio)

1. Ensure `.env` has valid `TWILIO_*` credentials and `TWILIO_PHONE_NUMBER=+18336691335`.
2. Seed number + business (above).
3. In Twilio Console → your number → **Messaging** webhook: `https://leadcareai.com/webhooks/twilio/sms`.
4. Keep `TWILIO_WEBHOOK_AUTH_ENABLED=true`.
5. Text **+18336691335** from your mobile.
6. You should receive the auto-response within seconds.
7. Verify in admin: lead detail → message history shows inbound + outbound.

## Production reminder

- Keep **`TWILIO_WEBHOOK_AUTH_ENABLED=true`** so only Twilio can post to the webhook.
- Do not use `TWILIO_PHONE_NUMBER_SID` as `from_`; only the E.164 number string.
