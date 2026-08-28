# Build Status

Snapshot of what exists in the repository, how it was verified, and what is left.

## Verification method (important)

Docker Desktop would not start on the dev machine during this session, so **nothing has been run against a live Postgres/Redis locally**. Everything below was verified statically.

**A CI pipeline is written** (`.github/workflows/ci.yml`) to close that gap. GitHub Actions supplies Postgres (pgvector) and Redis as service containers, so on push it is configured to apply migrations, verify they roll back and re-apply, run the seed script, execute the full test suite including the database-backed files, and assert `/health` reports both dependencies up — all with `PROVIDER_MODE=mock`, needing no API keys or spend.

### What has and has not actually run

| CI step | Written | Executed |
|---|---|---|
| Secret scan | yes | **yes** — `make scan`, clean across 231 files |
| Backend lint + format check | yes | no (`ruff` not installed locally) |
| Migrations forward → down → forward | yes | no (needs Postgres) |
| Seed script | yes | no (needs Postgres) |
| Test suite incl. DB-backed files | yes | no (`pytest` not installed) |
| Live uvicorn + `/health` assertion | yes | no (deps not installed) |
| Frontend types, lint, test, build | yes | **yes** — all four green locally |

The workflow file itself has only had a structural YAML check. **Its steps have never executed**, so any could fail on first run. Treat the pipeline as unverified configuration until a run goes green.

Also note: **the repository currently has zero commits.** Everything is untracked working-tree state, so CI cannot trigger and there is no version-control recovery point.

Static verification performed locally:

| Check | Command | Result |
|-------|---------|--------|
| Python syntax/imports, whole app + tests | `python -m compileall app tests` | passes |
| TypeScript types, whole frontend | `tsc --noEmit` | passes, 0 errors |
| Prompt builder logic (incl. injection escaping) | standalone stdlib run | 17/17 checks pass |
| Video prompt compiler | standalone stdlib run | 24/24 checks pass |
| FFmpeg command building + path confinement | standalone stdlib run | 22/22 checks pass |
| Webhook signature crypto (Stripe + Cozzipay) | standalone stdlib run | 13/13 checks pass |
| Blueprint prompt + embedding text (incl. legal guardrails) | standalone stdlib run | 25/25 checks pass |
| Image prompt + character sheet builder | standalone stdlib run | 22/22 checks pass |
| **TOTP against RFC 6238 reference vectors** | standalone stdlib run | 33/33 checks pass |
| Content moderation + PII scrubbing | standalone stdlib run | 60/60 checks pass |
| Frontend production build + route table | `next build` | passes, 26 routes |
| Frontend types | `npm run typecheck` | passes, 0 errors |
| Frontend lint (ESLint 9 flat config) | `npm run lint` | passes, 0 problems |
| Frontend unit tests | `npm test` | 24/24 pass (2 files) |
| Pricing page render mode | `next build` route table | confirmed dynamic (not statically baked) |
| Proxy (route guard) registered | `next build` route table | confirmed present after the Next 16 rename |
| Production dependency advisories | `npm audit --omit=dev` | **0 vulnerabilities** |
| CI workflow structure | stdlib structural check | valid, 3 jobs |
| No mock references outside the factory | repo-wide grep | confirmed zero |

**Not yet verified:** live migrations, live endpoint behaviour, database-backed tests, real provider calls. These need `make dev` once Docker runs.

---

## CI & provider modes

- **CI pipeline** with three jobs: secret scan (gitleaks over full history), backend (lint, format check, migrations, reversibility check, seed, tests, live `/health` assertion against a real server), and frontend (types, lint, production build).
- **Mock provider mode** (`PROVIDER_MODE=mock`) runs the entire pipeline with no API keys and no cost. See `docss/PROVIDER_MODES.md` for the full contract.
- The design constraint, held deliberately: **mocks are peer implementations of the adapter interfaces, never a mode the business logic branches on.** Selection happens in exactly one file (`app/adapters/factory.py`), and a repo-wide grep confirms zero mock references in any service, route, or worker. Deleting the mock package would require no business-logic edits.
- This required a refactor that improved the design independently: routes previously instantiated `GeminiAdapter()`, `S3StorageAdapter()` and friends directly. All eight call sites now resolve providers through the factory, which also unified "provider not configured" into a single `ProviderUnavailableError` instead of per-provider exception handling.
- Mocks reproduce the awkward parts of reality rather than smoothing them over: the video mock stages **queued → running → completed** across polls so the polling loop and progress UI are genuinely exercised; the image mock writes a real decodable PNG; the video mock renders a real MP4 via ffmpeg so stitching operates on genuine media; failures raise the same exception classes as live adapters so retry and refund paths run.
- Mock mode is **refused at startup in production**, and `live` is the default so nobody gets fakes by forgetting a variable.

## Backend (`apps/api`)

### Foundation
- FastAPI app with fail-fast config validation, CORS, security headers (incl. CSP), request-size ceiling, and an identity middleware used only for rate-limit bucketing.
- Async SQLAlchemy + Alembic. Two migrations: `0001_initial` (15 tables, pgvector + pgcrypto extensions), `0002_payments`.
- Celery app with `video_tasks` registered.
- Idempotent seed script: admin user, credit ratio, 6 action prices, 3 plans, 3 packages, 3 feature flags, 7 video models.

### Auth & accounts
- Register/login/refresh/logout/me. bcrypt (cost 12), password strength rules.
- JWT access tokens + refresh tokens with **family tracking and reuse detection** (a replayed refresh token revokes the whole family).
- httpOnly, SameSite=strict cookies; Bearer header also accepted for future mobile clients.
- Object-level authorization dependency; `get_current_admin` returns 404 (not 403) so admin routes are not discoverable.
- Rate limits on auth (5/min), generation (10/min), uploads (20/min), checkout (10/5min).

### Projects & brief
- CRUD with ownership enforced on every read and write; unknown/foreign ids return 404.
- Brief stored as JSONB with shallow-merge auto-save (nothing lost on refresh).
- Soft delete with 30-day recovery window.
- Secure asset upload: magic-byte type detection, size cap, full image re-encode (strips EXIF and appended payloads), randomised storage keys, private bucket + signed URLs.

### Swipe file / ad intelligence (Phase 2)
- Reference-ad upload with magic-byte container validation (MP4/MOV/WebM), 200 MB cap.
- Multimodal deconstruction via Gemini's Files API (resumable upload, ACTIVE-state polling, `gemini-2.5-pro` for analysis).
- Analysis prompt is written to extract **transferable structure only**: no transcripts, no brand or mascot names, no recreatable descriptions of identifiable people. Enforced and tested.
- Output strictly schema-validated into beats, triggers, hook style, pacing, palette, camera techniques, plus "why it works" and "reusable pattern".
- Embedding generated from structural fields only, so similarity matches on strategy rather than any brand's wording. Embedding failure degrades to filter-only retrieval instead of blocking ingestion.
- Curator workflow: pending by default → edit metadata → score → approve. **Only approved blueprints are ever retrieved at generation time.**
- Library coverage stats (totals, by category, by industry) so gaps are visible.
- Admin UI: upload with hints, filterable library list, full review panel with beat timeline, corrections, approve/unapprove, vector rebuild, delete.

### Asset pre-generation (Phase 3)
- `ImageAdapter` interface + fal.ai adapter (Flux Pro; automatically switches to the Redux image-to-image endpoint when references are supplied).
- Image prompts translate brand hex codes into natural language, inject voice-tone as mood, and suppress text/logo rendering (models render text badly, and a hallucinated logo is worse than none).
- Asset planning reads `image_gen_needed` from the script and is **idempotent** — re-running never duplicates rows, so a partial run resumes cleanly.
- **Character consistency**: one shared character sheet (multiple angles, neutral background, consistent lighting) is generated per project and reused as a reference across scenes. A user-uploaded character image is always preferred over a synthetic one.
- Per-image credit charging with **per-image refunds** — if 2 of 8 images fail, only those 2 are refunded and the rest stand.
- Review screen: per-scene grouping, approve/reject, regenerate a single asset, or upload your own replacement (uploads are never charged). Approving attaches assets as video references and advances the project.

### Script & direction engine
- Gemini adapter behind an `LLMAdapter` interface (httpx, no vendor SDK lock-in).
- RAG retrieval over approved ad blueprints with structured filters, pgvector similarity, and graceful relaxation when filters match nothing.
- **Prompt-injection defence:** fixed system instruction, brief passed as clearly-delimited JSON data in the user turn, never interpolated.
- Model output is strictly schema-validated before use; malformed output is rejected, not trusted.
- Credits charged only after a successful, validated generation.

### Video model aggregator
- `VideoModelAdapter` interface + fal.ai adapter covering Veo, Kling, Seedance, MiniMax, Wan (model chosen by registry `model_id`).
- Provider registry: new model = one DB row; new provider = one adapter class.
- Catalogue endpoint with capability filtering, a "recommended" default, and per-model cost preview computed from admin pricing.

### Generation pipeline
- Per-scene submission and state tracking so a partially generated project resumes without re-charging finished scenes.
- Retries with attempt limits; **automatic per-scene credit refund** on permanent failure.
- Per-scene re-roll charging only that scene.
- Concurrency cap of 3 simultaneous generating projects per user (contains provider spend).
- Background Celery tasks poll progress and trigger stitching; the API never blocks.

### Stitching & export
- FFmpeg normalisation (fps, dimensions, pixel format, audio) then concat — **argument arrays, never shell strings**; inputs confined to a sandboxed temp dir with traversal rejection.
- Exports: director's treatment (Markdown), shot list (CSV), raw prompts (TXT), final MP4 via short-lived signed URL, individual scene clips.

### Credits & payments
- Append-only ledger; every balance change writes a transaction row with `balance_after`.
- Deductions use `SELECT ... FOR UPDATE` so the check and debit are atomic — no double-spend race.
- **All pricing is database-driven**: credit-to-USD ratio, per-action base credits, per-model multipliers, plans, packages. No hardcoded prices anywhere.
- Three gateways: Stripe, PayPal, Cozzipay (HMAC-SHA512 request signing, nonce, timestamp, idempotency key per their docs).
- Webhook security: signatures verified over the **raw body** with constant-time comparison; Stripe timestamp tolerance blocks replay; PayPal verified via its remote endpoint (the sync path deliberately refuses to assert trust).
- **Fulfilment reads credits from the pre-created `credit_purchases` row, never from the webhook body**, and `processed_webhooks` makes repeat deliveries a no-op.

### Admin
- Credit-to-USD ratio, per-action pricing, model registry CRUD (with provider-adapter validation), plans, packages.
- **Live margin analysis**: provider cost vs. user price per scene, flagging unprofitable configurations.
- User list, activate/suspend (cannot suspend self), manual credit grants recorded in the ledger with admin attribution.
- Feature flag toggles.

---

## Frontend polish (Tasks 41-43)

- **Marketing site**: landing page with how-it-works and capability sections, plus a shared nav/footer layout. Copy is written for people who make ads, and deliberately says the platform is useful *without* AI video for teams who shoot with real crews.
- **Pricing page is live off the database**: plans and packages are fetched server-side (so the page is indexable) and rendered per request with `force-dynamic` + `no-store`. This was a deliberate call — prices are admin-editable at runtime and the API is not necessarily reachable at build time, so static generation would bake in stale or unavailable pricing. Correctness beats a few milliseconds on a low-traffic page. If the API is down the page degrades to a fallback message rather than erroring.
- **Guided first project**: the dashboard now shows a getting-started checklist (profile, credits, first ad) that disappears once complete, a "pick up where you left off" list of in-progress projects, and a "what you will need" primer for first-time users.
- **Field hints throughout the brief wizard**: accessible `?` buttons (real buttons with `aria-describedby`, not hover-only tooltips, so they work by keyboard and screen reader). The hints explain *why* a field matters — e.g. that quoting real customer complaints produces far better hooks than generic positioning.
- **Responsive navigation**: the fixed sidebar became a `DashboardNav` component that collapses to a slide-over drawer below `lg`, closes on navigation (including via the back button), and marks the active route with `aria-current`. Shared by both the dashboard and admin shells.

## Framework upgrade: Next 14 → 16 (security-driven)

`npm audit` reported **21 advisories** against `next@14.2.35`, several high severity. Next.js patches security only in the Active and Maintenance LTS lines (16.x and 15.x); **nothing is backported to 14.x**, so there was no patch path without a major upgrade. Two of the advisories bore directly on code in this repo: middleware/proxy redirect cache poisoning, and request smuggling in rewrites (the app proxies `/api/backend/*` to FastAPI).

Now on **Next 16.3.3 (Active LTS) + React 19.2.8**, with `npm audit --omit=dev` reporting **0 production vulnerabilities**.

The upgrade surface turned out to be small because of choices already in place: every dynamic route reads its id through the client-side `useParams()` hook rather than the server-side `params` prop, and there are no `cookies()` or `headers()` calls — those are the two breaking changes that make most Next 15 migrations painful.

What did need doing:

- **`middleware.ts` → `proxy.ts`, and the exported `middleware()` → `proxy()`.** Next 16 renamed the convention and now runs it on the Node runtime. This fails *silently*: the old filename is simply not picked up, so the route guard would have stopped running with no error and no warning. The build route table is the proof it is wired — it lists `Proxy (Middleware)`. The 8 guard tests written just before the upgrade are what made this verifiable rather than a matter of hope.
- **`next lint` was removed entirely, and `next build` no longer lints.** The `lint` script now invokes `eslint` directly, so linting still happens in CI — otherwise the upgrade would have quietly disabled it.
- **ESLint 8 → 9 with flat config.** `eslint-config-next@16` requires ESLint ≥9, which does not read `.eslintrc.*`. Worth noting for anyone following a migration guide: `eslint-config-next@16` ships a *native* flat config array from `eslint-config-next/core-web-vitals` and must be spread directly. Wrapping it in `FlatCompat` (the usual advice) throws `Converting circular structure to JSON`, because the plugin objects are self-referential.
- **CI Node bumped 20 → 22** to satisfy the new lint toolchain's engine constraint.
- **Two real bugs surfaced by React 19's stricter hooks rules**, both fixed rather than suppressed:
  - `DashboardNav` reset its drawer state via `setState` inside an effect, which committed the open drawer and then re-rendered — a visible flash of the drawer over the new page. Now adjusted during render, React's documented pattern, which also fixes back-button navigation.
  - `MfaSetup` cleared its QR code in an effect, leaving a window in which a QR image generated from a *previous* provisioning URI was on screen. The QR is now stored alongside the URI it encodes and discarded by derivation if they diverge, so a code can never be displayed against the wrong secret. That one matters: scanning a stale QR would enrol the wrong TOTP secret.

Remaining audit findings are **dev-only** (the vitest → vite → esbuild chain) and concern the vite dev server, which this project never runs.

## Frontend (`apps/web`)

Next.js 16 App Router (Turbopack), React 19, TypeScript, Tailwind. Route groups: `(marketing)`, `(auth)`, `(dashboard)`, `(admin)`.

- Login and register forms (react-hook-form + zod), auto-login after signup.
- Three-step onboarding wizard with progressive server-side save.
- Five-step brief wizard with debounced auto-save and a live save indicator.
- Project folder list with status badges and credits spent; status-based routing so users resume at the right step.
- Script storyboard: expandable scene cards showing dialogue, visuals, camera, lighting, grading, audio, brand elements, the compiled prompt, and required assets.
- Model selector cards with quality tier, capabilities, and per-model credit/USD cost.
- Generation timeline with per-scene blocks, auto-polling that stops when work settles, progress bar, failure notice explaining refunds, per-scene re-roll, and inline video preview.
- Export page for MP4, treatment, shot list, prompts, and individual clips.
- Billing page: balance, plans, packages, transaction history.
- Dashboard topbar with live credit balance and sign-out.

### Resilience & error handling
- **Error boundaries** at the root and per route group, so a failure inside the dashboard or admin area keeps the surrounding navigation usable instead of blanking the page. The root boundary shows a generic message and surfaces only Next's `digest` — exception text can carry query fragments and provider responses, which do not belong on a user's screen.
- `not-found.tsx` for unmatched routes; skeleton loading states for the dashboard and admin shells.
- **Route guard** (`proxy.ts`) redirects anonymous visitors away from `/dashboard`, `/admin`, and `/onboarding`, preserving the intended destination in `?next=`. Signed-in users are bounced off `/login` and `/register`.
- This is a **UX guard, not a security boundary**, and the file says so: it checks only for cookie presence and never verifies the JWT, because the signing secret belongs server-side and the backend re-verifies every request and re-checks ownership. Documented in place so it is not later mistaken for access control.
- The `?next=` value passes through `safeRedirect()`, which rejects absolute URLs, protocol-relative URLs (`//host`), backslash variants (`/\host`), non-HTTP schemes, and control-character smuggling. Without it, `?next=` is an open-redirect and a credible phishing vector. Covered by 16 tests.

### Password reset (completed)
- The `PasswordResetRequest` / `PasswordResetConfirm` schemas previously existed with **no endpoints using them** — dead code that looked like a feature. Now wired end to end.
- The request endpoint **always returns the same response** whether or not the address exists, so it cannot be used to enumerate accounts. Rate limited to 3 per hour.
- Tokens are single-use, random, stored **SHA-256 hashed** in Redis with a 30-minute TTL, and deleted on use.
- **Completing a reset revokes every existing session.** The first implementation of this scanned Redis comparing refresh-family values against the user id — but those keys store the token `jti`, not the user id, so it would never have matched. It would have looked like a working security control while silently doing nothing. Replaced with a real per-user family index (`refresh:user:{id}`) maintained by `auth_service`.
- Frontend: `/forgot-password` and `/reset-password`, with a "Forgot your password?" link on login. The reset form mirrors the backend password policy exactly, so a password accepted at signup is never rejected at reset.

---

## Test suite

Written and compiling; **execution pending Docker** for the DB-backed ones.

| File | Covers | Needs DB |
|------|--------|----------|
| `test_prompt_builder.py` | prompt assembly, injection escaping, JSON extraction | no |
| `test_video_prompt_compiler.py` | hex→language colour mapping, brand injection, truncation | no |
| `test_ffmpeg.py` | argument-list construction, shell-metachar safety, path confinement | no |
| `test_webhook_security.py` | signature validation, tampering, replay, rotation, wrong secret | no |
| `test_script_schema.py` | rejection of malformed/oversized model output | no |
| `test_tokens.py` | JWT round-trip, type confusion, tampering, rotation, password rules | no |
| `test_uploads.py` | format allowlist, disguised executables, SVG, EXIF stripping, polyglots | no |
| `test_credit_service.py` | pricing from DB, atomic deduction, overspend, refunds, ledger integrity | yes |
| `test_project_ownership.py` | IDOR isolation, soft delete, brief merge | yes |

### Frontend (Vitest) — these **do** run locally

| File | Covers | Result |
|------|--------|--------|
| `lib/safe-redirect.test.ts` | open-redirect guard: 12 real bypass techniques (protocol-relative, backslash, scheme, control-character smuggling) | 16/16 pass |
| `proxy.test.ts` | route guard: anonymous redirect, `next` round-trip, refresh-only cookie, signed-in bounce off `/login`, lookalike prefixes, reset pages reachable while signed in | 8/8 pass |

---

## What remains

**Blocked on Docker**
- Run migrations, hit `/health`, seed, and execute the DB-backed tests (spec Task 5).
- End-to-end smoke test of the full flow.

**Needs API keys**
- `GEMINI_API_KEY` for script generation; `FAL_KEY` for video and image models.
- Gateway keys for live payments (all three are implemented and can run in test mode).
- S3/R2 credentials for asset and video storage.

**Not yet built**
- Marketing site content and the mobile app (Phase 8).

### MFA, audit log & monitoring (Tasks 36, 39)
- **TOTP implemented in-house with zero dependencies** and verified against the six RFC 6238 reference vectors. A ±1 window drift tolerance stops clock skew locking users out; comparison is constant-time.
- **MFA is mandatory for admins**: an admin without a second factor cannot obtain a session at all (403 with an enrolment instruction), and admins are blocked from disabling it.
- Recovery codes are stored **hashed** and consumed on use, so a database dump yields nothing usable.
- **Append-only audit log** on every sensitive admin action (pricing ratio, action pricing, model create/update, user suspension, credit grants, flag toggles, MFA changes, admin logins) capturing actor, before/after values, IP, and user agent. Writes never block the action they record.
- `security_events` table for anomaly signals, with threshold-based alerting (failed logins, webhook signature failures, unusual spend).
- **Webhook signature failures are recorded as critical events** — a forged webhook is either an attack or a misconfiguration, and both need to be visible.
- Sentry integration is **optional and degrades gracefully**: no DSN or no SDK means structured logging, never a broken request. PII scrubbing runs before anything leaves the process, extracted into `utils/scrubbing.py` so it's reusable and independently testable.
- Global exception handler reports the failure but returns a generic message, so internals never leak.
- Admin security screen: active alerts, recent security events, and the audit trail.

### MFA enrolment UI & product analytics
- **MFA setup screen** at `/dashboard/settings`: begin enrolment, scan a QR code (rendered client-side from the `otpauth://` URI), or copy the secret for manual entry, confirm with a live code, then a one-time display of recovery codes with copy-to-clipboard. Falls back to manual key entry if QR rendering fails, so enrolment is never blocked.
- **Login handles both MFA paths**: a correct password with MFA enabled moves to a code step (recovery codes accepted); an admin without a second factor gets a clear enrolment-required screen rather than a bare error.
- **PostHog analytics wired** through their HTTP capture API rather than the SDK, for one fewer dependency and explicit failure behaviour. Events are fire-and-forget on a detached task, so a slow analytics endpoint can never slow a user request; with no API key every call is a no-op.
- Analytics carries **no PII**: `distinct_id` is the user UUID, traits are segments only (country, industry, role, use case, company size), and every payload passes through the same scrubber used for error reporting.
- Funnel coverage: registration, onboarding, script generated, assets generated, video started, scene re-rolled, checkout started, credits purchased. Plus quality signals: generation failures, content refusals, and insufficient-credit events (useful for spotting pricing friction).

### Content moderation & legal guardrails (Task 40)
- Two-stage screening: the **brief is checked before any provider is paid**, and the **generated script is checked before it is persisted or charged**.
- Blocks requests for the likeness of real, identifiable people (deepfake, face swap, impersonation, "looks exactly like" patterns) — detected by *intent pattern* rather than an unmaintainable celebrity name list. The refusal message points users to the legitimate path: original characters, or their own uploads with consent.
- Blocks sexual content, graphic violence, hate speech, illegal activity, self-harm, and anything touching minor safety.
- **Flags rather than blocks** lawful-but-risky advertising claims (health, financial), because refusing legitimate advertising copy would be wrong; the advertiser is told to check it against local rules.
- Terms-of-service versioning and acceptance recorded per user.

### Admin screens (all built)
Overview (with health warnings for zero approved blueprints and below-cost pricing), Pricing (credit value, per-action costs, live margin table), Video Models (register, reprice, enable/disable), Swipe File, Users (suspend, manual credits), Feature Flags.

**Known gaps worth flagging**
- Scene thumbnails are not yet generated per scene (only for the final video), so timeline blocks show status text rather than images.
- Subscription lifecycle webhooks (pause/cancel/past_due) are recognised but do not yet adjust access; only credit grants are wired.
- `poll_project` retries on a fixed interval rather than exponential backoff.
