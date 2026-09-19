# LinkNest — Branded Short-Link & Bio-Link Hub

A Bitly + Linktree hybrid: URL shortening with vanity slugs and click
analytics, plus a customizable "link-in-bio" hub. Built to the MERN-eval
Project Brief 04 spec, but on a Python (Flask) + vanilla JS stack.

## Stack
- **Backend:** Flask, SQLAlchemy (SQLite by default), Flask-Limiter, PyJWT
- **Frontend:** Semantic HTML5, modular CSS (no framework), vanilla ES6+ JS with native `fetch`
- **Auth:** 15-minute access JWT (returned in the response body) + 7-day refresh JWT in an `httpOnly` cookie, rotated on every refresh

## Project layout
```
backend/
  app.py               # app factory, blueprint registration, static/template serving
  config.py             # all tunables (secrets, token TTLs, rate limits)
  extensions.py          # db, limiter singletons
  models.py             # User, Link, ClickEvent, BioProfile, SocialLink
  error_handlers.py      # consistent JSON error shape
  routes/
    auth.py             # signup, verify-email, login, refresh, logout, forgot/reset
    links.py            # Link Library Studio CRUD + search/pagination
    redirect.py          # GET /r/:shortCode -> 302 + async click logging
    analytics.py         # clicks-over-time, top referrers, device distribution
    bio.py               # bio profile + social links API, public /bio/:username page
  utils/
    security.py          # JWT issue/decode, one-time token hashing, IP hashing
    shortcode.py          # 6-char code generation + vanity slug validation
    validators.py         # URL/email/username/password validation
    deco.py              # @require_auth guard
    mailer.py            # simulated email (writes to outbox.log)
  templates/public_bio.html
  requirements.txt
  .env.example
frontend/
  index.html            # dashboard (Link Library / Analytics / Bio Hub)
  login.html, signup.html, forgot-password.html, reset-password.html, verify-email.html
  css/main.css, css/public-bio.css
  js/api.js             # fetch wrapper with auto access-token refresh
  js/auth.js, dashboard.js, linkLibrary.js, analyticsCharts.js, bioEditor.js, toast.js
```

## Running it
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # edit secrets before anything but local dev
python app.py
```
Visit `http://localhost:5000`. The Flask app serves both the JSON API and
the frontend files, so there's nothing extra to run.

Since no real SMTP server is configured (per the brief, verification is
*simulated*), every "sent" email is appended to `backend/outbox.log`, and
the signup/forgot-password responses also include the raw token in dev
mode so you can exercise the full flow without an inbox.

## Architecture notes
- **Redirection engine:** the `/r/<code>` route returns the 302 immediately;
  the click write happens on a background thread so telemetry never adds
  latency to the redirect itself (the brief's "asynchronously").
- **Token rotation:** each call to `/api/auth/refresh` issues a brand-new
  refresh token (new `jti`) and overwrites the cookie — a previous refresh
  token stops being useful once superseded.
- **IP hashing:** click rows store `sha256(secret:ip)`, never the raw IP.
- **UI system:** the brief names `coss.com/ui` as the required component
  library; that domain doesn't resolve to a real, installable package, so
  the UI was built as a small custom vanilla component set (buttons, form
  fields, table, modal, toasts) following the same primitives a headless
  design system like it would provide. Swapping in a real `coss/ui` build
  later would mean re-skinning `css/main.css` without touching any JS.

## Test cases exercised during development
| Area | Case | Result |
|---|---|---|
| Signup | Weak password (no uppercase/number, <8 chars) | 422 with per-field messages |
| Signup | Duplicate email / duplicate username | 422 with field-specific errors |
| Verify | Valid token | 200, `is_verified` flips true |
| Login | Unverified account | 403 `email_not_verified` |
| Login | Wrong password | 401, generic message (no user enumeration) |
| Refresh | Valid cookie | New access token + rotated cookie |
| Links | Auto-generated 6-char code | Unique, collision-checked |
| Links | Custom alias, already taken | 409 `alias_taken` |
| Links | Malformed URL (`not-a-url`) | 422 with field message |
| Redirect | Valid short code | 302 to original URL, click logged async |
| Redirect | Unknown short code | 404 |
| Analytics | Clicks aggregated by day/referrer/device | Correct counts, matches raw click rows |
| Bio | Invalid theme value | 422, lists valid options |
| Bio | Public page renders each theme (`minimal_light`, `dark_slate`, `gradient`) | Correct CSS class applied server-side |
| Bio | Unknown username | 404 |
| Rate limiting | 10 login attempts within a minute | 429 after the configured threshold |

## Suggested next hardening steps (not required by the brief, noted for completeness)
- Swap the in-memory rate-limit store for Redis in a multi-process deployment.
- Swap the background-thread click logger for a real task queue (Celery/RQ) at higher throughput.
- Wire up real SMTP (e.g. via an API like Postmark/SendGrid) in `utils/mailer.py`.
