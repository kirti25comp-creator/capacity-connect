# CAPACITY CONNECT — Backend

A Flask + SQLAlchemy backend for a multi-tenant corporate training platform:
organizations, employees, managers, trainers, competency-based trainer
matching, training lifecycle, MCQ assessments, demo AI proctoring, feedback
& trainer quality, skill-gap analysis, certificates, notifications, and a
RBAC-scoped "CAPACITY AI" query assistant.

## Verification status

This backend has been executed end-to-end (not just written): the full
36-test suite passes, `flask --app run.py init-db` / `seed-db` run cleanly,
the server starts and serves real traffic, and `/api/health`, login,
`/api/auth/me`, department CRUD, and cross-organization IDOR protection were
all exercised over live HTTP against a real SQLite-backed instance.
Verification was performed against real Flask, Werkzeug, and SQLite — the
only substitution was a minimal, sqlite3-backed SQLAlchemy-compatible
compatibility layer used purely because this particular execution sandbox
has no package-install access; that layer is not part of this deliverable
and real `Flask-SQLAlchemy` (per requirements.txt) is what actually ships
and what you should install.

**Scope note:** this is a backend-only deliverable. No frontend/UI work is
included — the frontend team can build against the REST API described below
without touching this code.

## What's DEMO / MOCK (be upfront about this in any demo/pitch)

- **Organization verification** (`/api/auth/verify-organization/<id>`) is a
  clearly-labelled MOCK — it does **not** call a real MCA (Ministry of
  Corporate Affairs) or any government API. It just checks a
  registration_number was supplied.
- **AI proctoring** is a **simulated** event log. There is no real webcam/
  computer-vision pipeline. A (hypothetical) client-side widget would submit
  event types (`FACE_MISSING`, `MULTIPLE_FACES`, etc.) and the backend
  classifies severity → `CLEAR` or `REVIEW_REQUIRED`. It never concludes
  someone cheated — a manager always makes that call.
- **CAPACITY AI** runs in `DEMO` mode by default: keyword-based intent
  detection + real, RBAC-scoped SQL queries + template-based phrasing. No
  external LLM call is required to demo the full pipeline. If
  `ANTHROPIC_API_KEY` is set and `AI_MODE=LIVE`, the same verified_data can be
  handed to a real model purely for prose phrasing — the model is never given
  raw query/authorization power itself.
- **Feedback "lie detection"** does not exist. The feedback analyzer only
  ever classifies evidentiary strength (`SUPPORTED`, `PARTIALLY_SUPPORTED`,
  `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`, `HUMAN_REVIEW_REQUIRED`).

## Project layout

```
app/
  config.py              Flask config (env-driven)
  extensions.py          db = SQLAlchemy()
  models/                All SQLAlchemy models, one file per group of entities
  auth/
    routes.py            register/verify/activate org, login, logout, invite activation
    utils.py             JWT issue/verify, @token_required, @roles_required, org-isolation helper
  api/                   One blueprint per role/domain (admin, manager, trainer,
                          employee, courses, training, assessments, feedback,
                          competency, certificates, notifications, ai)
  services/              Business logic, deliberately split into:
                            - pure functions (matching.py, assessment_scoring.py,
                              skill_gap.py, trainer_quality.py, training_lifecycle.py,
                              ai_intent.py) — no DB dependency, directly unit-testable
                            - DB adapters (matching_db.py, trainer_quality_db.py,
                              notification_service.py, certificate_service.py,
                              proctoring_service.py, ai_service.py) — load/persist
                              ORM rows and enforce authorization scoping
  seed.py                Demo data: two organizations, to make isolation obvious
tests/                   pytest suite (see below)
run.py                   App entrypoint + `flask init-db` / `flask seed-db` CLI commands
requirements.txt
.env.example
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # edit SECRET_KEY / JWT_SECRET_KEY for anything beyond local demo use
flask --app run.py init-db
flask --app run.py seed-db         # optional but recommended — creates 2 demo orgs
python run.py
```

Server runs at `http://localhost:5000`. Health check: `GET /api/health`.

### Demo login credentials (after `seed-db`)

| Org | Role | Email | Password |
|---|---|---|---|
| Acme Corp (code `ACME`) | Admin | admin@acme.demo | Password123! |
| Acme Corp | Manager | manager@acme.demo | Password123! |
| Acme Corp | Employee | employee1@acme.demo | Password123! |
| Acme Corp | Trainer | trainer@acme.demo | Password123! |
| Globex Inc (code `GLOBEX`) | Admin | admin@globex.demo | Password123! |

Globex exists specifically so you can demo/prove that Acme's admin/manager
tokens are refused when used against Globex's data (org isolation).

## Running tests

```bash
pip install -r requirements.txt   # includes pytest
pytest
```

The suite covers: registration, login, RBAC (role checks, client-supplied
role never trusted), organization isolation & IDOR resistance, manager→own-
employee-only access, trainer matching against real DB data, course
assignment, deadline/lifecycle handling (including that expiry is not an
unlimited auto-extension), assessment scoring & pass/fail & attempt limits &
the training-completion gate, skill-gap computation, trainer quality alert
thresholds, certificate issuance authorization, notification scoping, demo
proctoring status values, and CAPACITY AI's manager-vs-admin query scoping.

The purely algorithmic modules (`services/matching.py`,
`services/assessment_scoring.py`, `services/skill_gap.py`,
`services/trainer_quality.py`, `services/training_lifecycle.py`,
`services/ai_intent.py`) have **zero** database dependency by design and were
executed and verified directly during development, independent of Flask/
SQLAlchemy being installed.

## Authentication

`POST /api/auth/login` returns a JWT. Send it as:

```
Authorization: Bearer <token>
```

The token carries `sub` (user id), `org`, and `role` claims for convenience,
but **every** request re-loads the user from the database and uses the
freshly-loaded `role`/`organization_id`/`is_active` for all authorization
decisions — the token's claims are never trusted for anything beyond looking
up which user to load. A deactivated user or a role change takes effect on
their very next request, without waiting for token expiry.

## Security model (see app/auth/utils.py + every api/*.py file)

- Every protected endpoint requires `@token_required`.
- Role checks use `@roles_required(*roles)` against the DB-loaded user.
- Organization isolation is enforced by **filtering every query** on
  `organization_id == g.current_user.organization_id` — never by trusting an
  `organization_id` supplied in the request. Cross-org resource access
  returns `404` (not `403`) where the resource genuinely doesn't exist in the
  caller's org, so existence isn't leaked.
- Manager→employee ownership is enforced the same way: every manager
  endpoint resolves "my employees" via `ManagerEmployeeAssignment` rows
  scoped to `(organization_id, manager_id=g.current_user.id)`, and rejects
  any request touching an employee id outside that set.
- Passwords are hashed with Werkzeug's `generate_password_hash` /
  `check_password_hash` (never stored in plaintext).
- File uploads (`/api/trainer/profile/intro-video`) sanitize the filename
  with `secure_filename`, prefix it with a random token, restrict the
  extension allowlist, and store per-organization to prevent path traversal
  and cross-tenant file collisions.
- All state-changing actions are recorded to `AuditLog`.
- CSRF: this API is stateless-JWT (Authorization header), not cookie-session
  based, so classic CSRF doesn't apply the way it does to cookie-authenticated
  apps — noted explicitly in `app/__init__.py` in case cookie auth is ever
  added later.
- Rate limiting: not wired up as a dependency for the hackathon build (to
  avoid adding a Redis/Flask-Limiter requirement); `Config.RATE_LIMIT_DEFAULT`
  is left as a documented hook for wiring in `Flask-Limiter` before
  production use.

## Trainer matching algorithm (transparent, DB-driven, never hardcoded)

See `app/services/matching.py`. Weights, exactly as specified:

| Criterion | Weight |
|---|---|
| Subject expertise | 25% |
| Qualification | 15% |
| Experience | 20% |
| Certification | 10% |
| Training experience | 15% |
| Availability | 10% |
| Previous performance/rating | 5% |

`GET /api/manager/training-requirements/<id>/matches` recomputes matches
live from current trainer data every call (via `matching_db.py`, which
deletes and rewrites `TrainerMatch` rows for that requirement) — there is no
cached/hardcoded ranking.

## CAPACITY AI

`POST /api/ai/ask` (MANAGER or ADMIN only) with `{"question": "..."}`.
Pipeline: `detect_intent` → role/scope check inside the query handler →
authorized SQLAlchemy query → `verified_data` → templated natural-language
`answer`. A MANAGER's queries are always filtered to their own team via
`ManagerEmployeeAssignment`; organization-wide questions (e.g. "which manager
has the best performance?") are rejected for managers and only answered for
ADMIN.

## Known limitations / next steps for the frontend team

- No payment processing (explicitly out of scope per spec).
- No real MCA verification, no real computer-vision proctoring, no real LLM
  call by default — see "What's DEMO / MOCK" above.
- Rate limiting and CSRF (for any future cookie-based flow) are documented
  hooks, not wired dependencies, in this hackathon build.
- SQLite is used for the prototype; swap `DATABASE_URL` for a real Postgres
  DSN for anything beyond the hackathon demo — the code makes no
  SQLite-specific assumptions.
