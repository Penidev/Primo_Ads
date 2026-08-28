# Design — Primo AI Ad Platform

## Overview

This design document is the technical blueprint for the Primo platform. The full, detailed design already exists in three companion documents and is treated as the authoritative source for their respective areas:

- **`docss/ARCHITECTURE.md`** — module-by-module architecture, tech stack, video model aggregator, credit/pricing system, admin controls, multi-client readiness, and the phased build plan.
- **`docss/PROJECT_STRUCTURE.md`** — monorepo layout, Docker Compose, complete database schema (SQL), dependency lists, Make commands, environment variables.
- **`docss/SECURITY.md`** — the security hardening standard and release gate.

This document summarizes the architecture, states key design decisions and their rationale, and defines the component boundaries the tasks will build against. Where detail exists in the companion docs, this document references rather than repeats it.

---

## Architecture Summary

Primo is an **API-first** system with a clean client/server split:

```
Clients (Next.js web now; React Native mobile later)
        │  REST + WebSocket/SSE
        ▼
FastAPI backend  ──►  PostgreSQL (source of truth, incl. credit ledger)
        │             Redis (cache, rate limits, queue broker, pub/sub)
        │
        ▼
Celery workers (script / asset / video / stitch / payment queues)
        │
        ▼
External services: fal.ai (video+image), Gemini/Claude (LLM),
                   Stripe / PayPal / Cozzipay (payments), S3 (storage)
```

All business logic lives in the backend. Clients render and call the API. This is what makes mobile a UI-only effort later (Requirement 15).

### Technology Stack
Defined in ARCHITECTURE.md → "Technology Stack". Summary: Next.js 14 + TypeScript + Tailwind + Shadcn (web); FastAPI + SQLAlchemy async + Pydantic (API); Celery + Redis (jobs); PostgreSQL 16 + pgvector (data + RAG); S3/R2 (storage); FFmpeg (stitching).

---

## Key Design Decisions & Rationale

1. **RAG over fine-tuning for v1.** Instant iteration, near-zero upfront cost, ~90% of fine-tuned quality. The swipe-file analysis pipeline is built regardless and feeds RAG now, fine-tuning later if quality plateaus. (ARCHITECTURE Module 3, 5.)

2. **fal.ai as the primary video/image gateway.** One SDK and billing account covers Veo, Kling, Seedance, MiniMax, Wan, and more. Direct adapters (e.g., Runway) added only when a model isn't on fal. (ARCHITECTURE Module 6.)

3. **Adapter pattern for all external providers** (video, image, LLM, payments, storage). New provider = one adapter class implementing a base interface. Registry-driven video models mean most additions are just a DB row. (ARCHITECTURE Module 6, PROJECT_STRUCTURE `adapters/`.)

4. **Pre-generate assets before video.** Feeding brand-accurate reference images into video models dramatically reduces failures and improves brand/character consistency. (ARCHITECTURE Module 4, 7.)

5. **Immutable credit ledger with locked transactions.** Credits are money; append-only ledger + `SELECT ... FOR UPDATE` prevents double-spend and gives a full audit trail. (ARCHITECTURE Module 8, SECURITY §3.)

6. **All pricing is database-driven and admin-managed.** No price, credit cost, or ratio is hardcoded. `platform_settings`, `action_pricing`, `subscription_plans`, `credit_packages`, and per-model `credit_multiplier` are all editable at runtime. (ARCHITECTURE Module 8, 9.)

7. **Feature flags everywhere.** Any module or model can be toggled globally or per tier/user without deployment. (ARCHITECTURE Module 9.)

8. **Server-side persistence, state-machine resume.** Everything is saved in the DB/S3; `projects.status` routes returning users to the exact step; partial scene progress is preserved and never re-charged. (ARCHITECTURE Module 2.)

9. **Async-first pipeline.** All heavy work runs in Celery queues with progress pushed over WebSocket/SSE; failures retry with backoff and auto-refund on permanent failure. (ARCHITECTURE Module 7, 11.)

---

## Component Boundaries

### Backend service layers (PROJECT_STRUCTURE `apps/api/app/`)
- **api/** — thin route handlers; auth + object-level authorization; delegate to services.
- **services/** — business logic (script, asset, video, stitch, credit, payment, rag, swipe_file, feature_flag).
- **adapters/** — external integrations behind base interfaces (llm, video, image, payments, storage).
- **workers/** — Celery tasks per queue.
- **models/** + **schemas/** — ORM models and Pydantic request/response contracts.
- **utils/** — security, ffmpeg command builders, prompt compiler, validators.

### Frontend (PROJECT_STRUCTURE `apps/web/`)
- Route groups: `(marketing)`, `(auth)`, `(dashboard)`, `(admin)`.
- Feature component folders: brief wizard, script/storyboard, timeline, model selector, billing, admin.
- `lib/api.ts` API client, `hooks/` for data + WebSocket, `types/` mirroring backend contracts.

### Shared packages (for web + future mobile)
- `packages/shared-types` (generated from OpenAPI), `packages/api-client`, `packages/validation` (Zod).

---

## Data Model

The complete SQL schema is in **PROJECT_STRUCTURE.md → "Database Initialization"**. Core entities:

- **users, wallets, credit_transactions, subscriptions** — accounts + money.
- **projects, scenes, scene_assets, generation_jobs** — the production pipeline.
- **video_models, ad_blueprints** — the aggregator registry + swipe-file (with pgvector embeddings).
- **platform_settings, action_pricing, subscription_plans, credit_packages, feature_flags** — admin-managed configuration.

Key integrity rules: UUID primary keys everywhere (no enumeration); append-only ledger; soft-delete on projects; per-scene status for resumability.

---

## Cross-Cutting Concerns

- **Security**: governed entirely by SECURITY.md; enforced as a per-release checklist. Highlights: object-level authorization on every request, verified idempotent webhooks, locked credit transactions, argument-array FFmpeg, secrets manager, signed URLs.
- **Observability**: Sentry (errors, PII-scrubbed), PostHog (product analytics), audit log for sensitive/admin actions, alerting on anomalies.
- **Scalability**: workers scale independently of API; S3 lifecycle rules control storage cost; Redis-backed rate limits.

---

## Build Sequencing

The phased plan (Phase 0 → Phase 8) is defined in **ARCHITECTURE.md → "Phased Build Plan"** and mirrored as executable tasks in **tasks.md**. Sequencing is deliberately cost-de-risked: foundations → script MVP (cheap, proves value) → ad intelligence → assets → video/stitching (first real API spend) → payments → admin/ops → polish/launch → mobile & extras.
