# Partner payout batches (V1)

Manual off-platform payout bookkeeping for approved partner commissions. **No money movement happens inside LeadCare AI.**

## Workflow

1. Stripe `invoice.paid` creates commission rows (`pending`).
2. Admin approves commissions at `/admin/commissions`.
3. Admin groups **approved, unpaid** commissions into a **draft payout batch** at `/admin/payouts/new`.
4. Admin pays the partner outside the app (ACH, check, PayPal, etc.).
5. Admin marks the batch **paid** at `/admin/payouts/{id}` with a reference or payment note.
6. Included commissions move to `paid` automatically.

## Payout batch statuses

| Status | Meaning |
|--------|---------|
| `draft` | Batch created; commissions linked; not paid yet |
| `paid` | Off-platform payment recorded; commissions marked paid |
| `canceled` | Draft canceled; commissions detached and remain `approved` |

## Business rules

- Only `approved` commissions with no existing `payout_id` can be added.
- A commission belongs to at most one payout batch.
- Batch `total_amount_cents` equals the sum of included commissions (same currency).
- Marking a payout paid requires **external reference** and/or **payment method note**.
- Individual **Mark paid** on `/admin/commissions` remains for approved commissions **not** in a draft batch.

## Tax / W-9 display

Payout detail (`/admin/payouts/{id}`) shows partner W-9 summary when available:

- Legal name, address, tax classification
- **Masked TIN only** (never plaintext or `tin_encrypted`)

## Partner visibility

Partners see their own batches at `/partner/payouts`:

- Status, total, paid date, commission count
- Per-type amount summaries
- No admin notes, no Stripe IDs, no TIN data

## Limitations (V1)

- No automated payouts or bank account collection
- No 1099 filing
- No partner downline / team overrides
- No in-app funds transfer
- Payout batches are audit/bookkeeping records only

## Related

- [commission-ledger-v1.md](./commission-ledger-v1.md) — How commissions are created and approved
