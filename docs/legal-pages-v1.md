# Legal and compliance pages (V1)

Public draft policies for LeadCareAI before production launch. **Not legal advice** — have qualified counsel review before Twilio A2P 10DLC filings, Stripe disclosures, or customer contracts.

## Routes

| URL | Page | Legacy aliases |
|-----|------|----------------|
| `/privacy` | Privacy Policy | `/legal/privacy` |
| `/terms` | Terms of Service | `/legal/terms` |
| `/sms-terms` | SMS Terms | `/sms`, `/legal/sms`, `/legal/sms-terms` |
| `/refund-policy` | Refund & Cancellation Policy | `/legal/refund-policy` |
| `/contact` | Contact form | — |

Templates: `app/templates/legal/*.html`  
Router: `app/routers/public.py`  
Footer: `app/templates/layout/_footer.html`

## Purpose of each page

| Page | Primary audience | Why it exists |
|------|------------------|---------------|
| **Privacy** | Customers, consumers, partners | Data collection/use, third-party processors, SMS consent, security |
| **Terms** | Paying businesses | Service scope, responsibilities, payments, AI limits, disclaimers |
| **SMS Terms** | Consumers + Twilio/carriers | A2P 10DLC program description, STOP/HELP, rates, no third-party marketing sharing |
| **Refund** | Paying businesses | Setup fee, Stripe billing, cancellation, forwarding limitations |
| **Contact** | All | Support intake |

## Contact email

Legal pages use `LEGAL_CONTACT_EMAIL` (default `paul@leadcareai.com`) via `settings.legal_contact_email`. The contact form may still deliver to `DEFAULT_SUPPORT_EMAIL`.

## Twilio A2P relevance

**Registration packet:** [a2p-registration-packet-v1.md](a2p-registration-packet-v1.md) — campaign description, sample messages, opt-in/out, URLs, and message flags for copy/paste. Admin reference: `/admin/a2p-packet`.

SMS Terms and Privacy include language commonly needed for campaign registration:

- Program name and description
- Consent model (call/text/form → service-related messages)
- Message frequency varies
- Message and data rates may apply
- **STOP** / **HELP**
- Support contact
- Link to Privacy Policy (`/privacy`)
- Mobile opt-in / SMS consent **not sold or shared for third-party marketing**

Carriers control call forwarding; Terms and Refund state forwarding is customer-configured and not universally guaranteed.

## Privacy / SMS language checklist

- [x] Business, lead, phone, message, login, payment, partner/W-9 data described
- [x] Uses: missed-call recovery, notifications, AI intake, Stripe, commissions
- [x] Twilio, Stripe, OpenAI, SMTP, hosting listed as processors
- [x] SMS opt-in not sold/shared for third-party marketing
- [x] STOP / HELP and correction/deletion contact path
- [x] Reasonable security; encrypted partner TIN; no perfect-security guarantee
- [x] No HIPAA compliance claim

## Terms highlights

- Service description (SMS intake, dashboard, Backup Mode guidance, notifications)
- Customer duties (forwarding, testing, accurate info, lawful use)
- Growth pricing reference ($199 setup + $147/mo) in Refund; Terms references Stripe
- Not 911 / emergency services
- AI limitations; business remains responsible for customer decisions
- Carrier forwarding not guaranteed

## Attorney-review limitations

- Pages are **V1 drafts** with an on-page draft notice
- Not marked as attorney-reviewed
- Do not claim HIPAA, emergency dispatch, universal carrier forwarding, or guaranteed lead conversion
- Industry-specific compliance (TCPA, state laws, contractor classification) may require counsel
- Partner program documents are separate (`docs/partner-program-v1.md`)

## Tests

`tests/test_legal_pages.py` — HTTP 200, required phrases, footer links, draft notice.

## Implementation notes

- No changes to Twilio webhooks, Stripe logic, or checkout flow (footer links only)
- `/sms` kept for backward compatibility; canonical public link is `/sms-terms`
