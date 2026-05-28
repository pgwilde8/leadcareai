

```text
Setup payment
→ sales rep activation bonus
→ Twilio number / brand / messaging setup costs
→ onboarding/support time
→ very little left for the house
```

That is okay **only if the customer stays subscribed**. The profit is in the recurring $147/month.

So the cancellation policy must protect you from paying out $100, doing setup, paying telecom fees, and then the customer cancels after a week.

## First correction: setup should probably stay $199, not $147

Earlier plan was:

```text
$199 setup fee
$147/month subscription
```

If you make setup only $147, then:

```text
$147 setup
- $100 rep bonus
- ~$20 Twilio/brand/phone cost
= $27 before your labor, Stripe fee, support, taxes
```

That’s too thin.

At **$199 setup**, it is still tight, but better:

```text
$199 setup
- $100 rep bonus
- ~$20 telecom/setup cost
= $79 before Stripe/support/taxes
```

Still not huge, but workable if onboarding is simple.

## The clean cancellation policy

I’d do this:

### Setup fee

**Non-refundable once setup work begins.**

Because that covers:

* phone/recovery number assignment
* messaging/brand setup
* business configuration
* call-forwarding assistance
* dashboard setup
* staff notification setup
* testing

Suggested wording:

```text
The setup fee is non-refundable once onboarding, phone number assignment, messaging configuration, or account setup work has begun.
```

### Monthly fee

**Cancel anytime. No prorated refund. Service continues until the end of the paid billing period.**

Suggested wording:

```text
Monthly subscriptions may be cancelled at any time. Cancellation stops future billing. Fees already paid for the current billing period are non-refundable, and service remains available until the end of the paid period unless suspended for non-payment, misuse, or policy violations.
```

That’s normal and fair.

## Partner commission timing is the real protection

Do **not** pay the rep the $100 immediately just because the business starts checkout.

Pay the rep when the customer is:

```text
paid + activated + outside short cancellation/refund window
```

For V1, I’d use this:

```text
Activation commission becomes pending when setup fee + first month are paid.
Activation commission becomes payable after 30 days if the customer has not refunded, disputed, or cancelled.
```

That protects you.

## Better payout schedule

Here is the safer version:

| Event                          |                 Customer pays |                    Partner commission |
| ------------------------------ | ----------------------------: | ------------------------------------: |
| Signup                         | $199 setup + $147 first month |                   $100 marked pending |
| First invoice paid             |                Included above | $25 monthly commission marked pending |
| After 30 days active/no refund |                             — |                 $125 becomes approved |
| Month 2 paid                   |                          $147 |                           $25 pending |
| Month 2 + 30 days              |                             — |                          $25 approved |

That means the rep still sees money coming, but you don’t get crushed by quick cancellations.

## What if customer cancels in first 30 days?

Policy:

```text
Setup fee: non-refundable once setup begins.
Monthly fee: non-refundable.
Partner commission: cancelled if customer cancels/refunds/disputes before approval.
```

So if they cancel after 10 days:

* You keep the setup fee unless you choose otherwise.
* Their subscription stops future billing.
* Rep does **not** get the $100 activation bonus yet.
* Rep does **not** get recurring commission.
* You are not upside down.

## What if customer cancels after 2 months?

Then:

* Rep keeps approved commissions already earned.
* Future recurring commissions stop.
* No clawback unless there was refund/dispute/fraud.

That’s fair.

## What if customer refunds or disputes?

Then:

```text
Pending commissions are cancelled.
Approved unpaid commissions are reversed.
Paid commissions can be clawed back from future commissions.
```

That needs to be in the partner agreement and commission addendum.

## My recommended customer cancellation policy

Use this as your business rule:

```text
LeadCareAI has no long-term contract.

Customers may cancel anytime before their next billing date. Cancellation stops future billing. Monthly fees already paid are not prorated or refunded.

The setup fee is non-refundable once setup work has begun, including account configuration, phone number assignment, SMS configuration, call-forwarding support, or onboarding.

If a customer cancels, LeadCareAI may release assigned phone numbers, stop missed-call recovery, disable SMS automation, and close dashboard access at the end of the paid billing period.
```

## My recommended partner payout policy

Use this:

```text
Partner commissions are earned only from real customer payments received and retained by LeadCareAI.

Activation bonuses and monthly commissions are first marked pending. Pending commissions become approved after a 30-day review period if the customer remains active and the payment has not been refunded, disputed, reversed, or charged back.

No commission is paid on cancelled, refunded, disputed, unpaid, fake, test, or internal accounts.

If a commission was already paid and the customer payment is later refunded or disputed, LeadCareAI may offset or claw back that amount from future commissions.
```

## The hard truth

Your first month on a customer is not where you win.

You win here:

```text
Month 2: $147 - $25 rep = $122 before costs
Month 3: $147 - $25 rep = $122
Month 4: $147 - $25 rep = $122
Month 5: $147 - $25 rep = $122
Month 6: $147 - $25 rep = $122
```

Then at month 6 you pay the $100 retention bonus, but by then the customer has produced enough revenue to justify it.

## I’d structure the offer like this

Customer-facing:

```text
$199 setup
$147/month
Cancel anytime
Setup fee non-refundable once setup begins
Monthly payments are non-refundable after billing
```

Partner-facing:

```text
$100 activation bonus after customer is paid, active, and clears 30-day review
$25/month recurring per active paid customer
$100 retention bonus after 6 paid months
No commission on refunds, disputes, cancellations, unpaid accounts, or free trials
```

That’s the cleanest version.

And Boss, don’t feel bad that the house doesn’t make much on setup. That’s normal. Setup gets the machine started. Recurring revenue is the business.
