# End-to-end launch test (V1)

Repeatable script to prove the full LeadCareAI machine works for **one test business** before onboarding real customers.

**Admin UI:** `/admin/live-test-runbook` (select a business to auto-check DB records)

Related:

- `/admin/system-check` — environment prerequisites
- `/admin/a2p-packet` — Twilio A2P copy/paste
- `/admin/businesses/{id}#live-launch-test` — mark launch verified

This runbook does **not** send test SMS, email, or call Stripe/Twilio/OpenAI from the admin page.

---

## Phase 0 — System prerequisites

1. Open **System Check** — resolve all **error** rows (Twilio, Stripe, SMTP, DB, SECRET_KEY, PARTNER_TAX_ENCRYPTION_KEY in production).
2. Open **A2P Packet** — prepare campaign registration copy (manual Twilio submission).
3. Confirm legal pages are live: `/privacy`, `/terms`, `/sms-terms`, `/refund-policy`.

---

## Phase 1 — Test business setup

### Create the prospect

1. Use a partner referral link if testing commissions: `{base}/r/{code}` or `/demo/book?ref={code}`.
2. Or use public **Book demo** / **Growth checkout** with test contact info.
3. Confirm **call forwarding terms** checkbox before Stripe checkout.

### Stripe test checkout

| Field | Value |
|-------|--------|
| Card | `4242 4242 4242 4242` |
| Expiry | Any future date |
| CVC | Any 3 digits |

Use **Stripe test mode** (`sk_test_...`). Complete Growth checkout ($199 setup + $147/mo).

### Expected records after checkout

| Record | Expected |
|--------|----------|
| `business_leads` | Row exists; `payment_status` → `paid`; `call_forwarding_terms_acknowledged` true |
| `payment_events` | `checkout.session.completed` |
| `businesses` | New row; `status` → `active` |
| `business_users` | Linked user |
| `user_invite_tokens` | Business invite sent or accepted |

Admin: **Prospect pipeline** → lead detail → **Businesses** → business detail.

---

## Phase 2 — Twilio & Backup Mode

1. Admin assigns **active** `phone_numbers` row to the business.
2. Record **mobile carrier** on business (call forwarding section).
3. Customer enables **Backup Mode** / call forwarding to LeadCareAI number (carrier-controlled).
4. Admin marks **forwarding instructions sent** / **forwarding test passed** after live test.
5. Set **notification_email** or **notification_phone** for staff alerts.

---

## Phase 3 — Live call & SMS test

From a **separate phone**:

1. Call the business **customer-facing** mobile line (not the Twilio number directly unless testing routing).
2. **Do not answer** the business line.
3. Confirm **missed-call text-back** SMS on the calling phone.
4. Reply: **`I need help with a leak.`**
5. Confirm in admin:
   - **Operational lead** under `/admin/leads` for this business
   - **Inbound SMS** on lead message timeline
   - **AI fields** (`summary`, `ai_next_question`, `ai_last_analyzed_at`) if `OPENAI_ENABLED`
   - **`notification_logs`** row (email and/or SMS)

6. On business detail → **Live launch test** → **Mark launch verified** (with notes).

---

## Phase 4 — Partner & commission (if referred)

Only when signup used `?ref=` or `/r/{code}`:

| Check | Expected |
|-------|----------|
| `business_leads.partner_id` | Set |
| `partner_customers` | Row; status progresses to `paying` |
| `payment_events` | `invoice.paid` after first subscription invoice |
| `commissions` | Rows for partner; status `pending` initially |
| Partner dashboard | Shows commission |
| `/admin/commissions` | Shows pending commission |

First invoice may take a billing cycle moment in test mode — confirm Stripe webhook delivery.

---

## Phase 5 — Final verification

- [ ] **Ready for launch: Yes** on business onboarding checklist
- [ ] **Launch verified** marked with notes
- [ ] Business user can log in at `/login` (business portal)
- [ ] Partner dashboard shows referral/commission if referred

---

## Troubleshooting

### No text-back after missed call

- Forwarding not enabled or wrong carrier code
- Twilio number not `active` or wrong business mapping
- Voice webhook URL not configured in Twilio Console
- Call did not hit forwarded path (test from external phone, do not answer)

### SMS webhook not hit / no inbound message

- SMS webhook URL: `{base}/webhooks/twilio/sms`
- `TWILIO_WEBHOOK_AUTH_ENABLED` and signature validation
- Inbound **To** must match active `phone_numbers` row for business

### AI disabled or empty fields

- `OPENAI_ENABLED=true` and `OPENAI_API_KEY` configured (System Check)
- Inbound SMS must be stored first
- Check lead detail for `ai_last_analyzed_at`

### Staff notification missing

- `notification_email` / `notification_phone` on business
- SMTP configured for email; Twilio for staff SMS
- Check `/admin/notification-logs` for `skipped` vs `failed`
- Staff SMS skipped if same as customer phone

### Stripe webhook not processed

- `STRIPE_WEBHOOK_SECRET` and endpoint `{base}/webhooks/stripe`
- Use test card; confirm `checkout.session.completed` in `payment_events`
- Stripe CLI forward in local dev if needed

### Partner commission missing

- Signup must use referral link (session/cookie)
- `partner_id` on `business_leads`
- `invoice.paid` must fire (subscription first payment)
- Check `/admin/commissions` and partner dashboard

---

## Limitations

- Runbook page reads DB only; does not trigger webhooks or sends
- Does not auto-mark launch verified
- Business selector shows recent businesses (manual pick)
- No per-click referral analytics

## Implementation

- Service: `app/services/live_test_runbook_service.py`
- Route: `GET /admin/live-test-runbook?business_id=`
- Template: `app/templates/admin/live_test_runbook.html`
