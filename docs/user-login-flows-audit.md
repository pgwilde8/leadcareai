# User Login Flows Audit

Date: 2026-05-28  
Scope: business client logins and partner sales rep logins

## 1) Current auth model

- **User model** (`app/models/user.py`)
  - `email` unique
  - `hashed_password` required
  - `role` string (used values: `admin`, `business_user`, `partner`)
  - `is_active` flag
- **Password hashing**
  - `passlib` bcrypt via `hash_password()` / `verify_password()` (`app/core/security.py`)
- **Session auth**
  - Cookie session keys: `user_id`, `user_role` (`app/routers/auth.py`)
  - Login checks `email + password hash` and `is_active`
- **Role redirects after login**
  - `admin` -> `/admin`
  - `partner` -> `/partner/dashboard`
  - `business_user` -> `/business/dashboard`
- **Access guards**
  - `require_admin`, `require_partner`, `require_business_user`
  - `business_user` must also have `BusinessUser` link (`get_primary_business_for_user`)

## 2) Business user flow (current)

- **Business creation path**
  - Prospect -> checkout flow creates/ensures `Business` (`business_lead_checkout_service.ensure_business_from_lead`)
  - Stripe `checkout.session.completed` marks business active (`handle_checkout_session_completed`)
- **Business user linkage**
  - No automatic `User` creation for paying business customer
  - No automatic `BusinessUser` link on payment completion
  - Existing admin tooling allows linking an existing user manually on business detail page
- **Credential delivery**
  - No business invite email flow currently
  - No set-password token flow currently
- **What is missing**
  - Automatic create/reuse business user account at payment conversion
  - Secure invite link (token) and set-password flow
  - Admin visibility for invite state

## 3) Partner user flow (current)

- **Application creation**
  - `/partner/onboard` creates `PartnerApplication` + signed docs
- **Admin approval**
  - `/admin/partners/{application_id}/approve` calls `partner_service.approve_application()`
  - Creates `Partner` record and links `Partner.user_id`
- **User creation/linking**
  - If email exists, may link and upgrade role to `partner` (`link_existing_user_as_partner`)
  - If new email, creates `User(role='partner')` with generated temporary password
- **Credential delivery**
  - Temporary password is shown one-time in admin UI (`partner_application_detail.html`)
  - No email invite token flow yet
- **What is missing**
  - Partner invite email with set-password link
  - Invite lifecycle status (sent/failed/accepted/expired)
  - Resend invite action

## 4) Email capability

- SMTP settings exist in config and `.env`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`
- Existing email sender in `notification_service._send_notification_email(...)`
  - Returns `sent|failed|skipped`
  - `skipped` when SMTP not configured
- Existing email templates are notification-focused (lead alerts), not user invite-focused
- Email failures are handled safely in notification flow (logged, non-fatal for webhook processing)

## 5) Security risks and gaps

- **Temporary password exposure**
  - Partner approval currently surfaces plaintext temporary password in admin UI (one-time display)
- **Plaintext credential distribution risk**
  - No password setup link; invites depend on sharing temporary password
- **Duplicate email collision handling**
  - `User.email` unique (good)
  - But partner role-linking can convert an existing `business_user` into `partner`, which may be undesired in mixed-account scenarios
- **Role escalation risk**
  - Existing role mutation paths should be explicit and constrained (admin email protected in `link_existing_user_as_partner`)
- **Cross-access protections**
  - Guards are present:
    - partner cannot access business routes
    - business_user cannot access partner routes
    - business_user scoped to linked business
- **Invite replay/expiration**
  - No invite token model today; no expiration/single-use controls

## Audit conclusion

The app has solid session/role guards, but login provisioning for non-admin users is incomplete and partially insecure (temporary password display). A minimal secure invitation-token flow is needed for both:

- business users after Stripe conversion
- partners after admin approval

with hashed token storage, expiry, single-use semantics, SMTP-backed invite emails, and admin invite status visibility.
