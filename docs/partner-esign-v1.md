# Partner e-sign and W-9 (V1)

LeadCare AI uses an **in-house electronic signature** flow for partner onboarding. This is not legal advice; all draft documents must be reviewed by qualified counsel before production use.

## Architecture

1. **Markdown templates** — Active document bodies live under `app/templates/partner/documents/{code}.md`. The partner document service loads them via `load_document_body(code)` and seeds `partner_document_templates`.
2. **Signing** — After admin issues a tokenized link, `POST /partner/sign-documents` collects one **typed signature** and electronic consent. `sign_documents_for_application()` creates one `partner_signed_documents` row per active template.
3. **Snapshots** — Each signed row stores a full **document snapshot** at signing time. Updating template bodies in the database does **not** change snapshots for applications that already signed.
4. **Signed copies by email** — After a successful `POST /partner/sign-documents`, the app emails plain-text `.txt` attachments (one per signed document) to the applicant and to the legal/admin inbox (`DEFAULT_SUPPORT_EMAIL`, else `ADMIN_EMAIL`). Delivery uses SMTP when configured; signing and `docs_signed` status are **not** rolled back if email fails.
5. **W-9 / tax info** — `partner_tax_info` stores mailing address, classification, and **Fernet-encrypted** TIN. Plaintext TIN exists only transiently in the HTTP request handler.

## Document catalog (V1)

| Code | Title |
|------|--------|
| `independent_contractor_agreement` | Independent Contractor Agreement |
| `commission_schedule_acknowledgment` | Commission Schedule Acknowledgment |
| `acceptable_marketing_policy` | Acceptable Marketing Policy |
| `privacy_data_handling` | Privacy / Data Handling |
| `electronic_signature_notice` | Electronic Signature and Records Notice |

Legacy code `partner_program_terms` is deactivated on seed; new applications use the five documents above.

Seed or refresh templates from markdown:

```bash
python scripts/seed_partner_documents.py
```

Seed behavior:

- Creates missing templates from markdown files.
- Does **not** overwrite template body when signed documents already reference that template/version.
- Deactivates legacy templates where applicable.

## Environment

| Variable | Purpose |
|----------|---------|
| `PARTNER_TAX_ENCRYPTION_KEY` | Fernet key (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |

In **production** (`APP_ENV=production`), W-9 submission fails with a clear error if this key is missing. Never log the key or plaintext TIN.

## Admin review

- List: `/admin/partners`
- Detail: `/admin/partners/{application_id}`

Admins see W-9 fields with **masked TIN only** (e.g. `***-**-6789` for SSN, `**-***6789` for EIN). There is no reveal button in V1.

## Signed document email copies

- Helper: `format_signed_document_copy_text()` in `partner_signed_document_copy_service.py`
- Trigger: `send_signed_document_copy_emails()` after DB commit on successful signing
- Partner subject: `Your signed LeadCareAI partner documents`
- Admin subject: `Partner documents signed: {applicant name}`
- Attachments: `{document_code}-signed.txt` (plain text; no PDF)

## Limitations (V1)

- Typed signature only — no drawn/canvas signature, no DocuSign/PandaDoc integration.
- No partner dashboard download of signed docs; email + admin detail page are the V1 copy paths.
- No DocuSign-level identity proof or KYC.
- No automated 1099 filing.
- No bank account or payout collection in onboarding.
- No admin UI to reveal full TIN.
- Draft document text includes explicit placeholder warnings until counsel approves final language.

## Related docs

- [partner-program-v1.md](./partner-program-v1.md) — Full partner lifecycle and commissions policy.
