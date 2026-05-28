# Partner program V1

LeadCare AI partners are independent sales contractors who refer or sell the platform to local businesses. This document describes the V1 onboarding workflow implemented in code — not legal advice.

## Public partner opportunity

- **`GET /partners`** — Public sales partner opportunity page (pay plan summary, compliance guardrails, how it works, apply CTA).
- **`GET /partner/onboard`** — Lightweight application only (no W-9, no IC signing, no tax ID on first submit).

## Partner lifecycle

1. **Apply** — Public form at `/partner/onboard` collects name, contact, market area, sales background, and IC/commission acknowledgment only. No tax ID or document signing on this step.
2. **Admin screening** — Admins review at `/admin/partners` and `/admin/partners/{application_id}`, contact the applicant, and may reject.
3. **Sign documents** — Admin generates a signing link (`docs_pending`). Applicant opens `/partner/sign-documents?token=…`, reviews templates, and signs. Status becomes `docs_signed`.
4. **W-9 / tax info** — After signing, applicant is redirected to `/partner/tax-info?token=…` to submit encrypted W-9 data (or admin sends a W-9 link later).
5. **Approve or reject**
   - **Approve** — Only when `docs_signed`. Creates an `active` `Partner` with `referral_code`, creates or links a `User` with `role=partner`, and sets `Partner.user_id`.
   - **Reject** — Sets application `rejected` with a stored reason (rejected applications cannot be approved).
6. **Login** — Partner accepts invite email (or admin resends) and signs in at `/login`.
6. **Dashboard** — Linked active partners use `/partner/dashboard` (skeleton metrics are placeholders).

Application statuses: `applied`, `docs_pending`, `docs_signed`, `admin_review`, `approved`, `rejected`.

Partner statuses: `pending`, `active`, `suspended`, `rejected`.

## Documents collected

Five default templates are seeded from markdown files (draft copy — **legal review required**):

| Code | Title |
|------|--------|
| `independent_contractor_agreement` | Independent Contractor Agreement |
| `commission_schedule_acknowledgment` | Commission Schedule Acknowledgment |
| `acceptable_marketing_policy` | Acceptable Marketing Policy |
| `privacy_data_handling` | Privacy / Data Handling |
| `electronic_signature_notice` | Electronic Signature and Records Notice |

Each signature stores: typed signature, timestamp, IP, user agent, consent text, document version, and a full **document snapshot** at time of signing. Snapshots for already-signed applications are never overwritten when templates are re-seeded.

See [partner-esign-v1.md](./partner-esign-v1.md) for e-sign architecture, encryption, and admin masking rules.

Seed templates:

```bash
python scripts/seed_partner_documents.py
```

## W-9 / tax information

- Collected on `/partner/tax-info?token=…` after IC documents are signed (not on the public apply form).
- Stored in `partner_tax_info` with **Fernet-encrypted** TIN (`PARTNER_TAX_ENCRYPTION_KEY` required in production).
- Admins see masked TIN only on `/admin/partners/{application_id}` — no full TIN in HTML or logs in V1.

**Legal review required** before using placeholder documents with real independent contractors. Placeholders explicitly state they are drafts and not legal advice.

## Admin approval workflow

1. Open `/admin/partners` (admin login required).
2. Open an application in `admin_review` — review applicant details and W-9 (masked TIN). Generate an IC document signing link when ready.
3. When status is `docs_signed`, verify signed documents and signature metadata.
4. **Approve** — Creates partner + referral code, creates/links login, and sends partner invite email when SMTP is configured.
5. **Reject** — Available from `admin_review`, `docs_pending`, or `docs_signed`; requires a rejection reason.

Copy the temporary password from the admin screen and deliver it to the partner through a secure channel (phone, encrypted message, etc.). Passwords are **not** emailed in V1.

## Commission rules (policy)

- Commissions apply **only** to real **paying business customers** referred by the partner.
- **No** commissions for recruiting other partners.
- **No** MLM, downline, or partner-recruitment compensation.
- **No** automated payouts in V1.
- `PartnerCustomer` tracks referral attribution (`referred`, `signed_up`, `paying`, `canceled`) for a later phase; commission ledger is not built yet.

## Referral link format (Phase 2C)

Partners share links from **`/partner/marketing`** (active partners only):

| Link | URL |
|------|-----|
| Referral landing | `{PUBLIC_BASE_URL}/r/{referral_code}` |
| Live demo | `{PUBLIC_BASE_URL}/demo?ref={referral_code}` |
| Book demo | `{PUBLIC_BASE_URL}/demo/book?ref={referral_code}` |
| Homepage with ref | `{PUBLIC_BASE_URL}/?ref={referral_code}` |

(`PUBLIC_BASE_URL` or `APP_BASE_URL` in environment for non-production.)

### Referral capture behavior

- Any public page with `?ref={referral_code}` stores the code in session and a **30-day** `leadcare_ref` cookie (last click wins).
- **`GET /r/{referral_code}`** validates an **active** partner, captures attribution, and shows a sales landing page with demo CTAs.
- Invalid or inactive codes on `/r/{code}` redirect to `/` without attribution (same spirit as invalid `?ref=` on the homepage).
- **`/demo/book`** resolves the partner from session first, then falls back to the `leadcare_ref` cookie.
- Attribution persists when the visitor navigates to `/demo` or submits `/demo/book` in the same browser.

### Business interest / demo form

- **GET/POST `/demo`** — public business intake form (not full customer onboarding).
- Creates a **`BusinessLead`** row (prospect), **not** a paying `Business` account.
- If session has a valid partner referral, the lead stores `partner_id` / `referral_code` and a **`PartnerCustomer`** row is created (`status=referred`).
- Duplicate submissions with the same email + phone update the existing lead and do not create duplicate `PartnerCustomer` rows for the same partner.

Business lead statuses (admin-managed): `new`, `contacted`, `qualified`, `converted`, `rejected`.

**Commissions are not created in this phase.** `PartnerCustomer.status` remains `referred` until a future Stripe `invoice.paid` integration.

### What partners see

On `/partner/dashboard`, `/partner/marketing`, and `/partner/resources`:

- Referral link (copyable) and referral code
- Marketing links page with demo/landing URLs and suggested share copy
- Resources & training playbook (quick start, pitch, demo script, objections, compliance)
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
| Partner opportunity | `https://leadcareai.com/partners` |
| Partner application | `https://leadcareai.com/partner/onboard` |
| Admin partner list | `https://leadcareai.com/admin/partners` |
| Admin application review | `https://leadcareai.com/admin/partners/{application_id}` |
| Partner dashboard | `https://leadcareai.com/partner/dashboard` |
| Public landing | `https://leadcareai.com/` |
| Book a demo | `https://leadcareai.com/demo` |
| Admin business leads | `https://leadcareai.com/admin/business-leads` |
