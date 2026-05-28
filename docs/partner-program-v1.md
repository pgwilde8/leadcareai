# Partner program V1

LeadCare AI partners are independent sales contractors who refer or sell the platform to local businesses. This document describes the V1 onboarding workflow implemented in code — not legal advice.

## Partner lifecycle

1. **Apply** — Public form at `/partner/onboard` collects applicant details.
2. **Sign documents** — Applicant reviews active `PartnerDocumentTemplate` records and provides a typed signature plus electronic consent checkbox.
3. **Admin review** — Application status becomes `admin_review`. Admins review at `/admin/partners` and `/admin/partners/{application_id}`.
4. **Approve or reject**
   - **Approve** — Creates an `active` `Partner` row with a unique `referral_code`, creates or links a `User` with `role=partner`, and sets `Partner.user_id`.
   - **Reject** — Sets application `rejected` with a stored reason (rejected applications cannot be approved).
5. **Login** — Admin gives the partner their credentials (see Auth below), then partner signs in at `/login`.
6. **Dashboard** — Linked active partners use `/partner/dashboard` (skeleton metrics are placeholders).

Application statuses: `applied`, `docs_pending`, `docs_signed`, `admin_review`, `approved`, `rejected`.

Partner statuses: `pending`, `active`, `suspended`, `rejected`.

## Documents collected

Three default templates are seeded (placeholder copy only):

| Code | Title |
|------|--------|
| `independent_contractor_agreement` | Independent Contractor Agreement |
| `partner_program_terms` | Partner Program Terms |
| `commission_schedule_acknowledgment` | Commission Schedule Acknowledgment |

Each signature stores: typed signature, timestamp, IP, user agent, consent text, document version, and a full **document snapshot** at time of signing.

Seed templates:

```bash
python scripts/seed_partner_documents.py
```

**Legal review required** before using placeholder documents with real independent contractors. Placeholders explicitly state they are drafts and not legal advice.

## Admin approval workflow

1. Open `/admin/partners` (admin login required).
2. Open an application in `admin_review`.
3. Verify signed documents, signature metadata, and applicant details.
4. **Approve** — Creates partner + referral code, creates/links login, shows a **one-time temporary password** on the application detail page when a new user is created.
5. **Reject** — Requires rejection reason.

Copy the temporary password from the admin screen and deliver it to the partner through a secure channel (phone, encrypted message, etc.). Passwords are **not** emailed in V1.

## Commission rules (policy)

- Commissions apply **only** to real **paying business customers** referred by the partner.
- **No** commissions for recruiting other partners.
- **No** MLM, downline, or partner-recruitment compensation.
- **No** automated payouts in V1.
- `PartnerCustomer` tracks referral attribution (`referred`, `signed_up`, `paying`, `canceled`) for a later phase; commission ledger is not built yet.

## Referral link format (Phase 2C)

```
https://leadcareai.com/?ref={referral_code}
```

(`APP_BASE_URL` in environment for non-production.)

### Referral capture behavior

- Any public page with `?ref={referral_code}` validates the code against an **active** partner.
- Valid codes are stored in the visitor session (`referral_code`, `referral_partner_id`).
- Invalid or unknown codes are ignored safely (no error page).
- Attribution persists when the visitor navigates to `/demo` in the same browser session.

### Business interest / demo form

- **GET/POST `/demo`** — public business intake form (not full customer onboarding).
- Creates a **`BusinessLead`** row (prospect), **not** a paying `Business` account.
- If session has a valid partner referral, the lead stores `partner_id` / `referral_code` and a **`PartnerCustomer`** row is created (`status=referred`).
- Duplicate submissions with the same email + phone update the existing lead and do not create duplicate `PartnerCustomer` rows for the same partner.

Business lead statuses (admin-managed): `new`, `contacted`, `qualified`, `converted`, `rejected`.

**Commissions are not created in this phase.** `PartnerCustomer.status` remains `referred` until a future Stripe `invoice.paid` integration.

### What partners see

On `/partner/dashboard`:

- Referral link (copyable) and referral code
- Count of referred businesses
- Table: business name, city/state, lead status, payment placeholder (“Not paying yet”)

Partners do **not** see prospect email/phone in the dashboard table (V1).

### What admins see

- **`/admin/business-leads`** — all demo/inquiry submissions with partner attribution when present
- **`/admin/business-leads/{id}`** — detail + status updates
- **`/admin/partners/{application_id}`** — referred leads for that partner when approved

## Auth and partner login (Phase 2B)

On approval:

| Case | Behavior |
|------|----------|
| New email | Creates `User` with `role=partner`, `is_active=true`, random temporary password (hashed only in DB). Admin sees password **once** on the application detail page. |
| Existing `business_user` or `partner` email | Links that user to the partner; sets `role=partner` if needed. No new password. |
| Existing `admin` email | Approval fails with an error (do not downgrade admin accounts). |
| Already linked | Idempotent: no duplicate user, partner, or referral code change; no new temporary password. |

Partner signs in at `/login` → redirected to `/partner/dashboard`.

**Future:** Email invitation or password-reset link (no plain-text password display). Automated email is **not** implemented in V1.

Admins use existing session auth (`role=admin`).

## Out of scope (V1)

- Automated login invitation emails
- DocuSign / PandaDoc
- Bank account / W-9 collection
- Automated payouts
- Stripe billing integration
- Partner-recruitment commissions or downlines
- Full business signup with referral capture (foundation only via `PartnerCustomer`)

## URLs

| Page | URL |
|------|-----|
| Partner onboarding | `https://leadcareai.com/partner/onboard` |
| Admin partner list | `https://leadcareai.com/admin/partners` |
| Admin application review | `https://leadcareai.com/admin/partners/{application_id}` |
| Partner dashboard | `https://leadcareai.com/partner/dashboard` |
| Public landing | `https://leadcareai.com/` |
| Book a demo | `https://leadcareai.com/demo` |
| Admin business leads | `https://leadcareai.com/admin/business-leads` |
