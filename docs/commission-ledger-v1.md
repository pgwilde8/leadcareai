# Commission Ledger (V1)

LeadCareAI commission ledger tracks what is owed to partners after customers actually pay.

## Commission types and amounts

- `activation_bonus`: **$100** (10,000 cents)
- `monthly_residual`: **$25** per paid monthly invoice (2,500 cents)
- `retention_bonus`: **$100** after 6 paid monthly invoices (10,000 cents)

No partner recruitment commissions are created in V1.

## When commissions are created

Commissions are created from Stripe **paid** events only:

- `invoice.paid`:
  - creates one `monthly_residual` for each paid monthly invoice
  - creates `activation_bonus` once on first paid monthly invoice
  - creates `retention_bonus` once when six paid monthly invoices are reached
- `checkout.session.completed`:
  - used for conversion/provisioning and payment event capture
  - **does not** create monthly residual commissions directly

## Why checkout links do not create commissions

Creating a checkout link is intent, not payment.
Commissions are only created after Stripe confirms payment (`invoice.paid`).

## Why only paid events count

Business rule: partners are paid only for real paying customers.

That means:

- no commissions for partner signup
- no commissions for demo lead submission
- no commissions for checkout link creation
- no commissions before confirmed payment

## Idempotency and duplicate safety

- Stripe event IDs are stored in `payment_events` and processed idempotently.
- Duplicate webhook deliveries for the same event are ignored safely.
- Commission creation checks prevent duplicate rows for invoice/type combinations and one-time bonuses.

## Admin manual payout workflow

Admin ledger page: `/admin/commissions`

State flow:

1. `pending` (auto-created from paid events)
2. `approved` (admin review)
3. `paid` (manual payout completed outside app)

Admin may also mark `pending` or `approved` rows as `canceled`.

### Payout batches (Phase 2J)

Group approved commissions into manual payout batches:

- List: `/admin/payouts`
- Create: `/admin/payouts/new`
- Detail / mark paid: `/admin/payouts/{id}`

See [partner-payouts-v1.md](./partner-payouts-v1.md) for batch statuses, tax display on payout detail, and partner `/partner/payouts` history.

Individual **Mark paid** on `/admin/commissions` still works for approved commissions not in a draft batch.

No automated payout, bank transfer, or disbursement is included in V1.

Before production launch, run **`/admin/system-check`** and **`docs/production-launch-checklist-v1.md`**.

## Partner dashboard behavior

Partners can see their own commissions on `/partner/dashboard`:

- business name
- commission type
- amount
- status
- created/eligible timestamps

Stripe IDs are not exposed to partners.

## Current limitations (future phase)

- Refund and clawback automation is not implemented in V1.
- Future phase should handle:
  - `charge.refunded`
  - `invoice.payment_failed`
  - subscription cancellation adjustments
- For now, admins can manually cancel pending/approved commissions.
