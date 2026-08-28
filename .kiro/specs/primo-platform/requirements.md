# Requirements — Primo AI Ad Platform

## Introduction

Primo is an end-to-end AI-powered commercial production studio. Business users provide a brand brief; the platform generates a strategic ad concept, a scene-by-scene script with full directorial guidance, pre-generated brand-consistent assets, and (optionally) a finished stitched video produced through a multi-model video-generation aggregator. Users pay via a prepaid credit system funded through Stripe, PayPal, or Cozzipay.

This document defines the functional and non-functional requirements. Design detail lives in `docss/ARCHITECTURE.md`, `docss/PROJECT_STRUCTURE.md`, and `docss/SECURITY.md`. Tasks live in `tasks.md`.

The requirements are grouped by capability area and phased for delivery (Phase 0 through Phase 8). Each requirement uses EARS-style acceptance criteria.

---

## Requirement 1: Platform Foundation & Environment (Phase 0)

**User Story:** As a developer, I want a reproducible local environment and a solid project skeleton, so that the team can build features consistently and deploy reliably.

### Acceptance Criteria
1. WHEN a developer runs the local dev command THEN the system SHALL start the API, worker, database, cache, and web app together via Docker Compose.
2. WHEN the backend starts THEN the system SHALL connect to PostgreSQL and Redis and expose a health-check endpoint returning service status.
3. WHEN database migrations are run THEN the system SHALL create all core tables (users, wallets, credit_transactions, projects, scenes, and supporting tables) as defined in PROJECT_STRUCTURE.md.
4. WHEN the seed command is run THEN the system SHALL create an initial admin user and seed the video model registry and default pricing.
5. IF a required environment variable is missing at startup THEN the system SHALL fail fast with a clear error naming the missing variable.

---

## Requirement 2: Authentication & Account Security (Phase 0-1)

**User Story:** As a user, I want a secure account, so that my projects, assets, and credits are protected.

### Acceptance Criteria
1. WHEN a user registers with email and password THEN the system SHALL store the password hashed with bcrypt (cost ≥ 12) or Argon2id and SHALL never store it in plaintext.
2. WHEN a user logs in with valid credentials THEN the system SHALL issue a short-lived JWT access token and a rotating refresh token.
3. WHEN a user submits invalid credentials repeatedly THEN the system SHALL rate-limit attempts and apply exponential backoff by IP and account.
4. WHEN a user requests a password reset THEN the system SHALL send a single-use, time-limited token and SHALL NOT reveal whether the email exists.
5. WHEN a user enables 2FA THEN the system SHALL require a valid TOTP code on subsequent logins.
6. WHEN an admin logs in THEN the system SHALL require MFA before granting admin access.
7. WHEN any request accesses a resource THEN the system SHALL verify the authenticated user owns or is authorized for that specific resource (object-level authorization).

---

## Requirement 3: User Onboarding & Intelligence Collection (Phase 1)

**User Story:** As a new user, I want a guided onboarding that captures my brand and preferences, so that the platform personalizes my experience.

### Acceptance Criteria
1. WHEN a user completes registration THEN the system SHALL guide them through a progressive onboarding wizard collecting name, company, country, industry, role, use case, and preferred ad platforms.
2. WHEN a user submits onboarding data THEN the system SHALL persist it to their profile and mark onboarding complete.
3. WHERE a user chooses to skip optional steps THE system SHALL allow them to proceed and complete those fields later in settings.
4. WHEN onboarding completes THEN the system SHALL land the user on the dashboard with a first-project prompt.

---

## Requirement 4: Project & Brief Intake (Phase 1)

**User Story:** As a user, I want to create a project by filling a structured brief, so that the AI has the strategic input it needs to produce a relevant ad.

### Acceptance Criteria
1. WHEN a user starts a new project THEN the system SHALL present a multi-step brief wizard (brand identity, product/audience, competition, campaign config, optional assets/characters).
2. WHILE a user fills the brief THE system SHALL auto-save progress (debounced) to the database so no input is lost on refresh or logout.
3. WHEN a user uploads brand assets THEN the system SHALL validate file type by content, enforce size limits, store them securely in object storage, and associate them with the project.
4. WHEN a user submits a complete brief THEN the system SHALL persist the full brief as structured JSON and set project status to allow script generation.
5. WHEN a user returns to a project THEN the system SHALL route them to the correct step based on project status and pre-fill all previously entered data.

---

## Requirement 5: AI Script & Direction Generation (Phase 1-2)

**User Story:** As a user, I want the platform to generate a scene-by-scene script with directorial detail, so that I have a professional ad concept ready to produce.

### Acceptance Criteria
1. WHEN a user requests script generation AND has sufficient credits THEN the system SHALL deduct the configured credit cost and generate a structured scene-by-scene script.
2. WHEN generating a script THEN the system SHALL retrieve relevant ad blueprints (RAG) matching the selected category, industry, and format, and use them as context.
3. WHEN a script is generated THEN the system SHALL return, per scene: script text, voiceover direction, visual description, camera movement, color grading, lighting, audio/SFX, brand elements, a compiled video-model prompt, and any required asset descriptions.
4. WHEN a script is generated THEN the system SHALL persist it to the project and create scene records.
5. IF the user has insufficient credits THEN the system SHALL block generation and prompt them to top up, deducting nothing.
6. WHEN a script-only user views a completed script THEN the system SHALL offer export as PDF, DOCX, and a shot list.

---

## Requirement 6: Ad Intelligence & Swipe File System (Phase 2)

**User Story:** As an admin, I want to analyze winning ads into structured blueprints, so that the script engine produces non-generic, pattern-informed output.

### Acceptance Criteria
1. WHEN an admin uploads a reference ad video THEN the system SHALL analyze it with a multimodal model and produce a structured blueprint (category, triggers, structural arc, pacing, camera techniques, color strategy, hook style).
2. WHEN a blueprint is created THEN the system SHALL generate a text embedding and store it for semantic retrieval.
3. WHEN an admin reviews a blueprint THEN the system SHALL allow tagging (industry, category, effectiveness score) and approval before it is used in retrieval.
4. WHEN the script engine retrieves context THEN the system SHALL return only approved blueprints ranked by relevance.
5. THE system SHALL NOT reproduce copyrighted footage, logos, or trademarked assets from reference ads in any generated output.

---

## Requirement 7: Asset Pre-Generation (Phase 3)

**User Story:** As a user, I want brand-consistent reference assets generated before video, so that the final video accurately reflects my brand and characters.

### Acceptance Criteria
1. WHEN a script identifies required assets THEN the system SHALL generate reference images per scene incorporating brand colors, style, and any uploaded references.
2. WHEN assets are generated THEN the system SHALL present them for user review with approve, regenerate, or upload-replacement options.
3. WHERE a user uploads their own character or product images THE system SHALL use those directly as references and SHALL NOT charge for uploads.
4. WHEN AI-generated characters are needed across scenes THEN the system SHALL generate a reusable character reference to maintain consistency.
5. WHEN a user approves assets THEN the system SHALL attach them as reference inputs for video generation.

---

## Requirement 8: Video Model Aggregator (Phase 4)

**User Story:** As a user, I want to choose among multiple video-generation models, so that I can balance quality, style, and credit cost.

### Acceptance Criteria
1. WHEN a user reaches the generation step THEN the system SHALL present available, enabled video models with quality tier, estimated time, and credit cost.
2. WHEN a user selects a model THEN the system SHALL compute and display the total credit cost (base cost × model multiplier × scene count) before charging.
3. WHERE a user chooses "let AI select" THE system SHALL pick a suitable model based on brief requirements (e.g., audio needed).
4. WHEN an admin adds a new model to the registry THEN the system SHALL make it available to users without a code deployment for supported providers.
5. WHEN an admin disables a model THEN the system SHALL immediately stop offering it to users.
6. THE system SHALL route all models through a unified adapter interface so new providers can be added by implementing one adapter.

---

## Requirement 9: Video Generation & Stitching Pipeline (Phase 4)

**User Story:** As a user, I want my scenes generated and stitched into one finished video, so that I can download a complete ad.

### Acceptance Criteria
1. WHEN a user confirms generation AND is charged THEN the system SHALL queue each scene as an asynchronous job and track per-scene status.
2. WHILE scenes are generating THE system SHALL push real-time progress updates to the user via WebSocket/SSE.
3. WHEN a scene generation fails THEN the system SHALL retry up to 3 times with exponential backoff.
4. IF a scene fails permanently after retries THEN the system SHALL refund the credits for that scene and notify the user.
5. WHEN all scenes complete THEN the system SHALL normalize (frame rate, resolution, pixel format, audio codec) and stitch them into a single video with FFmpeg, then store it.
6. WHEN a user views the timeline THEN the system SHALL show each scene block with thumbnail and status and allow per-scene re-roll, model swap, and prompt edit.
7. WHEN a user re-rolls a single scene THEN the system SHALL regenerate only that scene, re-stitch, and charge only for that scene.
8. WHEN generation completes THEN the system SHALL save the final video and all scene clips and allow the user to resume/download later.

---

## Requirement 10: Credit & Monetization System (Phase 5)

**User Story:** As a user, I want a transparent prepaid credit system, so that I understand and control what I spend.

### Acceptance Criteria
1. THE system SHALL record all credit changes in an append-only ledger and SHALL NOT mutate a balance without a corresponding transaction record.
2. WHEN credits are deducted THEN the system SHALL perform the balance check and deduction atomically within a locked database transaction to prevent double-spend.
3. WHEN a user purchases credits or subscribes THEN the system SHALL create a checkout session via the chosen gateway (Stripe, PayPal, or Cozzipay).
4. WHEN a payment gateway sends a webhook THEN the system SHALL verify its signature using constant-time comparison before crediting the wallet.
5. WHEN a webhook is delivered more than once THEN the system SHALL process it idempotently and SHALL NOT credit the wallet twice.
6. THE system SHALL grant credits only after server-side payment verification, never based on a client-side success callback.
7. WHEN a subscription renews, pauses, or cancels THEN the system SHALL update the user's plan and credit grants accordingly via verified webhooks.

---

## Requirement 11: Admin Dashboard & Pricing Control (Phase 5-6)

**User Story:** As an admin, I want full control over pricing, models, users, and features, so that I can operate the business without code changes.

### Acceptance Criteria
1. THE system SHALL read every chargeable price from the database at runtime and SHALL NOT hardcode any price, credit cost, or ratio in application code.
2. WHEN an admin sets the credit-to-USD ratio THEN the system SHALL apply it to all pricing math immediately.
3. WHEN an admin edits an action's base credits or a model's multiplier THEN the system SHALL apply the change immediately without deployment.
4. WHEN an admin views a model THEN the system SHALL show live margin analysis (platform API cost vs. user-facing price).
5. WHEN an admin creates or edits subscription plans or credit packages THEN the system SHALL reflect changes on the pricing page immediately.
6. WHEN an admin grants manual credits or issues a refund THEN the system SHALL record it in the ledger with attribution.
7. WHEN an admin performs a sensitive action THEN the system SHALL require MFA and write an immutable audit log entry.
8. WHEN an admin toggles a feature flag THEN the system SHALL enable/disable the corresponding capability globally or per tier/user without deployment.

---

## Requirement 12: Project Persistence & Resume (Phase 1, cross-cutting)

**User Story:** As a user, I want everything I create saved server-side, so that I can stop and resume across sessions and devices.

### Acceptance Criteria
1. THE system SHALL persist briefs, scripts, compiled prompts, assets, scene clips, and final videos to the database and object storage, not browser storage.
2. WHEN a user closes and reopens a project THEN the system SHALL restore it to its exact prior state including partial scene progress.
3. WHEN a project has partially generated scenes THEN the system SHALL preserve completed scenes and SHALL NOT re-charge for them on resume.
4. WHEN a user views their dashboard THEN the system SHALL list all their projects with thumbnail, title, status, credits spent, and last-modified date.
5. WHEN a user deletes a project THEN the system SHALL soft-delete it with a 30-day recovery window before permanent removal.

---

## Requirement 13: Security & Compliance (cross-cutting, all phases)

**User Story:** As the platform owner, I want the system hardened against attacks, so that user data, money, and reputation are protected.

### Acceptance Criteria
1. THE system SHALL follow all controls defined in `docss/SECURITY.md` as a release gate.
2. THE system SHALL validate all client input server-side with typed schemas and reject malformed requests.
3. THE system SHALL use parameterized queries exclusively and SHALL NOT build SQL from string concatenation.
4. THE system SHALL construct FFmpeg/shell commands from argument arrays with validated paths and SHALL NOT interpolate raw model or user text into shell commands.
5. THE system SHALL store all secrets in a secrets manager and SHALL NOT commit secrets to the repository.
6. THE system SHALL serve all user assets via time-limited signed URLs and SHALL NOT expose public buckets.
7. THE system SHALL enforce HTTPS, security headers, and per-endpoint rate limits.
8. THE system SHALL moderate generated content and block impersonation of real people without consent.

---

## Requirement 14: Scalability & Operations (Phase 6)

**User Story:** As the platform owner, I want the system to scale and self-heal, so that heavy load and transient failures don't break the product or lose money.

### Acceptance Criteria
1. THE system SHALL process long-running work (script, asset, video, stitch) through background queues, never blocking HTTP requests.
2. WHEN load increases THEN the system SHALL scale workers independently of the web/API tier.
3. WHEN a job fails transiently THEN the system SHALL retry with backoff and, on permanent failure, refund and alert.
4. THE system SHALL apply object-storage lifecycle rules to control cost (raw clips short-lived, finals medium-lived, brand uploads retained).
5. THE system SHALL emit errors to monitoring and alert on anomalies (failed logins, unusual spend, webhook signature failures, elevated error rates).

---

## Requirement 15: Multi-Client / Mobile Readiness (foundation now, app in Phase 8)

**User Story:** As the platform owner, I want to add a mobile app later without backend rework, so that we can expand reach efficiently.

### Acceptance Criteria
1. THE system SHALL keep all business logic in the backend so any client (web, mobile) consumes the same API.
2. THE system SHALL use token-based auth compatible with both browsers and native apps.
3. THE system SHALL expose an OpenAPI spec from which client types are generated.
4. THE system SHALL keep shared contracts and validation in shared packages consumable by web and mobile.
