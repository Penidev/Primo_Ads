# Shared Packages

Code shared across clients (web now, mobile later). Keeping contracts here ensures web and mobile never drift.

- `shared-types/` — TypeScript types generated from the backend OpenAPI spec
- `api-client/` — typed API client + auth/token logic reused by all clients
- `validation/` — Zod schemas shared between web and mobile forms

These are populated in later phases (see `.kiro/specs/primo-platform/tasks.md`, Task 45). The directory exists now so the monorepo structure is established from the start.
