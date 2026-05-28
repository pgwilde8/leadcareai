# LeadCareAI Partner Pay Plan README

## Purpose

This document defines the starting LeadCareAI Sales Partner compensation model.

The goal is to keep the pay plan simple, fair, and sustainable:

* Partners are paid for real paying business customers.
* No commission is paid for recruiting alone.
* No commission is paid on free trials, unpaid accounts, refunds, chargebacks, fake accounts, or cancelled customers.
* LeadCareAI protects cash flow by using a pending/review period before commissions become payable.

This document is business guidance and should be reviewed by legal/accounting before large-scale rollout.

---

# Customer Pricing

## Growth Plan

LeadCareAI’s starting customer offer:

| Item                 |         Price |
| -------------------- | ------------: |
| Setup fee            | $199 one-time |
| Monthly subscription |    $147/month |

The setup fee helps cover:

* Sales partner activation commission
* Twilio/phone number setup
* Messaging/brand registration costs where applicable
* Business onboarding
* Call-forwarding setup support
* Staff notification setup
* Dashboard configuration
* Testing the missed-call recovery flow

The monthly subscription is the primary recurring revenue source.

---

# Partner Compensation

## Starting Partner Pay Plan

Partners may earn:

| Commission Type              |    Amount | When It Applies                                                        |
| ---------------------------- | --------: | ---------------------------------------------------------------------- |
| Activation bonus             |      $100 | For each activated paid customer                                       |
| Monthly recurring commission | $25/month | For each active paid customer                                          |
| Retention bonus              |      $100 | After customer remains paid for 6 months                               |
| Direct sponsor override      | $10/month | Optional; only on active customers sold by directly sponsored partners |

The direct sponsor override should remain disabled until the basic partner system is proven.

---

# Key Rule

## Partners are paid from real customer payments only.

Commissions are generated from successful customer payments, not from:

* Recruiting partners
* Free trials
* Demo accounts
* Unpaid accounts
* Fake/internal accounts
* Refunded payments
* Disputed payments
* Cancelled customers
* Checkout attempts
* Verbal promises
* Leads that never become paying customers

---

# Commission Timing

## Recommended V1 Timing

Commissions should not be paid instantly.

Instead:

```text
Customer pays
→ commission is created as pending
→ 30-day review period
→ commission becomes approved if payment is retained
→ admin pays approved commissions
```

## Why use a 30-day review period?

Because the first month includes real upfront costs:

```text
$199 setup fee
- $100 partner activation bonus
- Twilio / phone / messaging setup costs
- Stripe processing fees
- onboarding/support labor
= limited remaining margin
```

If a customer cancels, refunds, or disputes immediately, LeadCareAI must not already be upside down.

---

# Activation Bonus Rules

## Activation bonus amount

```text
$100 per activated paid customer
```

## Activation bonus becomes pending when:

* Customer pays the setup fee
* Customer pays the first monthly subscription charge
* Customer is assigned or attributed to the partner
* Customer account is activated
* Partner is active and approved

## Activation bonus becomes approved when:

* 30 days have passed
* Customer has not refunded
* Customer has not disputed payment
* Customer has not charged back payment
* Customer account is still valid
* No fraud, fake account, or policy issue exists

## Activation bonus is cancelled if:

* Customer cancels during review period
* Customer receives refund
* Customer disputes payment
* Payment fails
* Customer account is fake/internal/test
* Partner attribution is invalid
* Partner violated marketing or sales rules

---

# Monthly Recurring Commission Rules

## Recurring commission amount

```text
$25/month per active paid customer
```

## Monthly recurring commission becomes pending when:

* Stripe confirms a successful monthly subscription payment
* Customer remains active
* Customer remains attributed to partner
* Partner remains active and in good standing

## Monthly recurring commission becomes approved when:

* The review period passes
* Payment is not refunded, disputed, reversed, or charged back
* Customer remains valid and active

## Monthly recurring commission stops when:

* Customer cancels
* Customer subscription becomes unpaid
* Customer account is suspended
* Customer payment fails
* Customer disputes or refunds payment
* Partner relationship is terminated under a policy that ends future commissions

---

# Retention Bonus Rules

## Retention bonus amount

```text
$100 after 6 paid months
```

## Retention bonus becomes pending when:

* Customer completes 6 successful paid monthly billing cycles
* Customer is still active
* Customer has not refunded/disputed relevant payments
* Partner is still eligible under the agreement

## Retention bonus becomes approved when:

* Review period passes
* No refund/dispute/chargeback exists
* Customer remains valid

---

# Direct Sponsor Override

## Optional future rule

```text
$10/month on active customers sold by directly sponsored partners
```

This should not be enabled until the direct partner sales system works reliably.

If enabled, it must follow these rules:

* Paid only on real active paying customers
* Paid only to direct sponsor
* No deep multi-level structure
* No commission for recruiting alone
* No override on free trials, fake accounts, unpaid customers, refunds, disputes, or cancellations
* Must not be marketed as passive income or guaranteed income

---

# Customer Cancellation Policy

## Recommended customer-facing policy

Customers may cancel anytime before their next billing date.

Cancellation stops future billing.

Monthly fees already paid are not prorated or refunded unless required by law or approved by Webwise Solutions LLC.

The setup fee is non-refundable once onboarding, account setup, phone number assignment, SMS setup, call-forwarding support, or configuration work has begun.

Service remains available until the end of the paid billing period unless suspended for non-payment, misuse, fraud, legal risk, or policy violation.

---

# Setup Fee Refund Policy

## Recommended rule

The setup fee is non-refundable once setup work begins.

Setup work includes:

* Creating or activating account
* Assigning recovery/tracking number
* Configuring SMS/text-back flow
* Setting business name/signature
* Setting staff notification destination
* Helping with call forwarding
* Testing the missed-call recovery flow
* Any onboarding/support work

## Possible goodwill exception

LeadCareAI may choose to refund at its sole discretion if no setup work has started.

This should be rare and manual.

---

# Refunds, Disputes, Chargebacks, and Clawbacks

## If payment is refunded/disputed before commission is paid

```text
Pending commission → cancelled
Approved unpaid commission → reversed
```

## If commission was already paid

```text
Paid commission → clawback / offset against future commissions
```

## Clawback examples

A clawback may apply when:

* Customer disputes payment
* Customer receives refund
* Customer chargebacks setup or monthly fee
* Payment is reversed
* Fraud or fake account is discovered
* Partner violated marketing rules to obtain customer

---

# Commission Statuses

Recommended statuses:

| Status      | Meaning                             |
| ----------- | ----------------------------------- |
| pending     | Created but not payable yet         |
| approved    | Cleared review and ready to pay     |
| paid        | Paid to partner                     |
| cancelled   | Will not be paid                    |
| reversed    | Previously approved but invalidated |
| clawed_back | Already paid and must be offset     |

---

# Example: New Customer Signup

Customer pays:

```text
$199 setup fee
$147 first month
```

Total collected at signup:

```text
$346
```

Partner commissions created:

```text
$100 activation bonus pending
$25 monthly recurring pending
```

After 30 days, if no refund/dispute/cancellation:

```text
$125 approved for payout
```

If customer cancels/refunds/disputes within review window:

```text
$100 activation bonus cancelled
$25 recurring commission cancelled
```

---

# Example: 20 Active Customers

Monthly customer revenue:

```text
20 × $147 = $2,940/month
```

Monthly partner recurring commissions:

```text
20 × $25 = $500/month
```

Revenue after partner recurring commissions:

```text
$2,940 - $500 = $2,440/month
```

This is before Twilio, OpenAI, hosting, Stripe fees, taxes, support, refunds, and other operating costs.

---

# Example: Setup Fees for 20 Customers

Setup revenue:

```text
20 × $199 = $3,980
```

Activation bonuses:

```text
20 × $100 = $2,000
```

Setup revenue after activation bonuses:

```text
$3,980 - $2,000 = $1,980
```

This remaining amount helps cover Twilio setup costs, onboarding, support, Stripe fees, and early operating expenses.

---

# Payout Schedule

## Recommended V1 payout schedule

* Commissions are reviewed monthly.
* Only approved commissions are paid.
* Pending commissions are not paid.
* Admin manually marks commissions as paid.
* Automated Stripe Connect payouts can be added later.

Example:

```text
May customer payments
→ commissions pending during May/June review window
→ approved after 30 days if valid
→ paid in next monthly payout batch
```

---

# Stripe Connect Future Plan

V1 may use manual payouts.

Later, LeadCareAI may use Stripe Connect for partner payouts.

Recommended future flow:

```text
Partner completes Stripe Connect onboarding
→ customer pays LeadCareAI
→ commission ledger creates pending commission
→ commission clears review period
→ admin approves payout batch
→ Stripe Connect transfers approved amount
```

Do not automatically split funds immediately in V1.

Immediate auto-splits create refund, chargeback, and clawback risk.

---

# Partner Eligibility

A partner must be:

* Approved by LeadCareAI
* Active in the system
* In good standing
* Properly attributed to the customer
* Compliant with all marketing and sales rules
* Properly onboarded with tax/payout information

LeadCareAI may suspend or terminate a partner for:

* False claims
* Spam
* Brand misuse
* Fake customers
* Misleading income claims
* Unauthorized promises
* Data misuse
* Customer complaints
* Fraud or suspected fraud

---

# Required Partner Documents

Before paying a partner, collect:

1. Independent Contractor Sales Partner Agreement
2. Commission Plan Addendum
3. W-9
4. Acceptable Marketing Policy
5. Privacy/Data Handling Agreement
6. Payout information or Stripe Connect onboarding

---

# Marketing / Compliance Rules

Partners may not claim:

* Guaranteed income
* Passive income with no work
* No selling required
* Guaranteed business results
* Guaranteed leads
* Guaranteed revenue
* LeadCareAI replaces all answering services
* LeadCareAI is an emergency response service
* They are employees of LeadCareAI

Allowed safer positioning:

```text
Earn commissions when real business customers you refer become paying subscribers and remain active.
```

```text
LeadCareAI helps local businesses respond faster to missed calls and qualify leads by SMS.
```

```text
Actual earnings depend on your sales activity, customer retention, expenses, and compliance with company rules.
```

---

# Admin Rules

Admin should be able to:

* View pending commissions
* Approve commissions
* Cancel invalid commissions
* Reverse commissions after refunds/disputes
* Mark commissions as paid
* View customer payment status
* View partner attribution
* View payout history
* Add support notes/audit logs

Do not calculate commissions only on-screen.

Every commission should be a durable ledger record.

---

# Product Rule

Stripe is the payment source of truth.

Do not mark a commission as earned unless Stripe confirms successful customer payment.

Do not mark a commission as payable if the payment was refunded, disputed, reversed, or charged back.

---

# Final V1 Recommendation

Use this compensation structure:

```text
Customer:
$199 setup
$147/month

Partner:
$100 activation bonus, pending for 30 days
$25/month recurring, pending after each paid invoice
$100 retention bonus after 6 paid months
No instant payouts
No commission on refunds/disputes/cancellations/unpaid accounts
Manual monthly payout batches for V1
Stripe Connect payouts later
```

This protects LeadCareAI while still giving partners a simple, attractive recurring commission plan.
