"""Deterministic in-process provider fakes.

These are **peer implementations** of the live adapter interfaces, not a mode the
business logic branches on. Every mock:

* implements the same abstract base class as its live counterpart,
* accepts and returns the same types,
* raises the same exception classes on failure,
* reproduces the same asynchronous lifecycle (submit then poll) so retry,
  refund, and progress code paths are genuinely exercised.

Consequences, which are the point:

* No service or route contains a mock branch. Selection happens once, in
  `app.adapters.factory`.
* Switching to live providers is a config change, not a code change.
* Deleting this package would require no edits to business logic.
"""
