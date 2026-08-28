"""TOTP (RFC 6238) implementation using only the standard library.

Deliberately dependency-free: authenticator codes are a security primitive, and
the algorithm is small enough that owning it beats adding a package. Verified
against the RFC 6238 reference test vectors in `tests/test_totp.py`.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
PERIOD_SECONDS = 30
# Accept the adjacent windows so a code is not rejected for mild clock drift.
DEFAULT_DRIFT_WINDOWS = 1
SECRET_BYTES = 20  # 160-bit, the RFC-recommended size for SHA-1 HMAC


def generate_secret() -> str:
    """Return a new base32 secret suitable for authenticator apps."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii")


def _decode_secret(secret: str) -> bytes:
    # Authenticator apps display secrets without padding; restore it.
    cleaned = secret.strip().replace(" ", "").upper()
    padding = "=" * (-len(cleaned) % 8)
    try:
        return base64.b32decode(cleaned + padding, casefold=True)
    except Exception as exc:  # noqa: BLE001 - any decode failure is invalid input
        raise ValueError("Invalid TOTP secret.") from exc


def generate_code(
    secret: str,
    *,
    timestamp: float | None = None,
    digits: int = DIGITS,
    period: int = PERIOD_SECONDS,
) -> str:
    """Compute the TOTP code for a point in time."""
    key = _decode_secret(secret)
    counter = int((timestamp if timestamp is not None else time.time()) // period)
    if counter < 0:
        # Counters are unsigned in RFC 4226; a pre-epoch time is not a valid step.
        raise ValueError("Timestamp precedes the TOTP epoch.")
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()

    # Dynamic truncation (RFC 4226 §5.3).
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10**digits)).zfill(digits)


def verify_code(
    secret: str,
    code: str,
    *,
    timestamp: float | None = None,
    digits: int = DIGITS,
    period: int = PERIOD_SECONDS,
    drift_windows: int = DEFAULT_DRIFT_WINDOWS,
) -> bool:
    """Check a submitted code, tolerating small clock drift.

    Comparison is constant-time so a timing signal cannot reveal the code.
    """
    candidate = (code or "").strip().replace(" ", "")
    if not candidate.isdigit() or len(candidate) != digits:
        return False

    now = timestamp if timestamp is not None else time.time()
    for window in range(-drift_windows, drift_windows + 1):
        candidate_time = now + (window * period)
        if candidate_time < 0:
            continue  # drift window fell before the epoch; nothing to compare
        try:
            expected = generate_code(
                secret,
                timestamp=candidate_time,
                digits=digits,
                period=period,
            )
        except ValueError:
            return False  # malformed secret
        if hmac.compare_digest(expected, candidate):
            return True
    return False


def provisioning_uri(secret: str, account_name: str, issuer: str = "Primo") -> str:
    """otpauth:// URI that authenticator apps consume as a QR code."""
    label = quote(f"{issuer}:{account_name}", safe="")
    params = (
        f"secret={secret}"
        f"&issuer={quote(issuer, safe='')}"
        f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD_SECONDS}"
    )
    return f"otpauth://totp/{label}?{params}"


def generate_recovery_codes(count: int = 8) -> list[str]:
    """Single-use recovery codes for when the authenticator is lost."""
    return [
        f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}"
        for _ in range(count)
    ]
