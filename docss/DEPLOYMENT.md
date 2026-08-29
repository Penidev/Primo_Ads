# Deployment

Frontend on Vercel, Postgres on Supabase, API and Celery worker on a container
host. Redis alongside the backend.

## Why this split

The frontend is a Next.js app and Vercel is its native home. The backend is not a
candidate for serverless, for two reasons that no timeout increase fixes:

- **Celery needs a long-lived process** consuming a queue. Scheduled function
  invocations are not the same thing, and the entire video pipeline depends on
  that worker running.
- **Stitching needs ffmpeg**, real CPU, and scratch disk. It downloads every
  scene clip, re-encodes each one, then concatenates.

So the backend runs as a container. `infrastructure/render.yaml` is written for
Render, but nothing about the image is Render-specific — the same Dockerfile and
the same environment variables run on Railway, Fly.io, or a VPS.

## The request path, and why it matters

```
browser ──▶ Vercel (Next.js)
              │  /api/backend/*  rewrite, server-side
              ▼
            API container ──▶ Supabase Postgres
                         └──▶ Redis
```

**The browser never addresses the API host.** Every call goes through the
Next.js rewrite, which means:

- Auth cookies are **first-party**. `SameSite=strict` works. Had the frontend
  called the API domain directly, `vercel.app` and the API host would be
  different sites and strict cookies would never be sent — the usual fix being
  to weaken them to `SameSite=none`, which is worth avoiding.
- The API hostname is not in the client bundle, so it is not a target.
- `connect-src 'self'` in the CSP is sufficient and honest.

Do not "optimise" this by pointing the frontend at the API domain. It would
break auth and widen the CSP in the same change.

---

## 1. Supabase

Create a project, then **Database → Extensions** and enable `vector` and
`pgcrypto`. The first migration also issues `CREATE EXTENSION IF NOT EXISTS`, so
this is belt-and-braces, but doing it by hand first surfaces a permissions
problem before it surfaces as a failed deploy.

Take **two** connection strings from **Connect**. They do different jobs:

| Use | Port | Mode | Why |
|---|---|---|---|
| `DATABASE_URL` | 6543 | transaction pooler | short-lived connections, which is what an API wants and what keeps you inside Supabase's connection limit |
| `MIGRATION_DATABASE_URL` | 5432 | session | Alembic needs session-level behaviour the transaction pooler does not provide, and `CREATE EXTENSION` wants a direct connection |

Then edit both strings. The dashboard gives you
`postgresql://...?sslmode=require`, and pasted verbatim that fails twice:

1. no `+asyncpg`, so SQLAlchemy loads a **sync** driver
2. `sslmode` is libpq's keyword — **asyncpg rejects it**

Config validation refuses both with the reason attached rather than letting them
surface mid-connection. What you want:

```
postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

TLS comes from `DB_REQUIRE_SSL`, which is forced on whenever
`ENVIRONMENT=production` and is not overridable.

Also set `DB_BEHIND_TRANSACTION_POOLER=true`. Without it, asyncpg prepares
statements that the pooler's next backend has never seen, which fails as
`prepared statement ... does not exist` **under load rather than immediately** —
so it passes a smoke test and breaks in front of users.

---

## 2. Backend

Either point Render at `infrastructure/render.yaml`, or run the same image
anywhere:

```bash
docker build --target production -t primo-api ./apps/api

# API
docker run -p 8000:8000 --env-file prod.env primo-api

# Worker: same image, different command
docker run --env-file prod.env primo-api \
  celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
```

Migrations are a **release step**, not a startup step, so a deploy either has its
schema or does not start:

```bash
alembic upgrade head
```

Generate the signing secret properly. It must not be reused from staging:

```bash
openssl rand -base64 48
```

### Required environment

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `PROVIDER_MODE` | `live` — mock is refused at startup in production |
| `DATABASE_URL` | Supabase pooler, port 6543, `+asyncpg`, no `sslmode` |
| `MIGRATION_DATABASE_URL` | Supabase session mode, port 5432 |
| `DB_BEHIND_TRANSACTION_POOLER` | `true` |
| `DB_REQUIRE_SSL` | `true` |
| `REDIS_URL` | private network only |
| `JWT_SECRET` | fresh 48-byte random |
| `FRONTEND_URL` | `https://<vercel-domain>` — **this sets the CORS origin** |
| `TRUSTED_PROXY_COUNT` | see below |
| `GEMINI_API_KEY` | script generation |
| `FAL_KEY` | image **and** video generation |

### TRUSTED_PROXY_COUNT

This one is worth understanding rather than copying.

X-Forwarded-For is built by *appending*, so its **left-hand entries are supplied
by the caller**. Rate limiting therefore locates the client by counting from the
right, skipping the proxies you actually operate:

```
caller sends nothing    ->  "C, P1"           depth 2 -> C
caller forges an entry  ->  "9.9.9.9, C, P1"  depth 2 -> C
```

`0` ignores the header entirely and uses the socket peer. **Too high is the
dangerous direction**: it lets a caller pick their own rate-limit bucket and
walk past the limits on login, registration, and password reset — the endpoints
with no user id to bucket by. Too low only groups more callers together.

Vercel rewrite → container host balancer is typically `2`. Verify against a real
request before trusting it.

---

## 3. Vercel

Import the repository and set **Root Directory** to `apps/web`. Everything else
comes from `apps/web/vercel.json`, which runs typecheck, lint, and tests before
the build so a broken commit fails at build time rather than at runtime.

One environment variable:

| Variable | Value |
|---|---|
| `API_INTERNAL_URL` | `https://<your-api-host>` |

Server-side only. There is deliberately **no `NEXT_PUBLIC_` equivalent** —
anything with that prefix is compiled into the client bundle. The app currently
has zero `NEXT_PUBLIC_` variables, and that is worth keeping.

Set `FRONTEND_URL` on the backend to the resulting Vercel domain, or CORS will
reject the browser.

---

## Security posture

What is in place, and where it is enforced:

| Control | Where |
|---|---|
| Nonce-based CSP with `strict-dynamic`, no `unsafe-inline` for script | `apps/web/lib/csp.ts`, applied in `proxy.ts` |
| HSTS, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP, no `X-Powered-By` | `apps/web/next.config.mjs` |
| Auth cookies `httpOnly` + `Secure` + `SameSite=strict` | `apps/api/app/api/v1/auth.py` |
| Rate-limit identity resistant to XFF forgery | `apps/api/app/utils/rate_limit.py` |
| TLS to the database, non-overridable in production | `apps/api/app/config.py` |
| Mock providers refused in production | `apps/api/app/config.py` |
| Container runs as uid 10001, cannot write its own code | `apps/api/Dockerfile` |
| No compilers, pytest, or ruff in the production image | `apps/api/Dockerfile`, `production` target |
| Redis not publicly reachable | `infrastructure/render.yaml`, `ipAllowList: []` |
| Secrets never committed; `sync: false` throughout | `infrastructure/render.yaml` |

A per-request CSP nonce means HTML cannot be statically prerendered, so routes
carrying it render on demand. That is a real cost, accepted deliberately: the
alternative is `script-src 'unsafe-inline'`, which also permits any injected
script and leaves CSP doing close to nothing about XSS.

### Not yet done

Stated plainly, because a green deploy invites more confidence than is earned:

- **No provider has been called for real.** Everything verified so far runs on
  mocks. The adapter interfaces are exercised; the live HTTP contracts are not.
- **No load testing.** Spec task 44 is open.
- **No S3 lifecycle rules.** Raw scene clips accumulate and nothing expires them.
  Task 30.
- **No custom domain or WAF.** Both hosts terminate TLS, but there is no rate
  limiting or bot filtering ahead of the app.
- **Backups are whatever Supabase's plan includes.** No tested restore.

### First real ad will cost money

Video is billed per second of output. Do the first live run at **two scenes on
the lowest-multiplier model**, not a full ad. The admin margin table exists to
show provider cost against user price before anything goes live.
