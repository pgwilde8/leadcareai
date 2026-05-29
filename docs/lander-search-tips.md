# Lander search tips (LeadCareAI)

Organic landing pages are a **slow compounding channel**, not instant traffic. High CPC on answering-service keywords signals commercial intent; our angle is sharper than generic “phone answering service” copy:

```text
Backup Mode for missed calls — not a full live answering service.
```

**Recommendation:** Pause new lander pages until Google Search Console shows which URLs earn impressions. Do not add thin duplicate pages.

## Phase D completed (indexing readiness & CTA tracking)

- **Robots / sitemap:** `GET /robots.txt` and `GET /sitemap.xml` use `PUBLIC_BASE_URL` (or `APP_BASE_URL`) for absolute sitemap URLs; all `LANDER_ROUTES` are in `PUBLIC_SITEMAP_PATHS`.
- **CTA tracking:** `public/landers/_lander_cta.html` buttons use `data-analytics="lander_cta"`, `data-lander`, and `data-cta`. `layout/base.html` dispatches `leadcareai:lander_cta_click` on click (optional `gtag` if present). No GA/GTM bundle added.
- **Ops checklist:** [lander-indexing-checklist-v1.md](lander-indexing-checklist-v1.md) — deploy, GSC sitemap submit, priority URL indexing requests, 30–90 day measurement.

## Phase C completed (visual clarity & conversion)

- **Missed-call flow diagram:** `public/landers/_missed_call_flow.html` — 4-step HTML/CSS flow (missed call → instant text-back → job details → owner/team alerted) on priority landers.
- **Shared CTA:** `public/landers/_lander_cta.html` — “Stop letting missed calls become lost jobs” with demo + pricing/booking buttons (before FAQ on priority pages).
- **Video framing:** `public/landers/_lander_video_intro.html` — standard intro copy above embedded video; trade pages can override heading via `lander_video_heading`.
- **Who it is for:** `public/landers/_lander_fit.html` on pages without an equivalent section (alternative, business, contractors, plumbers, roofers). Hub and after-hours keep their existing fit copy.

## Phase B completed (site-wide linking & schema)

- **Footer + homepage:** `layout/_footer_guides.html` adds a compact **Guides** row (6 links) on every public page. Homepage section **“Explore missed-call recovery guides”** links to the hub and top pages.
- **Hub vs alternative roles:**
  - `/answering-service` — broad “answering service” guide (traditional call center vs. missed-call recovery).
  - `/answering-service-alternative` — “alternative” comparison page; cross-links to hub with distinct copy on each.
- **JSON-LD priority pages** (`WebPage` + `Service` + `BreadcrumbList` + `FAQPage` in `@graph`):
  - `/answering-service`, `/answering-service-alternative`, `/contractors-answering-service-alternative`, `/for/plumbers`, `/for/roofers`

## Current URL inventory (production routes)

| Path | Template | Role |
|------|----------|------|
| `/answering-service` | `answering-service.html` | **Hub** — broad “answering service” guide (traditional vs. missed-call recovery) |
| `/answering-service-alternative` | `answering-service-alternative.html` | **Alternative** — businesses comparing alternatives to traditional answering services |
| `/phone-answering-service` | `phone-answering-service.html` | Phone wording (not `/phone-answering-service-alternative`) |
| `/247-answering-service-alternative` | `247-answering-service-alternative.html` | 24/7 / after-hours angle |
| `/business-answering-service-alternative` | `business-answering-service-alternative.html` | Small business |
| `/virtual-answering-service-alternative` | `virtual-answering-service-alternative.html` | Virtual / remote receptionist |
| `/responsive-answering-service-alternative` | `responsive-answering-service-alternative.html` | Speed-to-lead |
| `/contractors-answering-service-alternative` | `contractors-answering-service-alternative.html` | Field-service / contractors |
| `/automated-answering-service-alternative` | `automated-answering-service-alternative.html` | Automation angle |
| `/after-hours-answering-service-alternative` | `after-hours-answering-service-alternative.html` | After-hours |
| `/answering-call-service-alternative` | `answering-call-service-alternative.html` | “Answering call service” wording |
| `/telephone-answering-service-alternative` | `telephone-answering-service-alternative.html` | Telephone wording |
| `/small-business-phone-answering-service-alternative` | `small-business-phone-answering-service-alternative.html` | SB + phone |
| `/small-business-answering-service-alternative` | `small-business-answering-service-alternative.html` | SB general |
| `/for/plumbers` | `plumbers.html` | Trade vertical |
| `/for/roofers` | `roofers.html` | Trade vertical |

**Legacy redirect:** `/for/answering-service-alternative` → `/answering-service-alternative` (301).

**Not built (future only):** `/for/hvac`, `/for/electricians`, `best-answering-service-alternative`.

All routes above are in `PUBLIC_SITEMAP_PATHS` (`app/services/public_seo_service.py`) and `LANDER_ROUTES` in `tests/test_public_landers.py`.

## Hub / child cluster structure

```text
                    /answering-service  (hub)
                           |
        +------------------+------------------+
        |                  |                  |
 /answering-service-   /phone-answering-   /business-...
  alternative            service            (child landers)
        |                  |
        +--------+---------+
                 |
    /contractors-answering-service-alternative
           /          \
    /for/plumbers   /for/roofers
```

Every lander extending `public/landers/_base.html` includes **“More answering service guides”** (`_lander_guides.html`) with links to the hub, key child pages, contractors, plumbers, and roofers (current page omitted when possible).

Industry pages also cross-link in body copy: plumbers ↔ roofers ↔ contractors ↔ hub.

## Standard marketing video

Most cluster pages use:

`https://our-cloud-storage.sfo3.cdn.digitaloceanspaces.com/leadcareai/marketing/video/Missed-Call_Safety_Net.mp4`

Trade pages may use trade-specific assets (e.g. `LeadCareAI_for_Roofers.mp4` on `/for/roofers`).

## What makes pages rank and convert

Nurture each page with:

- Clear search intent and honest positioning (missed-call recovery, not live operators)
- Title, H1, meta description aligned to target phrase
- Video (with `_lander_video_intro` framing), flow diagram, shared CTA, FAQ, comparison table where relevant
- JSON-LD (`WebPage` + `Service` + `BreadcrumbList` + `FAQPage` on priority pages listed above; other landers may still use `Service` only)
- Internal links (guides block + industry/hub links)
- Fast load, canonical, OG/Twitter

## Keyword angles (unique intent per page)

| Page | Intent angle |
|------|----------------|
| `/answering-service` | Head term — overview + links to children |
| `/answering-service-alternative` | Broad “alternative” for service businesses |
| `/phone-answering-service` | “Phone answering service” searches |
| `/business-answering-service-alternative` | Owner-operated / small business |
| `/247-answering-service-alternative` | Nights, weekends, always-on backup |
| `/virtual-answering-service-alternative` | Virtual receptionist alternative |
| `/responsive-answering-service-alternative` | Speed-to-lead |
| `/contractors-answering-service-alternative` | Jobsite / field work |
| `/for/roofers` | Roofing — storms, ladders, urgency |
| `/for/plumbers` | Plumbing — leaks, emergencies |

Do **not** publish many pages with the same copy and one keyword swapped — that cannibalizes the cluster.

## Measurement

**Google Search Console:** impressions, clicks, position, queries, indexed pages.

**Product analytics:** demo clicks, checkout, form submits, video plays.

Realistic organic timeline: indexing in 0–30 days; meaningful query data in 30–90 days; traction in 3–6+ months with ongoing improvements.

## Distribution (speed up beyond SEO)

YouTube → lander links, contractor groups, reps sending vertical URLs, paid tests on high-intent terms, partner collateral.

## References

- [Google SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)
- [Google Search Central documentation](https://developers.google.com/search/docs)
