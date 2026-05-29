# Lander indexing checklist (v1)

Operational steps to get the existing answering-service lander cluster into Google Search Console and measure early SEO signals. **Do not add new lander pages** until GSC shows which URLs earn impressions.

## Prerequisites

1. Set production public URL in environment:
   ```bash
   PUBLIC_BASE_URL=https://leadcareai.com
   ```
   (`APP_BASE_URL` may be used as fallback; prefer `PUBLIC_BASE_URL` for sitemap, robots, and canonicals.)

2. Deploy the build that includes:
   - `GET /robots.txt` — allows crawling, disallows admin/auth/checkout, lists sitemap
   - `GET /sitemap.xml` — absolute `<loc>` URLs for all public landers and marketing pages

## Post-deploy verification

| Check | URL | Expected |
|-------|-----|----------|
| Robots | `https://leadcareai.com/robots.txt` | `User-agent: *`, `Allow: /`, `Sitemap: https://leadcareai.com/sitemap.xml` |
| Sitemap | `https://leadcareai.com/sitemap.xml` | Valid XML `<urlset>`, hub `/answering-service`, trade `/for/plumbers`, `/for/roofers`, all cluster landers |
| Hub page | `https://leadcareai.com/answering-service` | 200, canonical, `index, follow` |

## Google Search Console

1. Add property for `https://leadcareai.com` (domain or URL prefix).
2. Submit sitemap: `https://leadcareai.com/sitemap.xml`
3. **Request indexing** (URL inspection → Request indexing) for priority URLs first:
   - `/answering-service`
   - `/answering-service-alternative`
   - `/business-answering-service-alternative`
   - `/after-hours-answering-service-alternative`
   - `/contractors-answering-service-alternative`
   - `/for/plumbers`
   - `/for/roofers`
4. Monitor **Pages** → indexed count and any crawl errors.

## What to measure (30–90 days)

Do not judge organic performance in the first few weeks. After 30–90 days, review in Search Console:

- **Impressions** and **clicks** by page URL
- **Queries** that trigger each lander (head term vs. alternative vs. trade)
- **Average position** on pages with meaningful impression volume

In product analytics (when wired), track lander CTA clicks via `data-analytics="lander_cta"`:

- Browser event: `leadcareai:lander_cta_click` (detail: `lander`, `cta`, `href`)
- Optional: forward to GA4/GTM using the same attributes — no script is bundled by default

## Pause rule

**Pause new lander pages** until Search Console shows which search intents get impressions on the current cluster. Improve titles, internal links, and CTAs on winning URLs instead of publishing more thin variants.

## Related docs

- [lander-search-tips.md](lander-search-tips.md) — cluster structure, phases A–D
- [production-launch-checklist-v1.md](production-launch-checklist-v1.md) — full production env checklist
