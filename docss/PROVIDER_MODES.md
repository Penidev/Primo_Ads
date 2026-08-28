# Provider Modes

Primo runs against real providers (`live`) or deterministic in-process fakes
(`mock`). This document exists to answer one question: **how do we make sure mock
mode never becomes an obstacle to integrating the real APIs?**

## The rule

> Mocks are peer implementations of the adapter interfaces. They are never a mode
> the business logic branches on.

Concretely:

- Every mock subclasses the same abstract base class as its live counterpart
  (`LLMAdapter`, `ImageAdapter`, `VideoModelAdapter`, `StorageAdapter`).
- Selection happens in exactly one file: `app/adapters/factory.py`.
- **No service, route, or worker contains a mock branch.** There is no `if mock:`
  anywhere outside the factory.
- Deleting `app/adapters/mock/` would require zero edits to business logic. Only
  the factory's mock branches would need removing.

This is enforced by tests in `tests/test_provider_factory.py` and
`tests/test_mock_providers.py`, and is verifiable at any time:

```bash
# Should return nothing outside app/adapters/
grep -rn "MockLLMAdapter\|MockImageAdapter\|MockVideoAdapter" apps/api/app \
  --include=*.py | grep -v "app/adapters/"
```

## Why the mocks are faithful, not convenient

A mock that is easier than reality hides bugs until integration day. These
deliberately reproduce the awkward parts:

| Real behaviour | How the mock reproduces it |
|---|---|
| Video jobs are asynchronous | `submit` returns a handle; status goes **queued → running → completed** over successive polls. Nothing completes instantly, so the polling loop, per-scene status transitions, and progress UI are genuinely exercised. |
| Providers return media, not URLs to nowhere | The image mock writes a real decodable PNG. The video mock renders a real MP4 via ffmpeg when available, so FFmpeg stitching operates on genuine media. |
| Providers fail | Failure is injectable, and raises **the same exception classes** as live adapters (`LLMRequestError`, `ImageProviderError`, failed `JobState`), so retry and refund paths run. |
| Model output must be schema-valid | Mock output is validated by the same strict Pydantic schemas as live output, including the rule that scene durations sum to the total. |
| Embeddings have fixed dimensionality | The mock returns a `1536`-dimension vector matching the pgvector column, so similarity queries behave. |
| Credentials can be missing | Live mode without keys raises one consistent `ProviderUnavailableError`, so callers need no per-provider handling. |

## Failure injection

Include a token in the prompt to force a failure:

| Token | Effect |
|---|---|
| `__FAIL_LLM__` | Script/analysis raises `LLMRequestError` |
| `__FAIL_IMAGE__` | Image generation raises `ImageProviderError`; the per-image refund path runs |
| `__FAIL_VIDEO__` | Video job reports `FAILED`; retry and per-scene refund run |

## Production safety

Mock mode is refused at startup when `ENVIRONMENT=production`:

```python
if settings.is_production and settings.provider_mode == "mock":
    raise RuntimeError("PROVIDER_MODE=mock is not permitted when ENVIRONMENT=production.")
```

Serving fabricated creative work to paying customers is a hard failure, not a
warning. `live` is also the default, so no one gets fakes by forgetting to set a
variable.

## Usage

```bash
# Local stack with fakes: no keys, no spend
make dev-mock

# Local stack with real providers (needs keys in apps/api/.env)
make dev
```

CI runs the backend job with `PROVIDER_MODE=mock` against a real Postgres and
Redis, so migrations, the seed script, `/health`, and the full test suite execute
on every push without any credentials.

## Integrating a real API later

1. Implement the adapter against the existing interface (or reuse an existing one
   and add a registry row, for fal-hosted video models).
2. Add the branch in `factory.py`.
3. Set the credential and `PROVIDER_MODE=live`.

No business logic changes. That is the whole point of the constraint.
