# Implementation Plan â€” Primo AI Ad Platform

Tasks are grouped by phase and sequenced to de-risk cost and complexity. Each task references the requirements it satisfies. Check off tasks as they are completed.

---

## Phase 0 â€” Foundations

- [x] 1. Initialize monorepo structure
  - Create root layout (`apps/`, `packages/`, `infrastructure/`, `docs/`) per PROJECT_STRUCTURE.md
  - Add root README, .gitignore, Makefile, and pre-commit hooks (gitleaks for secret scanning)
  - _Requirements: 1, 13.5_

- [x] 2. Scaffold the FastAPI backend
  - Create `apps/api` with app package, config (pydantic-settings), main entrypoint, health endpoint
  - Fail-fast validation of required env vars on startup
  - _Requirements: 1.2, 1.5_

- [x] 3. Set up database layer and migrations
  - Configure SQLAlchemy async session and Alembic
  - Implement core ORM models: users, wallets, credit_transactions, projects, scenes
  - Create initial migration covering all tables in PROJECT_STRUCTURE.md
  - _Requirements: 1.3, 12.1_

- [x] 4. Scaffold the Next.js web app
  - Create `apps/web` with App Router, TypeScript, Tailwind, Shadcn/UI
  - Set up route groups: (marketing), (auth), (dashboard), (admin)
  - Add API client (`lib/api.ts`) and base layout shells
  - _Requirements: 1.1_

- [ ] 5. Docker Compose dev environment
  - Compose file for postgres (pgvector), redis, api, worker, web
  - Verify `make dev` starts the full stack and the health endpoint responds
  - _Requirements: 1.1, 1.2_

- [x] 6. Seed scripts
  - Seed initial admin user, video model registry, and default pricing rows (platform_settings, action_pricing, subscription_plans, credit_packages)
  - _Requirements: 1.4, 11.1_

---

## Phase 1 â€” Auth, Onboarding & Script MVP

- [x] 7. Authentication backend
  - Registration with bcrypt/Argon2id hashing; login issuing JWT access + rotating refresh tokens
  - Refresh rotation with reuse detection; logout/revocation; password reset (single-use, non-enumerating)
  - Rate limiting on auth endpoints with backoff
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 8. Object-level authorization dependency
  - Reusable dependency verifying the current user owns/accesses the requested resource; 404 on mismatch
  - _Requirements: 2.7, 13.2_

- [x] 9. Auth frontend
  - Register, login, password reset pages; token handling via httpOnly cookies; auth guard on dashboard/admin routes
  - _Requirements: 2.1, 2.2_

- [x] 10. Onboarding wizard
  - Progressive multi-step wizard collecting profile + preferences; persist to profile; skip/resume support
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 11. Project & brief data + endpoints
  - Project CRUD with ownership checks; brief persistence as JSONB; auto-save (debounced) endpoint
  - Secure asset upload (magic-byte validation, size limits, S3 storage, signed URLs)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 12.1, 13.6_

- [x] 12. Brief intake wizard (frontend)
  - Multi-step form (brand, product/audience, competition, campaign, assets/characters) with client validation (Zod) and auto-save
  - _Requirements: 4.1, 4.2_

- [x] 13. Project folder & resume
  - Dashboard project list (thumbnail, title, status, credits spent, last-modified); status-based routing on open; soft-delete with 30-day recovery
  - _Requirements: 12.2, 12.4, 12.5_

- [x] 14. Credit service (core, pre-payments)
  - Immutable ledger; atomic locked deduct/grant; balance check; cost computation from action_pricing Ã— model multiplier
  - _Requirements: 10.1, 10.2, 11.1_

- [x] 15. LLM adapter + script service (RAG-lite)
  - LLM adapter base + Gemini adapter; script service producing the per-scene structured schema
  - Initial RAG using category/industry/format filters (semantic upgrade in Phase 2)
  - Deduct credits on generation; block on insufficient balance
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 16. Script/storyboard view + exports
  - Scene-card storyboard UI; expandable directorial detail; PDF/DOCX/shot-list export
  - _Requirements: 5.6, 6 (consumes blueprints later)_

---

## Phase 2 â€” Ad Intelligence Pipeline

- [x] 17. Swipe-file analysis pipeline
  - Admin upload of reference ads; multimodal analysis into structured blueprint; store with tags
  - _Requirements: 6.1, 6.3_

- [x] 18. Embeddings + semantic retrieval
  - Generate embeddings (pgvector); upgrade RAG to semantic similarity + filters; approved-only retrieval
  - _Requirements: 6.2, 6.4_

- [x] 19. Category management + user picker
  - Admin category CRUD; user-facing visual category picker with examples
  - _Requirements: 6.3, 4.1_

---

## Phase 3 â€” Asset Pre-Generation

- [x] 20. Image adapter + asset service
  - Image adapter base + Flux (via fal) adapter; per-scene asset generation with brand color/style injection
  - _Requirements: 7.1_

- [x] 21. Character consistency
  - Reusable character reference generation; reuse across scenes; use user-uploaded characters directly
  - _Requirements: 7.3, 7.4_

- [x] 22. Asset review UI
  - Approve / regenerate / upload-replacement per asset; attach approved assets as video references (no charge for uploads)
  - _Requirements: 7.2, 7.5_

---

## Phase 4 â€” Video Generation & Stitching

- [x] 23. Video model registry + admin CRUD
  - Registry-driven models; admin add/edit/enable/disable; capabilities + pricing fields
  - _Requirements: 8.4, 8.5, 11.3_

- [x] 24. Video adapter layer
  - Adapter base interface + fal adapter (Veo/Kling/Seedance/MiniMax/Wan); Runway adapter stub
  - _Requirements: 8.6_

- [x] 25. Model selection UI + cost preview
  - Model cards (tier, time, cost); "let AI select"; total cost computed and confirmed before charge
  - _Requirements: 8.1, 8.2, 8.3_

- [x] 26. Async generation queue
  - Celery video tasks; per-scene status tracking; prompt compiler (brand tags + reference images)
  - Retry with backoff; permanent-failure per-scene refund + notify
  - _Requirements: 9.1, 9.3, 9.4_

- [ ] 27. Real-time progress
  - WebSocket/SSE channel pushing per-scene progress to the frontend
  - _Requirements: 9.2_

- [x] 28. FFmpeg stitching worker
  - Normalize (fps, resolution, pixfmt, audio) and concat via argument arrays with validated paths; store final + preview
  - _Requirements: 9.5, 13.4_

- [x] 29. Timeline UI + re-roll
  - Timeline blocks with thumbnails/status; per-scene re-roll/model-swap/prompt-edit; re-stitch; charge only re-rolled scene
  - _Requirements: 9.6, 9.7, 9.8_

- [ ] 30. Storage lifecycle
  - S3 lifecycle rules (raw clips short-lived, finals medium, brand uploads retained)
  - _Requirements: 14.4_

---

## Phase 5 â€” Monetization & Payments

- [x] 31. Payment adapter layer
  - Base payment adapter; Stripe, PayPal, Cozzipay adapters (checkout session creation)
  - Cozzipay HMAC-SHA512 request signing (X-Signature/Timestamp/Nonce) + idempotency keys
  - _Requirements: 10.3, 13.5_

- [x] 32. Webhook handling (all gateways)
  - Signature verification (constant-time) against raw body; idempotent processing; credit grant only after verification
  - Subscription lifecycle handling (renew/pause/cancel)
  - _Requirements: 10.4, 10.5, 10.6, 10.7_

- [x] 33. Billing UI
  - Plans, top-up packages, transaction history, subscription management; balance display
  - _Requirements: 10.3, 12.4_

---

## Phase 6 â€” Admin, Pricing Control & Ops Hardening

- [x] 34. Admin pricing controls
  - Credit-to-USD ratio, action base credits, model multipliers, plans, packages â€” all editable at runtime; live margin analysis
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 35. Admin user & credit operations
  - User management (view/suspend/impersonate/role); manual credit grants and refunds with audit logging
  - _Requirements: 11.6_

- [x] 36. MFA + audit log for admin
  - Enforce MFA for admin login and sensitive actions; immutable audit log
  - _Requirements: 2.6, 11.7_

- [x] 37. Feature flag system
  - Flag storage + evaluation; gate modules/models globally or per tier/user; admin toggle UI
  - _Requirements: 11.8_

- [x] 38. Rate limiting, headers, CORS
  - Redis-backed per-user/IP limits; security headers; strict CORS
  - _Requirements: 13.7_

- [x] 39. Monitoring & alerting
  - Sentry (PII-scrubbed), PostHog events; alerts on failed logins, unusual spend, webhook signature failures, error spikes
  - _Requirements: 14.5_

- [x] 40. Content moderation & legal guardrails
  - Output moderation; block impersonation of real people without consent; ToS acceptance
  - _Requirements: 13.8, 6.5_

---

## Phase 7 â€” Polish & Launch

- [x] 41. Marketing site & pricing page (dynamic from DB)
  - _Requirements: 11.5_

- [x] 42. Onboarding polish, tooltips, guided first project
  - _Requirements: 3.4_

- [x] 43. Responsive dashboard + performance (lazy load, CDN, caching)
  - _Requirements: 1_

- [ ] 44. Security audit against SECURITY.md checklist + load testing
  - _Requirements: 13.1, 14.1, 14.2_

---

## Phase 8 â€” Post-Launch (Mobile & Extras)

- [ ] 45. Shared packages hardening (shared-types from OpenAPI, api-client, validation)
  - _Requirements: 15.3, 15.4_

- [ ] 46. React Native (Expo) mobile app consuming existing API
  - _Requirements: 15.1, 15.2_

- [ ] 47. Additional models, fine-tuning exploration, team/workspace features, voiceover/music, A/B variant generation
  - _Requirements: 8.4, 5_








