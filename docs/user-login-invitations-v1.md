# User Login Invitations (V1)

This version replaces plaintext temporary-password sharing with single-use invite tokens.

## Business client login flow (after payment)

1. Stripe webhook `checkout.session.completed` is received.
2. `handle_checkout_session_completed(...)` converts/activates the business.
3. The app calls `create_or_invite_business_user_for_business(...)`:
   - create/reuse `User` by business contact email
   - enforce `role=business_user` for this flow
   - ensure `BusinessUser` link to the converted `Business`
   - create invite token for new user (or when manually resent)
4. Invite email is sent with `/auth/accept-invite?token=...`.
5. User sets password and signs in at `/login`, then lands on `/business/dashboard`.

## Partner login flow (after approval)

1. Admin approves partner application (`/admin/partners/{id}/approve`).
2. Partner/user linkage is created or reused.
3. Invite token is generated for new partner users (or manual resend).
4. Invite email contains `/auth/accept-invite?token=...`.
5. Partner sets password and signs in to access `/partner/dashboard`.

## Invite token rules

- Raw token is generated once and never stored in DB.
- DB stores only `token_hash` (SHA-256).
- Token is single-use (`used_at`).
- Token expires after 7 days (`expires_at`).
- Purposes:
  - `business_invite`
  - `partner_invite`
  - `password_reset` (reserved)

## SMTP env vars

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME` (optional)
- `SMTP_PASSWORD` (optional)
- `SMTP_FROM_EMAIL`

If SMTP is missing, invite delivery is marked `skipped` but provisioning continues.

## Resend behavior

- Admin business detail: resend business invite button.
- Admin partner application detail: resend partner invite button.
- **User access dashboard** (`GET /admin/user-access`): central table of all users with invite status and links.
- **Per-user resend** (`POST /admin/users/{user_id}/resend-invite`): resends the role-appropriate invite (business or partner only).
- Resend creates a new invite token and attempts delivery again.

## Admin user access dashboard

### List page: `/admin/user-access`

Use this page for support and operations when you need a single view of login accounts.

Columns include:

- email, role, active/inactive
- linked business name (business users)
- linked partner name and referral code (partners)
- latest invite purpose, status, created/expires/used timestamps
- actions: view detail, view linked business/partner, resend invite (when allowed)

Filters (query string, no JavaScript required):

- `role=business_user|partner|admin`
- `invite_status=sent|failed|skipped|accepted|expired|not needed`
- `q=` partial email search

### Detail page: `/admin/user-access/{user_id}`

Shows account metadata, linked business/partner, latest invite summary, and full invite history (token hashes are never shown).

### Finding invite status

1. Open `/admin/user-access`.
2. Search by email with `q=` or browse the table.
3. Check **Invite status** on the row (`sent`, `failed`, `skipped`, `accepted`, `expired`, `not needed`).
4. Open **Details** for invite history and delivery notes.

You can also check invite status on the business detail or partner application detail pages (entity-scoped resend buttons).

### How to resend invites

**From user access (recommended for support):**

1. Find the user on `/admin/user-access`.
2. Click **Resend invite** on the row or on the user detail page.
3. Confirm SMTP is configured on **System Check** if status stays `skipped`.
4. Ask the user to check email for the accept-invite link (valid 7 days, single use).

**From entity pages (still supported):**

- Business: `/admin/businesses/{id}` → Resend invite
- Partner application: `/admin/partners/{application_id}` → Resend invite

Admin accounts cannot receive business/partner invites; resend is disabled for `role=admin`.

### Support troubleshooting checklist

| Symptom | What to check |
|--------|----------------|
| User cannot log in | Active? Correct role? Password set via accept-invite? |
| Invite status `skipped` | `SMTP_HOST` and `SMTP_FROM_EMAIL` on System Check |
| Invite status `failed` | SMTP credentials/port; check server logs (no token values logged) |
| Invite status `expired` | Resend invite; user must use the new link within 7 days |
| Invite status `accepted` | User already set password; resend only if they need a fresh link |
| Invite status `not needed` | Existing user with access; resend from user access if a new link is required |
| Wrong business/partner link | User access detail → linked records; fix linkage on entity pages if wrong |
| Admin email conflict | Cannot convert admin email to business/partner login |

## Security rules

- No plaintext passwords in invite emails.
- No invite token values in normal logs.
- Existing `admin` user emails are blocked from conversion to partner/business invite flows.
- Session/role guards remain unchanged:
  - business users -> business routes only
  - partners -> partner routes only
  - admins -> admin routes

## Current limitations

- Invite status is derived from token state + delivery status; there is no full delivery event history UI yet.
- Existing users that already have access may show `not needed` unless resend is requested.
