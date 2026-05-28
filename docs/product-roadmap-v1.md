# LeadCareAI Product Roadmap (V1)

This document turns current product notes into a practical roadmap: what is live, what to ship next, and what to defer.

## Product Positioning

LeadCareAI helps local service businesses recover missed-call leads by instantly texting callers, qualifying them by SMS, and alerting staff with a clean summary.

Core promise:

> "Stop losing customers when you miss calls."

## Ideal Customer Profile

Primary targets:

- Plumbing
- HVAC
- Roofing
- Electrical
- Landscaping
- Remodeling
- Med spas
- Real estate
- Insurance offices
- Any business that depends on inbound calls

## V1 Outcome

When a business misses a call:

1. Caller receives an immediate text-back.
2. AI collects key intake details over SMS.
3. Staff receives an alert and can see lead context in dashboard.
4. Team follows up quickly with full context.

## Current Scope (Live / Baseline)

- Twilio inbound SMS webhook
- Twilio voice missed-call webhook
- Missed-call text-back
- AI SMS intake qualification
- Lead creation/reuse and message history
- Business dashboard (lead inbox/detail/status)
- Business settings (including custom missed-call text-back)
- Business notifications (email + staff SMS, best effort)
- Partner onboarding and referrals
- Admin operations and compliance workflows

## V1 Guardrails

V1 should do:

- Missed-call recovery by SMS
- Lead qualification and summary
- Staff alerts
- Simple lead management

V1 should not do (yet):

- Full receptionist replacement
- Guaranteed appointment booking without calendar integration
- Exact pricing quotes by AI
- Hard promises on dispatch ETA
- Quiet hours / complex notification rules
- Voice AI conversations

## Messaging and Offer

Suggested offer:

- One-time setup: `$199`
- Monthly service: `$147/month`

What setup includes:

- Dedicated messaging number activation
- SMS compliance onboarding
- AI profile configuration
- End-to-end testing and go-live

## Demo Strategy (High Priority)

Primary CTA should be a live product demo, not only a form.

Suggested flow:

1. Prospect sees demo page.
2. Prospect calls demo number and gets no live answer.
3. LeadCareAI instantly texts prospect.
4. Prospect replies by SMS; AI asks intake questions.
5. Prospect logs into demo dashboard and sees lead appear.

### Demo Safety Requirements

- Demo dashboard is read-only.
- Mask phone numbers (show only last 4 digits by default).
- Do not expose full lead lists or sensitive PII broadly.
- Demo user cannot edit/delete/send/admin.

## Recommended SMS Intake Sequence

Order of questions:

1. Service/problem
2. Urgency + town/location
3. Customer name
4. Best email
5. Preferred callback window
6. Confirmation and handoff message

## Operating Model: White-Glove Onboarding

This is a feature, not a bug. Position setup as "compliance and deliverability activation."

Operational flow:

1. Business signs up and submits onboarding info.
2. Team reviews business/compliance profile.
3. Twilio number and account setup/assignment.
4. Compliance registration process (as needed).
5. Number marked active in platform.
6. Customer runs test call to verify missed-call recovery.

## 30-Day Build Priorities

1. Demo landing page and read-only demo dashboard
2. Hardened webhook reliability and monitoring
3. Message template polish (customer + staff)
4. Better onboarding UX around call forwarding
5. Usage/cost visibility by business for AI and messaging

## Call Forwarding Onboarding (Critical)

Customer-friendly explanation:

> "You keep your current number. If you miss a call, your phone provider forwards that unanswered/busy call to your LeadCareAI recovery number, and we text the caller instantly."

Onboarding should ask:

- Phone provider/carrier
- Mobile vs landline vs VoIP
- Whether conditional forwarding is already enabled

Then provide provider-specific instructions and a "Test Setup" button.

## Product Roadmap

### V1 (Now)

- Missed-call text-back
- AI SMS intake
- Staff alerts
- Dashboard/history
- Manual status tracking

### V2 (Next)

- Business-trained AI profile controls (tone/rules/services)
- Better qualification/scoring and urgency routing
- Improved summaries and follow-up automation

### V3 (Later)

- Calendar and scheduling integrations
- Deeper CRM/job-system integrations
- Voice AI and call summaries
- Outbound campaigns and lifecycle automation

## Data and Architecture Principles

Tenant safety:

- All business context must be scoped by `business_id`.
- Never mix cross-business context in AI prompts.

Keep simple first:

- Use structured business fields and rules first.
- Add RAG/vector retrieval only when document volume justifies it.

## Success Metrics

Primary:

- Missed-call recovery rate
- First response speed
- Lead-to-contact rate
- Lead-to-booked-job rate

Secondary:

- Alert delivery success rate
- AI completion rate for intake flow
- Dashboard engagement by business users

## Risks and Mitigations

- **Carrier forwarding complexity** -> provide guided onboarding + support
- **Compliance delays** -> set clear expectations and onboarding status visibility
- **Overpromising AI** -> enforce response guardrails and transparent UX wording
- **PII exposure in demos** -> masking + strict read-only demo permissions

## Recommended Homepage Line

> "When you miss a call, LeadCareAI instantly texts the caller, collects job details, and sends your team a ready-to-follow-up lead."
