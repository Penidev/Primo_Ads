"""Redaction of sensitive values before anything leaves the process.

Kept dependency-free and separate from the monitoring service so it can be used
(and tested) anywhere: log formatters, error reporting, or debug output
(SECURITY.md §10).
"""

import re
from typing import Any

MAX_DEPTH = 6
REDACTED = "[redacted]"

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|authorization|cookie|signature|pin|cvv)",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_BEARER_PATTERN = re.compile(r"(Bearer|Key)\s+[\w\-.=]+", re.IGNORECASE)


def scrub_text(value: str) -> str:
    """Redact credentials and identifiers from a string."""
    cleaned = _BEARER_PATTERN.sub(rf"\1 {REDACTED}", value)
    cleaned = _EMAIL_PATTERN.sub(REDACTED, cleaned)
    return _CARD_PATTERN.sub(REDACTED, cleaned)


def scrub(data: Any, _depth: int = 0) -> Any:
    """Recursively redact sensitive values from a payload.

    Keys matching known secret names are replaced wholesale; string values are
    pattern-scrubbed; other scalars pass through unchanged.
    """
    if _depth > MAX_DEPTH:
        return REDACTED
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            if _SENSITIVE_KEY_PATTERN.search(str(key)):
                result[str(key)] = REDACTED
            else:
                result[str(key)] = scrub(value, _depth + 1)
        return result
    if isinstance(data, (list, tuple)):
        return [scrub(item, _depth + 1) for item in data]
    if isinstance(data, str):
        return scrub_text(data)
    return data
