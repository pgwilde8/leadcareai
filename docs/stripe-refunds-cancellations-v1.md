# Stripe Refunds, Cancellations, and Payment Failures (V1)

This phase protects the commission ledger when Stripe payments fail, subscriptions end, or money is returned.

## Supported webhook events

| Event | Effect |
|-------|--------|
| `checkout.session.completed` | Conversion/provisioning (Phase 2G); no commission creation here |
| `checkout.session.expired` | Lead checkout marked canceled; no commissions |
| `invoice.paid` | Creates commissions (Phase 2G) |
| `invoice.payment_failed` | Updates statuses; no commissions created |
| `customer.subscription.deleted` | Business/partner customer canceled; unpaid commissions canceled |
| `customer.subscription.updated` | `past_due` / `canceled` / `unpaid` handling |
| `charge.refunded` | Cancel unpaid commissions; flag paid for review |
| `charge.dispute.created` | Flag paid commissions for review when business is known |

Duplicate Stripe event IDs are ignored via `payment_events.stripe_event_id` uniqueness.

## Business status behavior

| Event | Business `status` |
|-------|-------------------|
| `invoice.payment_failed` | `past_due` |
| `customer.subscription.deleted` | `canceled` |
| `customer.subscription.updated` (`past_due`) | `past_due` |
| `customer.subscription.updated` (`canceled`, `unpaid`) | `canceled` |
| `charge.refunded` | `canceled` |

Linked `BusinessLead.payment_status` is updated to `failed` or `canceled` when a converted lead exists.

## PartnerCustomer status behavior

| Event | PartnerCustomer `status` |
|-------|--------------------------|
| `invoice.payment_failed` (was paying) | `payment_failed` |
| `invoice.payment_failed` (not yet paying) | `signed_up` |
| `customer.subscription.deleted` | `canceled` |
| `customer.subscription.updated` (canceled/unpaid) | `canceled` |
| `charge.refunded` (was paying) | `canceled` |

Statuses: `referred`, `signed_up`, `paying`, `payment_failed`, `canceled`.

## Commission handling

### Pending / approved

- Canceled on subscription delete/cancel (`cancel_unpaid_commissions_for_business`)
- Canceled on refund/dispute for matching invoice (`cancel_commissions_for_invoice`)

### Paid

- Status remains `paid`
- Notes updated: `Refund/dispute detected; review for clawback`
- Admin may later mark `clawed_back` manually at `/admin/commissions`

### Canceled

- Stays canceled (no silent reversal)

## Admin manual actions

1. Review `/admin/commissions` for refund/dispute notes.
2. Cancel any remaining pending/approved rows if needed (button).
3. For paid rows flagged for clawback, recover funds offline then **Mark clawed back**.

No automated payout reversal or bank integration in V1.

## Partner dashboard

Partners see commission status including `canceled`. Internal Stripe IDs and dispute details are not shown.

## What still requires manual admin action

- Actual clawback/recovery of paid commissions
- Deciding whether to re-approve after customer returns
- Edge cases where Stripe object linkage is incomplete (no business match)

## Why no automated clawback/payout

V1 tracks liability and risk in the ledger only. Money movement stays manual to avoid incorrect automated reversals.
