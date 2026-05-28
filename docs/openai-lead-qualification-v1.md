# OpenAI lead qualification V1 (Phase 1L)

OpenAI classifies **inbound SMS** messages to help local businesses understand what the customer needs. It is **not** a general chatbot.

## What OpenAI is used for

After a new inbound SMS is stored:

1. Classify the message into structured fields (service, urgency, location, summary, temperature).
2. Optionally produce **one** short follow-up question for the auto-reply SMS.
3. Update the `Lead` record for admin review.

## What OpenAI is not used for

- Free-form multi-turn conversations
- Quoting prices or scheduling appointments
- Claiming a human is available now
- Legal, medical, financial, or emergency advice
- Voice calls
- Partner commissions or Stripe billing

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | (empty) | API key; required when enabled |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model for structured parsing |
| `OPENAI_ENABLED` | `true` | Set `false` to skip API calls |
| `OPENAI_TIMEOUT_SECONDS` | `20` | Request timeout |

## Lead fields updated

Uses existing columns where possible:

- `service_needed`, `location`, `urgency`, `name`, `summary`

Plus AI-specific columns:

- `ai_temperature` — `cold`, `warm`, `hot`, `unknown`
- `ai_next_question` — last suggested follow-up (capped at 160 chars)
- `ai_confidence` — 0.0–1.0
- `ai_last_analyzed_at` — timestamp

Lead `status` may move from `new` → `qualifying` when temperature is warm/hot.

## Safety rules (prompt + code)

- No prices, appointment promises, or “available now” language in `next_question`
- At most one follow-up question; max 160 characters
- Outbound SMS includes **Reply STOP to opt out**
- If `next_question` looks unsafe, it is dropped and a simple acknowledgment is sent instead

## Fallback when disabled or on failure

If `OPENAI_ENABLED=false`, `OPENAI_API_KEY` is missing, the API errors, or parsing fails:

| Field | Fallback |
|-------|----------|
| `summary` | Customer message (trimmed) |
| `urgency` | `unknown` |
| `lead_temperature` | `warm` |
| `next_question` | "Can you share a little more detail about what you need help with?" |
| `confidence` | `0.0` |

## Example inbound SMS and reply

**Inbound:** `Water heater leaking in the garage`

**AI reply (example):**

```text
Acme Plumbing: Thanks — we received your message. Is water actively pooling right now? Reply STOP to opt out.
```

**When AI is off / fails:**

```text
Acme Plumbing: Thanks — we received your message. Can you share a little more detail about what you need help with? Reply STOP to opt out.
```

## Idempotency

Duplicate Twilio `MessageSid` does not re-run AI or send a second outbound SMS (unchanged from inbound handler).

## Tests

All tests mock OpenAI (`OPENAI_ENABLED=false` by default in `conftest.py`). Do not call the real API in CI.

```bash
pytest tests/test_ai_lead_qualification.py -q
```
