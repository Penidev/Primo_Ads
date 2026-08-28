# Primo — AI Ad Production Platform

Primo is an end-to-end AI-powered commercial production studio. Business users provide a brand brief; the platform generates a strategic ad concept, a scene-by-scene script with directorial guidance, brand-consistent reference assets, and (optionally) a finished stitched video via a multi-model video-generation aggregator. Usage is billed through a prepaid credit system (Stripe, PayPal, Cozzipay).

## Monorepo Layout

```
primo/
├── apps/
│   ├── api/          # FastAPI backend (Python)
│   ├── web/          # Next.js frontend (TypeScript)
│   └── mobile/       # React Native (Expo) — added in Phase 8
├── packages/         # Shared code (types, api-client, validation)
├── infrastructure/   # Docker Compose, scripts, deploy config
└── docs/             # Architecture, security, deployment docs
```

Detailed design lives in `docss/`:
- `ARCHITECTURE.md` — module architecture, tech stack, phased build plan
- `PROJECT_STRUCTURE.md` — folder layout, database schema, dependencies
- `SECURITY.md` — security hardening standard (release gate)

The formal spec (requirements, design, tasks) lives in `.kiro/specs/primo-platform/`.

## Tech Stack

- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Shadcn/UI
- **Backend**: FastAPI, SQLAlchemy (async), Pydantic
- **Jobs**: Celery + Redis
- **Database**: PostgreSQL 16 + pgvector
- **Storage**: S3 / Cloudflare R2
- **AI**: Gemini/Claude (script), fal.ai (video + image models)
- **Payments**: Stripe, PayPal, Cozzipay

## Local Development

Prerequisites: Docker, Docker Compose.

```bash
# Copy environment template and fill in values
cp apps/api/.env.example apps/api/.env

# Start the full stack (api, worker, web, postgres, redis)
make dev

# Run database migrations
make migrate

# Seed admin user, model registry, and default pricing
make seed
```

- Web app: http://localhost:3000
- API: http://localhost:8000
- API docs (OpenAPI): http://localhost:8000/docs

## Common Commands

See the `Makefile` for the full list (`make dev`, `make migrate`, `make seed`, `make test-api`, `make lint-api`, etc.).

## Status

Currently in **Phase 0 — Foundations**. See `.kiro/specs/primo-platform/tasks.md` for the full implementation plan.
