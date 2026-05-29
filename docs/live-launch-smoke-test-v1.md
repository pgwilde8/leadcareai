# Live launch smoke test (V1)

Admin runbook for verifying a new customer end-to-end after pre-launch checklist items are complete.

## Where to run it

- **Admin business detail:** `/admin/businesses/{id}` → section **Live launch test**
- **Mark verified:** `POST /admin/businesses/{id}/mark-launch-verified`

## Pre-launch vs launch verified

| Status | Meaning |
|--------|---------|
| **Ready for launch** | Paid/active, dashboard access, Twilio number, Backup Mode acknowledgement, forwarding test passed, notifications configured |
| **Launch verified** | Admin completed live call/SMS smoke test and marked verified |

Ready for launch does **not** require a live lead. Launch verified is a separate post-setup confirmation.

## Exact test script

1. **Confirm active Twilio number** is assigned (status `active`).
2. **Ask the business owner** to enable Backup Mode / call forwarding to the LeadCareAI number.
3. **From a separate phone**, call the business customer-facing mobile line.
4. **Do not answer** the business line.
5. **Confirm** the caller receives the LeadCareAI missed-call text-back SMS.
6. **Reply as the customer:** `I need help with a leak.`
7. **Confirm in LeadCareAI:**
   - Lead in business dashboard / admin leads
   - Inbound SMS on lead message timeline
   - AI summary or next qualification question on lead
   - Staff email/SMS notification attempted
   - Row in `notification_logs` for this business
8. **Mark launch verified** with optional notes.

## Preconditions to mark verified

Required (button disabled until met):

- `customer_phone_forwarding_status == test_passed`
- At least one active Twilio phone number
- `notification_email` or `notification_phone` set

Not required (warnings only):

- First lead captured
- First inbound reply
- Notification log row (warn if missing)

Admin may still add notes explaining manual confirmation when warnings appear.

## If something fails

### Text-back does not arrive

- Confirm forwarding test passed and Backup Mode enabled on the correct line.
- Re-test with carrier; forwarding is **carrier-controlled**.
- Check Twilio number is `active` and webhook URL is correct (ops).

### Staff notification fails

- Confirm `notification_email` / `notification_phone` on business.
- Check `notification_logs` for failed status.
- SMTP/Twilio env in deployment (not changed by this runbook).

### AI response fails

- Confirm `OPENAI_ENABLED` and lead has inbound message.
- Check lead detail for AI fields; intake may use fallback path in tests.

### No lead in dashboard

- Confirm call hit LeadCareAI Twilio number (forwarding path).
- Check Twilio voice/SMS webhooks and business_id routing.

## Data stored on verify

| Field | Purpose |
|-------|---------|
| `launch_verified_at` | Timestamp |
| `launch_verified_by_user_id` | Admin who verified |
| `launch_verification_notes` | Free-text test notes |

## Relation to Backup Mode

- Forwarding test passed (pre-launch) confirms carrier forwarding was set up.
- Live launch test confirms production path: call → forward → SMS → reply → AI → staff alert.

## Limitations

- No automated browser or phone dialer in app
- Does not send real SMS/calls from tests
- Does not modify Twilio webhooks
- Does not auto-enable carrier forwarding
