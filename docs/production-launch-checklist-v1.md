# Production launch checklist (V1)

Use this checklist before inviting real businesses or partners. Pair it with the live audit at **`/admin/system-check`** (admin login required).

Related:

- [admin-system-check-v1.md](./admin-system-check-v1.md) — What each system-check row means
- [production-readiness-phase-2i.md](./production-readiness-phase-2i.md) — Partner W-9 encryption
- [partner-payouts-v1.md](./partner-payouts-v1.md) — Manual payout batches
- [commission-ledger-v1.md](./commission-ledger-v1.md) — Commission creation rules

---

## 1. Core application

- [ ] `APP_ENV=production` on production hosts
- [ ] `APP_BASE_URL` and `PUBLIC_BASE_URL` set to production HTTPS URL
- [ ] `DATABASE_URL` points to production PostgreSQL (credentials in secrets only)
- [ ] `alembic upgrade head` — revision matches head (verify via `/admin/system-check`)
- [ ] `SECRET_KEY` is a strong random value (not `change-me`)
- [ ] `ADMIN_EMAIL` / admin user exists; password rotated from default

## 2. DNS and email authentication

- [ ] Production domain DNS points to app load balancer / host
- [ ] SPF record authorizes your SMTP sending host
- [ ] DKIM signing enabled for outbound mail
- [ ] DMARC policy published (start with `p=none` monitoring if needed)
- [ ] `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` configured
- [ ] Send a real test email outside this app (system check does not send mail)

## 3. Twilio (missed call + SMS)

- [ ] `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` configured
- [ ] `TWILIO_WEBHOOK_AUTH_ENABLED=true` in production
- [ ] Twilio console webhooks point to:
  - `{PUBLIC_BASE_URL}/webhooks/twilio/sms`
  - `{PUBLIC_BASE_URL}/webhooks/twilio/voice`
  - `{PUBLIC_BASE_URL}/webhooks/twilio/voice/status`
- [ ] **A2P 10DLC** brand/campaign registered if sending SMS to US mobiles (carrier compliance)
- [ ] Test inbound SMS and missed-call flow on a staging number before go-live

## 4. OpenAI (lead qualification)

- [ ] `OPENAI_API_KEY` configured
- [ ] `OPENAI_ENABLED` set intentionally (`true` for AI replies, `false` for fallback-only)
- [ ] `OPENAI_MODEL` matches your production tier/budget

## 5. Stripe (checkout + commissions)

- [ ] `STRIPE_SECRET_KEY` is **live** (`sk_live_…`) for production
- [ ] `STRIPE_WEBHOOK_SECRET` from live webhook endpoint
- [ ] Webhook endpoint: `{PUBLIC_BASE_URL}/webhooks/stripe`
- [ ] `STRIPE_PRICE_ID_GROWTH_MONTHLY` and `STRIPE_PRICE_ID_SETUP_FEE` are live Price IDs
- [ ] Products/prices match your public pricing page
- [ ] Test checkout → `invoice.paid` creates commissions (see commission smoke tests)

## 6. Partner program

- [ ] `PARTNER_TAX_ENCRYPTION_KEY` set (Fernet) — **required** for W-9 in production
- [ ] Key backed up in secrets vault (loss = unreadable TINs)
- [ ] `python scripts/seed_partner_documents.py` run on production
- [ ] Legal counsel reviewed partner document drafts (placeholders still say DRAFT)
- [ ] Partner onboard, admin approval, invite login tested

## 7. Admin smoke tests

- [ ] `/admin/system-check` — no red errors for production
- [ ] `/admin/notification-logs` — email/SMS delivery visible
- [ ] `/admin/commissions` — approve flow works
- [ ] `/admin/payouts` — draft batch → mark paid
- [ ] `/admin/partners` — application review, masked TIN only

## 8. Business smoke tests

- [ ] Public `/demo` or intake form submits
- [ ] Stripe checkout completes for a test business
- [ ] Business user invite → login → dashboard
- [ ] Lead inbox and settings notifications

## 9. Partner smoke tests

- [ ] `/partner/onboard` with W-9 + e-sign (test partner only)
- [ ] `/partner/dashboard` and `/partner/payouts` after approval
- [ ] Referral `?ref=` attribution on demo form

## 10. Commission / payout smoke tests

- [ ] Paid invoice creates `pending` commissions
- [ ] Admin approve → add to payout batch → mark paid
- [ ] Partner sees payout history without Stripe IDs or TIN

## 11. Legal pages (before public marketing)

- [ ] `/terms`, `/privacy`, `/refund-policy` reviewed by counsel
- [ ] Contact page and support email monitored
- [ ] SMS/terms sections finalized where marked `[TO BE FINALIZED]`

---

## Not in V1

- Automated bank payouts or 1099 filing
- DocuSign / live DNS verification from system check
- Test SMS/email from system-check page
