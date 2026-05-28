# Sales Demo Readiness (Phase 1T)

Internal checklist and copy for showing LeadCare AI to business owners and training sales partners.

## Admin: demo control panel

**URL:** `/admin/demo`

### Readiness checklist

Built from environment + demo business record (no schema changes):

| Check | Source |
|-------|--------|
| Demo mode enabled | `DEMO_ENABLED` |
| Demo business ID configured | `DEMO_BUSINESS_ID` |
| Demo business exists | DB lookup |
| Demo number configured | `DEMO_TWILIO_NUMBER` |
| Staff notification configured | `Business.notification_email` or `notification_phone` |
| Recent demo lead exists | At least one lead on demo business |

### Sales assets on page

- **Live demo script** — call/hang up, SMS reply, show HOT/URGENT in dashboard, owner pitch, number-forwarding setup
- **Internal sales copy** — 30-second script, three objections, partner compensation reminder

## Partners

**URL:** `/partner/dashboard`

Includes the **live demo script** section (same partial as admin) so partners can run the public demo during sales conversations. Full objection handlers and compensation detail remain admin-only on `/admin/demo`.

## Public demo (unchanged)

- `/demo` — instructions
- `/demo/dashboard` — read-only masked leads
- Demo line: **1-833-669-1335**

## Remaining sales-readiness TODOs

- [ ] Legal-reviewed partner one-pager (PDF) — not in app
- [ ] Recorded video walkthrough — not in app
- [ ] Email template for post-demo follow-up — not in app
- [ ] Automated readiness alert (Slack/email) when checklist fails — not in V1
- [ ] Partner UI design-system migration — deferred
