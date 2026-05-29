# Customer onboarding checklist (V1)

Admin **Customer onboarding checklist** on `/admin/businesses/{id}` aggregates activation steps that were previously spread across business detail, leads, phone numbers, Backup Mode, and invites.

## Checklist items

| Key | Label | Typical status |
|-----|-------|----------------|
| `business_created` | Business record created | complete |
| `stripe_paid_or_active` | Stripe paid / account active | complete / missing |
| `business_user_invited` | Business user invited | complete / missing |
| `business_user_accepted_invite` | Business user accepted invite | complete / warning / missing |
| `business_user_access` | Business dashboard access | complete / warning / missing |
| `twilio_number_assigned` | Twilio number assigned (active) | complete / missing |
| `backup_mode_acknowledged` | Backup Mode terms acknowledged | complete / missing |
| `mobile_carrier_recorded` | Mobile line & carrier recorded | complete / warning / missing |
| `forwarding_instructions_sent_or_attempted` | Backup Mode instructions sent / attempted | complete / warning / missing |
| `forwarding_test_passed` | Forwarding test passed | complete / **manual** |
| `notification_contact_set` | Notification email or phone set | complete / missing |
| `first_lead_captured` | First lead captured (post-launch) | complete / missing |
| `first_customer_reply_captured` | First customer reply captured (post-launch) | complete / missing |
| `live_launch_verified` | Live launch smoke test verified (post-launch) | complete / missing |

Statuses: `complete`, `warning`, `missing`, `manual`.

## Ready for launch

**Ready for launch: Yes** when all launch-required items are satisfied:

1. **Stripe paid / account active** — `business.status == active` or Stripe subscription on file
2. **Business dashboard access** — linked business user; invite accepted, sent (pending), or not needed
3. **Twilio number assigned** — at least one `phone_numbers` row with `status=active`
4. **Backup Mode terms acknowledged** — linked `BusinessLead.call_forwarding_terms_acknowledged` on converted lead
5. **Forwarding test passed** — `customer_phone_forwarding_status == test_passed` (admin manual verification)
6. **Notification email or phone set** — `notification_email` or `notification_phone` on business

**Not required for launch:**
- First live lead
- First inbound customer reply
- Mobile/carrier fields (tracked separately)
- Instructions-sent progress (tracked separately)

Paying checkout alone does **not** mark the business launch-ready without forwarding test and Twilio number.

## Post-launch verification

After launch, confirm:

- **First lead captured** — operational `Lead` exists for the business
- **First customer reply** — inbound `Message` exists (SMS/missed-call flow)
- **Live launch verified** — admin completed guided smoke test and marked verified (`launch_verified_at`)

See [live-launch-smoke-test-v1.md](./live-launch-smoke-test-v1.md) for the step-by-step call/SMS script.

**Launch verified** is separate from **Ready for launch**: readiness is pre-launch configuration; verification is the end-to-end production test.

## Manual / admin verification

| Step | Who |
|------|-----|
| Forwarding test passed | Admin after live test call |
| Backup Mode terms (edge cases) | Admin on business lead detail if collected by phone |
| Twilio number active | Admin assigns number and sets status |
| Business invite | System on checkout; admin can resend |

## Admin actions

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/businesses/{id}` | Checklist + full detail |
| POST | `/admin/businesses/{id}/mark-forwarding-test-passed` | Set `test_passed` + `call_forwarding_tested_at` |
| POST | `/admin/businesses/{id}/mark-forwarding-instructions-sent` | Set `instructions_sent` |
| POST | `/admin/businesses/{id}/call-forwarding` | Full status + notes form |
| POST | `/admin/businesses/{id}/resend-invite` | Resend business login invite |
| POST | `/admin/businesses/{id}/mark-launch-verified` | Record live launch smoke test complete |

## Relation to Backup Mode

- **Acknowledgement** is recorded on `BusinessLead` at demo/checkout (required before Stripe).
- **Forwarding test passed** clears the business dashboard Backup Mode banner.
- Checklist links to call-forwarding section and Backup Mode customer page (`/business/backup-mode`).

## Implementation

- Service: `app/services/business_onboarding_service.py` → `build_business_onboarding_checklist(db, business)`
- Template: `app/templates/admin/_onboarding_checklist.html`

## Limitations

- No auto-provisioning of Twilio numbers or carrier forwarding
- Invite “login active” inferred from invite token `used_at`, not last login time
- Single primary linked user used for invite status
- Does not block business dashboard login when not launch-ready
