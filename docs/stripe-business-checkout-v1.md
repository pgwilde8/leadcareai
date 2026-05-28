# Stripe business checkout V1 (Phase 2D)

Converts qualified `BusinessLead` prospects into paying `Business` customers via Stripe Checkout. **No commission ledger yet** — that comes in Phase 2E (`invoice.paid`).

## Required environment variables

| Variable | Purpose |
|----------|---------|
| `STRIPE_SECRET_KEY` | Stripe API secret key |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (optional in dev; required in production) |
| `STRIPE_PRICE_ID_GROWTH_MONTHLY` | Recurring Price ID for **$147/month** Growth plan |
| `STRIPE_PRICE_ID_SETUP_FEE` | One-time Price ID for **$199** setup fee (preferred) |
| `STRIPE_SETUP_AMOUNT_CENTS` | Fallback setup amount in cents (`19900`) if setup Price ID is omitted |
| `APP_BASE_URL` | Public base URL for redirects, e.g. `https://leadcareai.com` |

Legacy aliases in docs sometimes use `STRIPE_GROWTH_PRICE_ID` — the app reads `STRIPE_PRICE_ID_GROWTH_MONTHLY` from `.env.example`.

## Stripe Dashboard setup

1. Create a **Product** for LeadCare AI Growth (subscription).
2. Create a **recurring Price** at $147/month → copy ID to `STRIPE_PRICE_ID_GROWTH_MONTHLY`.
3. Create a **one-time Price** at $199 for setup → copy ID to `STRIPE_PRICE_ID_SETUP_FEE`.
4. Configure webhook endpoint:
   - URL: `https://leadcareai.com/webhooks/stripe`
   - Event: `checkout.session.completed`
5. Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET`.

Checkout uses **subscription mode** with two line items: recurring Growth price + one-time setup price.

## Admin flow

1. Prospect submits `/demo` (creates `BusinessLead`, optional partner attribution).
2. Admin reviews `/admin/business-leads` and sets status to **contacted** or **qualified**.
3. On lead detail `/admin/business-leads/{id}`, click **Create checkout link**.
4. System creates a **pending** `Business` (not active until paid) and a Stripe Checkout Session.
5. Copy **Open checkout link** and send to the prospect.
6. On payment, Stripe sends `checkout.session.completed` → lead marked **converted** / **paid**, business **active**.

### Payment statuses (`business_leads.payment_status`)

| Status | Meaning |
|--------|---------|
| `none` | No checkout yet |
| `checkout_created` | Checkout session created; link available |
| `paid` | Webhook confirmed payment |
| `failed` | Reserved for future use |
| `canceled` | Reserved for future use |

## Webhook events supported (V1)

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Mark lead paid/converted, activate business, set `PartnerCustomer` to `paying`, record `payment_events` |

Other events are ignored. Processing is **idempotent** by `stripe_event_id` in `payment_events`.

## Metadata on Checkout Session

- `business_lead_id`
- `business_id`
- `partner_id` (if referred)
- `partner_customer_id` (if referred)
- `referral_code` (if referred)

## Redirect URLs

- Success: `{APP_BASE_URL}/billing/success?session_id={CHECKOUT_SESSION_ID}`
- Cancel: `{APP_BASE_URL}/demo?checkout=cancelled`

## What remains before commissions (Phase 2E)

- Commission rows / ledger
- `invoice.paid` webhook handling
- Partner payout automation
- Business user login provisioning after payment

## Local testing

```bash
stripe listen --forward-to localhost:8788/webhooks/stripe
stripe trigger checkout.session.completed
```

Tests mock Stripe API calls and do not use live keys.
