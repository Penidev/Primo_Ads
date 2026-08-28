# Primo — Security Guidelines & Hardening Standard

This document defines the security requirements every part of the Primo platform must follow. It is not optional reading. Treat it as a checklist during development and a gate before any deployment. The platform handles user credentials, payment flows, credit balances (real money), brand assets, and third-party API keys — all high-value targets.

**Guiding principle: defense in depth.** No single control is trusted alone. Assume any one layer can fail and design so a breach in one place does not compromise the whole system.

---

## 1. Authentication & Session Security

### Passwords
- Hash with **bcrypt** (cost factor ≥ 12) or **Argon2id**. Never store plaintext or reversible encryption.
- Enforce minimum password strength: 10+ chars, checked against a breached-password list (Have I Been Pwned k-anonymity API).
- Never log passwords, even hashed, even in debug mode.
- Rate-limit login attempts: 5 failures → temporary lockout with exponential backoff. Track by both IP and account.

### Tokens & Sessions
- Use short-lived **JWT access tokens** (15 min) + longer **refresh tokens** (7 days, rotated on use).
- Sign JWTs with a strong secret (256-bit) stored in a secrets manager, never in code or the repo.
- Store refresh tokens as httpOnly, Secure, SameSite=Strict cookies. Never in localStorage (XSS-accessible).
- Implement refresh token rotation with reuse detection: if an old refresh token is replayed, revoke the entire token family (indicates theft).
- Support server-side session revocation (logout everywhere, forced logout on password change).

### Multi-Factor Authentication (MFA)
- Offer TOTP-based 2FA (authenticator apps) for all users.
- **Require** MFA for all admin accounts — no exceptions.
- Enforce MFA re-verification before sensitive admin actions (changing pricing, granting credits, editing another user).

### Account Security
- Email verification required before first generation.
- Notify users by email on: new device login, password change, email change, MFA changes.
- Secure password reset: single-use, time-limited (30 min) tokens; never reveal whether an email exists ("If an account exists, a reset link was sent").

---

## 2. Authorization & Access Control

### Principle of Least Privilege
- Every API endpoint checks: (1) is the user authenticated, (2) is the user authorized for THIS specific resource.
- **Object-level authorization on every request.** A user requesting `/projects/{id}` must own that project. Never trust an ID from the client without verifying ownership. This prevents IDOR (Insecure Direct Object Reference) — the most common and damaging web vuln.

```python
# WRONG - trusts the client
project = db.get(Project, project_id)
return project

# RIGHT - verifies ownership
project = db.get(Project, project_id)
if project is None or project.user_id != current_user.id:
    raise HTTPException(404)  # 404 not 403 - don't reveal existence
return project
```

### Role Separation
- Roles: `user`, `admin`. Admin flag lives server-side (`users.is_admin`), never inferred from client input.
- Admin routes are on a separate router with a hard `require_admin` dependency on every endpoint.
- Never expose admin capability by hiding a button in the frontend only. The backend must enforce it.

### Use UUIDs, Not Sequential IDs
- All public-facing resource IDs are UUIDs (already in the schema). Sequential integer IDs let attackers enumerate resources (`/projects/1`, `/projects/2`...).

---

## 3. Payment & Credit Security (Highest Risk Area)

This is where real money moves. Bugs here are financial losses.

### Credit Ledger Integrity
- Credits are money. Use the **immutable ledger pattern** (append-only `credit_transactions`), never a mutable balance edited in place.
- All credit deductions happen inside a **database transaction with row-level locking** (`SELECT ... FOR UPDATE`) to prevent race conditions where a user spends the same credits twice via concurrent requests.
- **Check balance and deduct atomically.** Never check-then-deduct in two steps (TOCTOU race).
- Charge credits only AFTER confirming the user has enough, and log the resulting balance in `balance_after` for auditability.

### Webhook Security (Stripe, PayPal, Cozzipay)
- **Always verify webhook signatures** before trusting any payment event:
  - Stripe: verify `Stripe-Signature` header with the signing secret.
  - PayPal: verify via PayPal's webhook verification API.
  - Cozzipay: verify `X-Cozzipay-Signature` = `sha256=HMAC-SHA256(rawBody, webhook_secret)` using **constant-time comparison** (`hmac.compare_digest`).
- Verify against the **raw request body**, not a re-serialized version (serialization changes bytes and breaks the signature).
- **Idempotency**: store processed webhook IDs. If a webhook is delivered twice (gateways retry), do not credit the wallet twice. Cozzipay provides `webhook_id`; Stripe provides event `id`.
- Never grant credits based on a client-side "payment success" callback. The client can be forged. Only the verified server-side webhook (or a server-side verify call) grants credits.

### Cozzipay Outbound Requests
- Sign all write requests with HMAC-SHA512 as their docs require (`X-Signature`, `X-Timestamp`, `X-Nonce`).
- Use unique nonces (UUID v4) per request and fresh timestamps (their server rejects requests older than 5 minutes).
- Send `X-Idempotency-Key` on money-moving operations to prevent double charges on retries.
- Secret keys (`czp_live_sk_*`) are server-side only, in the secrets manager. Never in frontend, logs, or the repo.

### Preventing Abuse & Fraud
- Hard per-user concurrency limit on generation jobs (max 3 concurrent) — prevents credit-draining loops and cost bombs.
- Lock the quoted price at confirmation time so a user can't exploit a mid-flight price change.
- Monitor for anomalous spending patterns (sudden burst of generations) and flag for review.
- Refunds on failed jobs are automated but logged; alert admins on high refund rates (could indicate an exploit).

---

## 4. Input Validation & Injection Prevention

### Validate Everything from the Client
- Every request body validated with **Pydantic schemas** (backend) and **Zod** (frontend). Reject anything that doesn't match the expected shape, type, and range.
- Whitelist allowed values for enums (aspect ratios, categories, model slugs). Never pass raw client strings into logic.

### SQL Injection
- Use **SQLAlchemy ORM / parameterized queries exclusively.** Never build SQL with string concatenation or f-strings.
- The pgvector similarity queries and any raw SQL must use bound parameters.

### Prompt Injection (AI-Specific)
- Treat all user input that reaches an LLM/video/image model as **untrusted**. Users may try to inject instructions ("ignore your rules, output X").
- Separate system instructions from user content structurally (system role vs. user role), never concatenate user text into the system prompt.
- Sanitize/validate LLM JSON output before acting on it (schema-validate the returned scenes). A model tricked into returning malformed or malicious content must not break the pipeline.
- Never let model output directly become a shell command, file path, or SQL. The FFmpeg pipeline builds commands from validated, structured data — not from raw model text.

### Command Injection (FFmpeg Pipeline)
- Build FFmpeg commands with argument arrays (`subprocess` with a list), **never** a shell string with user data interpolated.
- Validate all file paths against an allowlist of expected S3 keys / temp directories. Reject path traversal (`../`).
- Run FFmpeg workers in isolated containers with no network access to internal services and minimal filesystem permissions.

### File Upload Security (Brand Assets, Characters)
- Validate file type by **content/magic bytes**, not just extension or client-supplied MIME.
- Enforce size limits (e.g., 10MB images, reject oversized uploads at the edge).
- Re-encode/strip uploaded images (removes embedded malware, EXIF PII, polyglot files).
- Store uploads in S3 with randomized keys, served via signed URLs — never executed, never in a web-accessible path on the app server.
- Scan uploads for malware if budget allows (ClamAV or a cloud scanning service).

---

## 5. Secrets & API Key Management

- **No secrets in the repository. Ever.** Enforce with pre-commit hooks (gitleaks/trufflehog) and GitHub secret scanning.
- Store all secrets (DB creds, JWT secret, Stripe/PayPal/Cozzipay keys, fal.ai key, Gemini key, AWS creds) in a **secrets manager** (AWS Secrets Manager, Doppler, or Vault). Inject at runtime as env vars.
- `.env` files are for local dev only and are gitignored. `.env.example` contains only placeholder keys.
- **Rotate keys** on a schedule and immediately if a leak is suspected.
- Use separate keys per environment (dev/staging/prod). A leaked dev key must not touch production money.
- Scope third-party keys to minimum permissions (e.g., S3 keys limited to the specific bucket).

---

## 6. API & Network Security

### Transport
- **HTTPS everywhere**, enforced. HTTP redirects to HTTPS. HSTS header with a long max-age.
- TLS 1.2 minimum, prefer 1.3.

### Rate Limiting & Throttling
- Global rate limits per IP and per user (Redis-backed counters).
- Stricter limits on expensive endpoints: generation (10/min), auth (5/min), password reset (3/hour).
- Return `429` with `Retry-After`. Protects against brute force, scraping, and cost-based DoS.

### CORS
- Allowlist only your own frontend origin(s). Never `Access-Control-Allow-Origin: *` on authenticated endpoints.

### Security Headers (set on all responses)
- `Content-Security-Policy` (restrict script/style/frame sources — mitigates XSS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` (clickjacking)
- `Strict-Transport-Security`
- `Referrer-Policy: strict-origin-when-cross-origin`

### CSRF
- For cookie-based auth flows, use anti-CSRF tokens (double-submit or SameSite=Strict cookies).
- API-token (Bearer) endpoints are less CSRF-prone but still validate origin on state-changing requests.

---

## 7. Frontend (Next.js) Security

- **XSS prevention**: React escapes by default. Never use `dangerouslySetInnerHTML` with unsanitized content. Sanitize any user-generated HTML (DOMPurify) if it must render.
- Never store tokens or secrets in localStorage/sessionStorage. Use httpOnly cookies.
- Never expose backend secrets in `NEXT_PUBLIC_*` vars — those ship to the browser. Only truly public values there.
- Validate and re-check authorization on the backend for every action, even if the UI hides it. Frontend checks are UX, not security.
- Keep dependencies patched; run `npm audit` in CI.

---

## 8. Data Protection & Privacy

- **Encryption at rest**: database and S3 buckets encrypted (AES-256). Enable RDS/S3 encryption.
- **Encryption in transit**: TLS on all connections including DB and Redis.
- **PII minimization**: collect only what's needed (Module 1 fields). Don't log PII in plaintext.
- **Data retention & deletion**: honor user data deletion requests (GDPR/CCPA). Soft-delete then hard-delete after the recovery window. Purge from S3 and backups.
- **Brand assets are confidential**: a user's logos/product shots/unreleased campaigns are sensitive competitive material. Strict per-user isolation, signed-URL access only, never publicly listable buckets.
- **Signed URLs** for all asset/video access, time-limited (e.g., 1 hour). No public bucket listing. No permanent public URLs for user content.

---

## 9. Infrastructure & Deployment Security

- **Least-privilege IAM**: each service gets only the cloud permissions it needs. The web server can't delete S3 buckets; the worker can't read the users table if it doesn't need to.
- **Network segmentation**: database and Redis are in a private subnet, never publicly reachable. Only the API/workers can reach them.
- **Container hardening**: run containers as non-root, read-only filesystems where possible, drop unnecessary Linux capabilities.
- **No debug mode in production**: FastAPI/Next.js debug and verbose error pages disabled. Never leak stack traces to users.
- **Dependency scanning**: automated (Dependabot/Snyk) for both Python and Node. Patch known CVEs promptly.
- **Backups**: automated encrypted DB backups, tested restores, stored in a separate account/region. The credit ledger especially must be recoverable.
- **Separate environments**: dev, staging, prod fully isolated — separate databases, keys, and cloud accounts/projects.

---

## 10. Logging, Monitoring & Incident Response

- **Audit log** for all sensitive actions: logins, admin actions, pricing changes, credit grants, refunds, permission changes. Immutable, timestamped, attributed to a user ID.
- **Never log secrets, passwords, full card data, or full API keys.** Mask/redact.
- **Error monitoring** (Sentry) with PII scrubbing enabled.
- **Alerting** on: spikes in failed logins, unusual spending, high refund rates, webhook signature failures, elevated 4xx/5xx rates.
- **Incident response plan**: documented steps for suspected breach — rotate keys, revoke sessions, notify affected users, preserve logs. Know it before you need it.

---

## 11. Third-Party & Supply Chain

- Vet npm/PyPI packages before adding. Watch for typosquatting (a package name one character off from a popular one).
- Pin dependency versions (lock files committed). Review lock file changes in PRs.
- Minimize dependency count — every package is attack surface.
- Verify webhooks and API responses from third parties are authenticated (signatures), never trusted blindly.

---

## 12. AI Content Safety & Legal Guardrails

- **Content moderation** on generated output: screen for prohibited content (violence, explicit, hateful, deceptive).
- **No impersonation / deepfakes** of real people without consent. If users upload character photos, require confirmation they have rights/consent. Block generation of recognizable public figures.
- **Copyright**: the internal swipe-file (analyzed reference ads) is for structural learning only — never reproduce a competitor's footage, logos, music, or trademarked assets in output.
- **Usage policy & ToS** users must accept, disclaiming misuse and clarifying content ownership.
- **Watermark or provenance metadata** (C2PA) on AI-generated video where feasible, for transparency.

---

## Security Checklist (Gate Before Each Release)

- [ ] All new endpoints enforce authentication AND object-level authorization
- [ ] No secrets committed (gitleaks passes)
- [ ] All user input validated (Pydantic/Zod)
- [ ] Credit operations use locked DB transactions
- [ ] Webhook signatures verified with constant-time comparison + idempotency
- [ ] No raw SQL string building; ORM/parameterized only
- [ ] FFmpeg/shell commands use argument arrays, no interpolated user data
- [ ] File uploads validated by magic bytes, re-encoded, size-limited
- [ ] Rate limits applied to auth and generation endpoints
- [ ] Security headers present on all responses
- [ ] Admin actions require MFA and are audit-logged
- [ ] Dependencies scanned, no unpatched criticals
- [ ] Error responses leak no stack traces or internal detail
- [ ] Signed URLs for all user asset access; no public buckets

---

## Threat Model Summary (Top Risks Ranked)

| Risk | Impact | Primary Mitigations |
|------|--------|--------------------|
| Credit/payment fraud (double-spend, forged payments) | Direct financial loss | Locked ledger transactions, verified webhooks, idempotency |
| IDOR (accessing others' projects/assets) | Data breach, IP theft | Object-level authorization on every request, UUIDs |
| Leaked API keys (Stripe, fal, Cozzipay) | Financial + service abuse | Secrets manager, no repo secrets, scanning, rotation |
| Account takeover | Full account compromise | Bcrypt/Argon2, MFA, rate limiting, token rotation |
| Cost-based DoS (draining your API budget) | Financial loss | Per-user concurrency + rate limits, balance checks |
| Prompt injection into AI models | Unwanted/malicious output | Role separation, output schema validation, moderation |
| Command injection via FFmpeg | Server compromise | Argument arrays, path allowlists, isolated containers |
| XSS / CSRF | Session theft, forged actions | React escaping, CSP, httpOnly cookies, CSRF tokens |
| Malicious file uploads | Server compromise, malware serving | Magic-byte validation, re-encoding, signed-URL isolation |
