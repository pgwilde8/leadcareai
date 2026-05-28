# Production readiness — Phase 2I (partner W-9 / e-sign)

Checklist for deploying partner onboarding with encrypted W-9 collection and markdown-backed e-sign documents. **Not legal advice** — draft documents still require counsel review before production use with real contractors.

**Last verified:** 2026-05-28 (this environment)

---

## Verdict

| Area | Status |
|------|--------|
| Database migration | **Ready** — `20260528_0016 (head)`, `partner_tax_info` table present |
| Encryption key (this host) | **Configured** — `PARTNER_TAX_ENCRYPTION_KEY` is set (value not logged) |
| Document templates | **Ready** — 5 active templates after seed |
| Application code | **Ready** — compileall OK; Phase 2I behavior verified in code review |
| Full pytest (this host) | **284 passed, 1 failed** — see [Test note](#test-note) below |

**Production-ready for partner W-9 onboarding** when:

1. `APP_ENV=production` on the production host
2. `PARTNER_TAX_ENCRYPTION_KEY` is set in production secrets (same key across all app instances)
3. `alembic upgrade head` has been run on the production database
4. `python scripts/seed_partner_documents.py` has been run after deploy (or in release step)
5. Legal has reviewed draft partner documents (placeholders still contain `DRAFT PLACEHOLDER` warnings)

---

## Required environment variable

| Variable | Required | Notes |
|----------|----------|--------|
| `PARTNER_TAX_ENCRYPTION_KEY` | **Yes** in production | Fernet key; must be stable for the life of stored TINs |
| `APP_ENV` | **Yes** | Must be `production` on production hosts |
| `DATABASE_URL` | **Yes** | PostgreSQL URL used by app and Alembic |

Documented in `.env.example`:

```bash
PARTNER_TAX_ENCRYPTION_KEY=
```

### Generate a Fernet key (run once per environment)

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the output in your secrets manager or production `.env` / platform env config. **Never commit the key to git. Never log it.**

### If the key is missing in production

- `POST /partner/onboard` with W-9 fields returns **400** with a form error mentioning `PARTNER_TAX_ENCRYPTION_KEY`.
- No `partner_application` / `partner_tax_info` row is committed (transaction rolls back on `ValueError`).
- Fix: set `PARTNER_TAX_ENCRYPTION_KEY`, restart app workers, retry onboarding.

### If the key is lost or rotated incorrectly

- Existing `partner_tax_info.tin_encrypted` values **cannot be decrypted** without the original key.
- Admin masked TIN may show `***-**-****` or decryption errors are handled without exposing plaintext.
- **There is no V1 admin “reveal TIN” UI.** Recovery requires partners to re-submit tax info (operational process), not a code toggle.

---

## Security warnings

1. **Backups** — Database backups contain `tin_encrypted`. Treat backups like secret-bearing data; restrict access and encrypt backup storage.
2. **Key storage** — Keep `PARTNER_TAX_ENCRYPTION_KEY` only in secrets (env / vault). Do not paste into tickets, chat, or application logs.
3. **Logs** — Partner onboard and tax services do not log plaintext TIN or the encryption key. Decryption failures log a generic message only (`field_encryption.py`).
4. **Admin UI** — Only `tax_info.tin_masked` is passed to templates; `tin_encrypted` is never rendered.
5. **Plaintext TIN** — Stored only as `tin_encrypted` in PostgreSQL. Model has no plaintext TIN column.

---

## Deployment commands

### 1. Migration check

```bash
cd /srv/projects/leadcareai
alembic current
```

Expected:

```text
20260528_0016 (head)
```

Apply if behind:

```bash
alembic upgrade head
```

### 2. Confirm table exists

```bash
python -c "
from sqlalchemy import create_engine, inspect
from app.core.config import get_settings
e = create_engine(get_settings().database_url)
print('partner_tax_info' in inspect(e).get_table_names())
"
```

Expected: `True`

### 3. Seed partner documents

```bash
python scripts/seed_partner_documents.py
```

Expected: **5** active templates:

- `independent_contractor_agreement`
- `commission_schedule_acknowledgment`
- `acceptable_marketing_policy`
- `privacy_data_handling`
- `electronic_signature_notice`

Seed does **not** overwrite template `body` when `partner_signed_documents` already reference that template (signed snapshots remain unchanged).

### 4. Smoke checks after deploy

```bash
python -m compileall app
pytest -q
```

---

## What admin should verify

1. Log in as admin → `/admin/partners`
2. Open a new application → `/admin/partners/{application_id}`
3. Confirm **W-9 / tax information** section shows:
   - Legal name, address, tax classification, TIN type
   - **TIN (masked)** only (e.g. `***-**-6789` or `**-***6789`)
   - Certified timestamp
4. Confirm **no** full SSN/EIN, no `tin_encrypted` blob, no “Reveal TIN” control
5. Confirm **Signed documents** section lists 5 documents with snapshots and signature metadata
6. Confirm draft banner / document text still marked for legal review before go-live

---

## Technical verification summary

### Database

- Alembic head: `20260528_0016`
- Table `partner_tax_info` with columns including `tin_encrypted` (no plaintext TIN column)
- `PartnerTaxInfo` registered in `app/models/__init__.py` for Alembic/metadata

### Encryption config

- `field_encryption._fernet()` raises `ValueError` with `PARTNER_TAX_ENCRYPTION_KEY` in message when key empty and `APP_ENV=production`
- `partner_tax_service.create_partner_tax_info_for_application()` calls `encrypt_field(data.tin)` only
- Key and plaintext TIN are not logged in partner onboard or tax service code paths

### Admin safety

- `admin.py` passes `tax_info_masked` (`PartnerTaxInfoMasked`) only
- `partner_application_detail.html` uses `tax_info.tin_masked`; no reveal button in templates

### Partner onboarding (`/partner/onboard`)

- Template includes W-9 section, collapsible document previews, one typed signature
- Successful POST creates: `partner_applications`, `partner_tax_info`, `partner_signed_documents` (one per active template)
- Invalid TIN length/type returns 400 with validation message; `db.rollback()` on error
- TIN input uses `type="password"` on form (not echoed on validation error re-render for password field)

### Document templates

- Bodies loaded from `app/templates/partner/documents/{code}.md`
- Snapshots stored at sign time in `partner_signed_documents.document_snapshot`

---

## Test isolation

Partner tax tests use `tests/settings_helpers.patch_get_settings()` to build `Settings(_env_file=None, ...)` and patch `get_settings` in `app.core.config` and `app.core.field_encryption`, so tests do not depend on repo `.env` for encryption behavior.

---

## Related documentation

- [partner-esign-v1.md](./partner-esign-v1.md) — Architecture and limitations
- [partner-program-v1.md](./partner-program-v1.md) — Partner lifecycle

---

## Pre-launch checklist (copy for deploy ticket)

Verify live status at **`/admin/system-check`** and complete **`docs/production-launch-checklist-v1.md`** before go-live.

- [ ] `APP_ENV=production`
- [ ] `PARTNER_TAX_ENCRYPTION_KEY` set in production secrets (backed up in vault)
- [ ] `alembic current` → `20260528_0016 (head)`
- [ ] `partner_tax_info` table exists in production DB
- [ ] `python scripts/seed_partner_documents.py` run on production
- [ ] 5 active document templates confirmed
- [ ] Admin smoke test: masked TIN on `/admin/partners/{id}`
- [ ] Legal review of draft partner documents completed (or onboarding kept disabled until done)
- [ ] Backup/restore runbook notes encryption key dependency
