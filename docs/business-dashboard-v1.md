# Business dashboard — lead inbox (Phase 1N)

Paying business users get a simple lead inbox scoped to their business. No cross-tenant access, no full CRM.

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/business/dashboard` | Overview counts (new, qualifying, urgent/hot, total) |
| GET | `/business/leads` | Lead inbox list |
| GET | `/business/leads/{lead_id}` | Lead detail + message timeline + AI fields |
| POST | `/business/leads/{lead_id}/status` | Update lead status |
| GET | `/business/settings` | Business profile and lead-handling settings |
| POST | `/business/settings` | Save settings |

See [business-settings-v1.md](business-settings-v1.md) for settings fields and missed-call message rules.

Login redirect for `business_user` role: `/business/dashboard`.

## Access model

- **Business user** (`role=business_user`) must be linked in `business_users` to exactly one primary business (first link by `created_at`).
- **Partner** and **admin** users are **not** allowed on `/business/*` (redirect to `/login`).
- Unauthenticated requests redirect to `/login`.
- Lead queries always filter by the session user’s `business_id`. Another business’s `lead_id` returns redirect to `/business/leads` (no data leak).

## Demo business user seed

After demo business + phone exist:

```bash
cd /srv/projects/leadcareai
python scripts/seed_demo_twilio_number.py
python scripts/seed_demo_business_user.py
```

- Finds business **LeadCare AI Demo**
- Creates or reuses `demo@leadcareai.com`
- Prints a **one-time password only when the user is newly created**
- Idempotent: safe to rerun

## Inbox columns

- Created at
- Customer phone
- Status
- Source (SMS / Missed call)
- Summary (truncated)
- Urgency
- AI temperature
- Last message preview
- Link to detail

## Lead detail

- Contact: phone, name, source, status, service, location, urgency
- AI: summary, next question, temperature, confidence, last analyzed
- Message timeline: voice calls, inbound/outbound SMS (chronological)
- Status form: `new`, `qualifying`, `contacted`, `won`, `lost`, `archived`

Statuses must exist in `LEAD_STATUSES` (includes legacy values like `qualified`, `booked`, `spam` for admin; business UI shows the selectable subset above).

## Current limitations

- One business per user (first `business_users` row only)
- No lead delete, notes, outbound SMS from UI, billing, or calendar
- No admin impersonation of business dashboard
- Urgent/hot count uses `ai_temperature=hot` or urgency in `urgent`, `today`, `asap`, `emergency`
- List preview uses latest message body only (160 chars)

## Production URL

`https://leadcareai.com/business/dashboard` (after login as a linked business user)
