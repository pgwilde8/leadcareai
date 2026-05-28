# LeadCare AI — Foundation Audit

**Audit date:** 2026-05-27  
**Project path:** `/srv/projects/leadcareai`  
**Deploy target (from docs):** `134.199.242.254:8788` (`PORTS-README.md`)

This audit was performed **before Milestone 1 feature code**. The repo is a **scaffold only**: directory tree and empty placeholder files exist; no application logic is implemented yet.

---

## 1. Current project structure

### 1.1 Documentation and config (root)

| Path | Status | Notes |
|------|--------|-------|
| `README1.md` | **Present, complete** | Full engineering spec (~1,638 lines): architecture, data model, routes, milestones |
| `LEADCAREAI.md` | **Present, partial** | Short product brief (pricing, industries); ends mid–section 1 |
| `README.md` | **Empty** | Placeholder only |
| `PROJECT_AUDIT.md` | **This file** | Foundation audit |
| `.env.example` | **Present, populated** | 45 lines; template for all integration keys |
| `.env` | **Present, populated** | Local copy; `APP_BASE_URL` incomplete (`http://localhost:`); billing return URL uses port `8788` |
| `.gitignore` | **Empty** | No ignore rules yet |
| `requirements.txt` | **Empty** | No pinned dependencies |
| `requirements-dev.txt` | **Empty** | No dev dependencies |
| `pyproject.toml` | **Empty** | No tool config |
| `pytest.ini` | **Empty** | No pytest settings |
| `alembic.ini` | **Empty** | Alembic not configured |
| `docker-compose.yml` | **Empty** | No local Postgres/Redis services defined |
| `Dockerfile` | **Empty** | No container build |
| `nginx-leadcareai.conf` | **Empty** | No reverse-proxy config |
| Git repository | **Not initialized** | `git status` fails: not a git repo |

### 1.2 Main app entrypoint

| Path | Status |
|------|--------|
| `app/main.py` | **Empty** — no `FastAPI()` instance, no router includes, no middleware |

**Boot status:** App cannot start. `uvicorn app.main:app` would fail (no `app` attribute).

### 1.3 Existing routers (`app/routers/`)

All router modules exist as **empty files** (0 bytes):

| File | Intended role (from `README1.md`) |
|------|-----------------------------------|
| `public.py` | Marketing: `/`, `/pricing`, `/demo`, `/partners`, `/apply` |
| `auth.py` | Login, logout, session |
| `business_dashboard.py` | Business lead inbox, settings, billing UI |
| `partner_dashboard.py` | Partner referrals, commissions (Milestone 7+) |
| `admin.py` | Platform admin: businesses, partners, commissions |
| `webhooks_twilio.py` | Voice/SMS webhooks (Milestone 3+) |
| `webhooks_stripe.py` | Stripe webhooks (Milestone 6+) |

`app/routers/__init__.py` is empty (no package exports).

### 1.4 Existing models (`app/models/`)

All model modules exist as **empty files**:

| File | Spec tables (README) | Milestone 1 need |
|------|----------------------|------------------|
| `user.py` | `users` | **Yes** |
| `business.py` | `businesses` | **Yes** |
| `lead.py` | `leads` | No (Milestone 2) |
| `message.py` | `sms_messages` | No (Milestone 3) |
| `partner.py` | `partners` | No (Milestone 7) |
| `commission.py` | `commissions` | No (Milestone 8) |
| `billing.py` | subscriptions / payment sync | No (Milestone 6) |

**Not scaffolded (listed in README §5):** `phone_number.py`, `audit_log.py`, and join tables (`business_users`, `business_settings`, etc.) — add when their milestone needs them.

### 1.5 Existing schemas (`app/schemas/`)

Empty placeholders only:

- `business.py`, `lead.py`, `partner.py`, `billing.py`
- **Missing vs README:** `user.py`, `message.py`, `commission.py` (not required for Milestone 1)

### 1.6 Existing services (`app/services/`)

Empty placeholders only:

| File | Milestone |
|------|-----------|
| `twilio_service.py` | 3–4 (do not implement yet) |
| `sms_service.py` | 3 |
| `ai_service.py` | 5 (do not implement yet) |
| `lead_service.py` | 2–4 |
| `commission_service.py` | 8 (do not implement yet) |
| `stripe_service.py` | 6 (do not implement yet) |
| `notification_service.py` | 4–5 |

**Missing vs README:** `business_service.py`, `partner_service.py`, `report_service.py`

### 1.7 Core (`app/core/`)

| File | Status |
|------|--------|
| `config.py` | Empty — no `Settings` / env loading |
| `database.py` | Empty — no engine, `SessionLocal`, `Base`, `get_db` |
| `security.py` | Empty — no password hash / session helpers |
| `logging.py` | Empty — no logger setup |
| `permissions.py` | **Not created** (README lists for RBAC later) |

### 1.8 Background jobs (`app/jobs/`)

Empty: `followups.py`, `monthly_reports.py`, `commission_approval.py`  
README also names `reports.py`, `commissions.py`, `notifications.py` — naming differs; defer until Milestone 9.

### 1.9 Templates (`app/templates/`)

Only `.gitkeep` in:

- `public/`, `business/`, `partner/`, `admin/`

**Missing vs README:** `base.html`, `auth/login.html`, all named HTML pages (§5). No Jinja layouts exist.

### 1.10 Static assets (`app/static/`)

- `css/.gitkeep`, `js/.gitkeep` only  
- **Missing:** `app.css`, `app.js` (README)

### 1.11 Tests

| Location | Contents |
|----------|----------|
| `tests/conftest.py` | Empty |
| `tests/test_health.py` | Empty |
| `app/tests/.gitkeep` | Placeholder only |

README also lists `test_auth.py`, `test_twilio_webhooks.py`, `test_stripe_webhooks.py`, `test_commissions.py`, `test_leads.py` — not scaffolded.

**Duplicate test roots:** `tests/` (root) and `app/tests/` — pick **root `tests/`** for pytest (matches `crewassistai` / README dev setup); avoid splitting later.

### 1.12 Alembic / migrations

| Path | Status |
|------|--------|
| `alembic.ini` | Empty |
| `alembic/env.py` | Empty |
| `alembic/script.py.mako` | Empty |
| `alembic/versions/` | `.gitkeep` only — no migrations |

README mentions `migrations/` at repo root; project uses `alembic/` (acceptable — standard Alembic layout).

### 1.13 Scripts / Docker

| Path | Status |
|------|--------|
| `scripts/run.sh`, `migrate.sh`, `seed.sh` | Empty |
| `docker/.gitkeep` | Empty dir |

### 1.14 Runtime environment

| Check | Result |
|-------|--------|
| Project venv (`.venv` / `venv`) | **None** |
| System Python | 3.10.12 at `/usr/bin/python3` |
| System `fastapi` | 0.115.12 (global install) |
| System `pytest` | 7.4.3 (global install) |
| PostgreSQL / Redis running | **Not verified** in this audit |

### 1.15 Python file inventory

- **43** `.py` files under `app/` — **all 0 bytes**
- `compileall` succeeds on empty modules (valid empty Python files)

---

## 2. Foundation readiness checklist

| Item | Ready? | Evidence |
|------|--------|----------|
| FastAPI app boots | **No** | `app/main.py` empty |
| Settings/config loads from env | **No** | `app/core/config.py` empty; `.env` exists but unused |
| Database session configured | **No** | `app/core/database.py` empty |
| Alembic configured | **No** | `alembic.ini`, `alembic/env.py` empty |
| Base model available | **No** | No SQLAlchemy `Base` |
| User model exists | **No** | File exists, no ORM class |
| Business model exists | **No** | File exists, no ORM class |
| Auth exists | **No** | `auth.py`, `security.py` empty |
| Admin routes exist | **No** | `admin.py` empty |
| Public routes exist | **No** | `public.py` empty |
| Tests can run | **No** | Empty test modules; pytest collects 0 tests |

**Overall foundation readiness: 0 / 11** — scaffold only, ready for Milestone 1 implementation.

---

## 3. Missing foundation pieces

### 3.1 Must have for Milestone 1 (not implemented)

**Application core**

- [ ] `requirements.txt` — FastAPI, uvicorn, SQLAlchemy, Alembic, psycopg, pydantic-settings, python-multipart, jinja2, bcrypt (or passlib), python-dotenv
- [ ] `requirements-dev.txt` — pytest, httpx (TestClient)
- [ ] `.gitignore` — `.env`, `venv/`, `__pycache__/`, `.pytest_cache/`
- [ ] `app/main.py` — `FastAPI()`, mount static, include routers, `/health`
- [ ] `app/core/config.py` — `Settings` from `.env` (match `.env.example` keys)
- [ ] `app/core/database.py` — engine, `Base`, `SessionLocal`, `get_db`
- [ ] `app/core/logging.py` — basic logger
- [ ] `app/core/security.py` — password hash/verify (bcrypt)
- [ ] `app/models/user.py` — `User` ORM + roles enum
- [ ] `app/models/business.py` — `Business` ORM + status enum
- [ ] `app/models/__init__.py` — import models for Alembic metadata
- [ ] Alembic init content — `alembic.ini`, `env.py` wired to `app.core.database`
- [ ] Initial migration — `users`, `businesses` tables (and `business_users` if multi-user in M1)

**Auth & access**

- [ ] Session middleware (Starlette `SessionMiddleware`) or signed cookie strategy
- [ ] `app/routers/auth.py` — login/logout (form POST + redirect)
- [ ] `app/core/permissions.py` or deps in `auth` — `require_admin`, `get_current_user`
- [ ] Seed script or startup hook — create admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD`

**Routes & UI (minimal)**

- [ ] `app/routers/public.py` — `GET /` landing (Jinja)
- [ ] `app/routers/admin.py` — `GET /admin/businesses` list (admin-only)
- [ ] `app/templates/base.html`, `public/index.html`, `auth/login.html`, `admin/businesses.html`
- [ ] `app/static/css/app.css` — minimal styles (optional for M1)

**Tests**

- [ ] `tests/conftest.py` — TestClient, test DB or sqlite override
- [ ] `tests/test_health.py` — `GET /health` → 200
- [ ] `tests/test_auth.py` — admin login + RBAC smoke (recommended in M1)
- [ ] `pytest.ini` — `testpaths = tests`

**Docs**

- [ ] `README.md` — how to install, migrate, run (short; link to `README1.md`)

### 3.2 Scaffolded but intentionally deferred (post–Milestone 1)

Do **not** implement in Milestone 1:

| Area | Files / features |
|------|------------------|
| Twilio | `webhooks_twilio.py`, `twilio_service.py`, `sms_service.py` |
| Stripe | `webhooks_stripe.py`, `stripe_service.py`, `billing` models |
| AI | `ai_service.py` |
| Commissions | `commission_service.py`, `commission` model logic, `jobs/commission_approval.py` |
| Partner UI | `partner_dashboard.py`, partner templates |
| Business product UI | `business_dashboard.py` beyond stub if needed |
| Leads | `lead.py` model/routes (Milestone 2) |
| Jobs | `followups.py`, `monthly_reports.py`, Redis/RQ worker |

### 3.3 Spec vs scaffold gaps (track, do not block M1)

| README1 item | Repo today | Action |
|--------------|------------|--------|
| `core/permissions.py` | Missing file | Add in M1 with RBAC deps |
| `models/phone_number.py`, `audit_log.py` | Missing | Milestone 3+ / admin hardening |
| `schemas/user.py`, `message.py`, `commission.py` | Missing | When routes need them |
| `services/business_service.py`, etc. | Missing | Optional thin layer in M1 or inline in routers |
| `templates/auth/`, many HTML pages | Missing dirs/files | Add incrementally per route |
| `jobs/reports.py` vs `monthly_reports.py` | Name mismatch | Keep current names unless refactoring |
| `app/tests/` vs `tests/` | Duplicate intent | Use root `tests/` only |

### 3.4 Tiny fixes applied in this audit

**None.** No code was added. Empty scaffold is intentional; boot failures are expected until Milestone 1 starts.

---

## 4. Recommended Milestone 1 plan

**Goal:** Prove the boring foundation — app runs, config loads, DB migrates, admin can log in and list businesses, public landing loads.

**Out of scope for M1:** Twilio, Stripe, OpenAI, commissions, partner dashboards, lead inbox, AI, background workers.

### Phase 1A — Tooling & boot (day 1)

1. Fill `requirements.txt` / `requirements-dev.txt` (pin versions consistent with `/srv` siblings, e.g. `crewassistai`).
2. Create `.venv` and `pip install -r requirements.txt -r requirements-dev.txt`.
3. Fill `.gitignore`.
4. Implement `app/core/config.py` reading `.env.example` keys (fail fast on missing `SECRET_KEY` in prod only; allow dev defaults).
5. Implement `app/core/database.py` + `app/core/logging.py`.
6. Implement `app/main.py`:
   - `GET /health` → `{"status": "ok"}`
   - Include `public` and `auth` routers only (admin included; others not mounted or return 501 stub).
7. Fill `pytest.ini`; implement `tests/test_health.py`.
8. **Acceptance:** `uvicorn app.main:app --port 8788` starts; `pytest -q` passes health test.

### Phase 1B — Database & models (day 1–2)

1. Configure `alembic.ini` + `alembic/env.py` targeting `app.core.database.Base`.
2. Implement `User` (`users`): id, email, hashed_password, full_name, role, is_active, timestamps.
3. Implement `Business` (`businesses`): id, name, industry, status, timestamps; optional `stripe_customer_id` nullable for later.
4. Optional M1: `business_users` association (owner link) — needed if business users log in in M1; otherwise admin-only business CRUD first.
5. Run `alembic revision --autogenerate` + `alembic upgrade head`.
6. **Acceptance:** Tables exist in Postgres; no manual SQL.

### Phase 1C — Security & auth (day 2)

1. Implement `app/core/security.py` (bcrypt hash/verify).
2. Session middleware in `main.py` (`secret_key` from settings).
3. `auth.py`: `GET/POST /login`, `POST /logout`; redirect admin → `/admin/businesses`.
4. Admin seed: CLI in `scripts/seed.sh` or one-off migration — user from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
5. Dependency `require_role("admin")` for admin routes.
6. **Acceptance:** Admin login works; unauthenticated `/admin/*` redirects to login.

### Phase 1D — Admin & public UI (day 2–3)

1. `public.py`: `GET /` — simple Jinja landing (“Stop losing customers when you miss calls”).
2. `admin.py`: `GET /admin/businesses` — table of businesses; `POST` create business (minimal form).
3. Templates: `base.html`, `public/index.html`, `auth/login.html`, `admin/businesses.html`.
4. `tests/test_auth.py`: login success/failure, admin route 401/redirect.
5. **Acceptance (README Milestone 1):**
   - Admin can log in.
   - Admin can create/view businesses.
   - Business user login — **defer to M1.5** if `business_users` not in scope; document decision.
   - Business user sees only assigned business — **defer** until `business_users` exists.

### Phase 1E — README & ops

1. Fill `README.md` with: venv, `cp .env.example .env`, docker compose (when added), migrate, run, test.
2. Optional: minimal `docker-compose.yml` for Postgres only.
3. `git init` + initial commit (user-requested).

### Suggested file fill order

```
requirements.txt → .gitignore → config.py → database.py → logging.py
→ main.py (/health) → test_health.py
→ user.py → business.py → alembic → migration
→ security.py → auth.py → admin.py → public.py → templates
→ test_auth.py → README.md
```

### Milestone 1 definition of done (adjusted for “boring first”)

| Criterion | Include in M1? |
|-----------|----------------|
| App boots on port 8788 | Yes |
| Config from `.env` | Yes |
| Alembic migrations run | Yes |
| Admin login | Yes |
| Admin list/create businesses | Yes |
| Public landing `/` | Yes |
| Business user login + scoped access | **M1.5** (needs `business_users`) |
| Twilio / Stripe / AI / commissions | **No** |

---

## 5. Risks

### 5.1 Configuration

| Risk | Detail | Mitigation |
|------|--------|------------|
| Incomplete `APP_BASE_URL` | `.env` has `http://localhost:` (no port) | Set `http://localhost:8788` to match `PORTS-README.md` |
| Empty `requirements.txt` | Reproducible installs impossible | Pin deps in M1 Phase 1A |
| No project venv | Relies on global FastAPI/pytest | Always use `.venv` per project |
| Postgres not provisioned | `DATABASE_URL` points to `leadcare` DB | Add `docker-compose` Postgres or document create DB/user |
| Secrets in `.env` | File exists on disk | Ensure `.gitignore` before `git init`; never commit `.env` |

### 5.2 Code / imports

| Risk | Detail |
|------|--------|
| All modules empty | Any import from `app.models` etc. will fail until implemented |
| Duplicate test dirs | `app/tests/` vs `tests/` may confuse pytest discovery |
| Router mount order | Not applicable yet; watch public vs admin path conflicts later |

### 5.3 Unsafe assumptions (do not guess)

| Topic | Rule |
|-------|------|
| Commission amounts / timing | Use README §12 exactly; implement only in Milestone 8 |
| Stripe “paid” status | Never set `business.status=active` without webhook confirmation |
| Twilio webhook security | Validate signatures in production; do not skip in prod |
| AI behavior | Structured extraction only; no pricing/scheduling promises |
| Partner MLM | Only direct override $10/mo per README; no downline logic |
| Auth strategy | Confirm session cookie vs JWT with team before implementing |
| `business_users` M1 scope | Explicitly choose admin-only vs multi-user in M1 planning |

### 5.4 Areas where implementers should read spec, not invent

- Full data model (§7): many tables beyond current scaffold
- Commission lifecycle: pending → 30-day hold → approved → manual payout
- Webhook idempotency: `stripe_event_id` uniqueness
- Role matrix: admin / business_user / partner / support

---

## 6. Current failures

Commands run from `/srv/projects/leadcareai` on 2026-05-27.

### `python -m compileall app`

```
Exit code: 0
```

All 43 empty `.py` files compile. **No syntax errors** (expected for empty modules).

### `pytest -q`

```
no tests ran in 0.05s
Exit code: 5
```

| Item | Detail |
|------|--------|
| **Cause** | `tests/test_health.py` and `tests/conftest.py` are empty (0 bytes). Pytest exit code **5** = no tests collected. |
| **Not a logic failure** | No failing assertions; test suite not yet written. |
| **Fix (Milestone 1)** | Implement `test_health.py` with `TestClient(app)` and configure `pytest.ini` (`testpaths = tests`). |

### `uvicorn app.main:app` (not run in audit)

Expected failure if attempted: `AttributeError: module 'app.main' has no attribute 'app'`.

---

## 7. Reference: env variables ready for later milestones

`.env.example` already defines keys for M6+ integrations. **Do not wire Stripe/Twilio/OpenAI in Milestone 1** except optional no-op placeholders in `Settings`.

| Group | Keys |
|-------|------|
| App | `APP_NAME`, `APP_ENV`, `APP_DEBUG`, `APP_BASE_URL`, `SECRET_KEY` |
| DB | `DATABASE_URL` |
| Redis | `REDIS_URL` |
| Auth | `ADMIN_EMAIL`, `ADMIN_PASSWORD` |
| Stripe | `STRIPE_*` (M6) |
| Twilio | `TWILIO_*` (M3–4) |
| AI | `OPENAI_*` (M5) |
| Email | `SMTP_*`, `DEFAULT_SUPPORT_EMAIL` |

---

## 8. Audit summary

| Metric | Value |
|--------|-------|
| Total project files (excl. audit) | 67 |
| Python modules with code | 0 |
| Routers with routes | 0 |
| ORM models defined | 0 |
| HTML templates | 0 |
| Alembic migrations | 0 |
| Foundation checklist | 0 / 11 |
| Git repo | No |

**Verdict:** Repository layout matches the high-level README1 scaffold. The project is **ready to begin Milestone 1 implementation** but is **not runnable** today.

**Recommended next step:** Execute **Milestone 1 Phase 1A** — fill `requirements.txt`, create `.venv`, implement `config.py` + `database.py` + minimal `main.py` with `/health`, and make `pytest` collect at least one passing test.
