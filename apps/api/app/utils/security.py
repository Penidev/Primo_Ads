"""Password hashing and verification (SECURITY.md §1).

Uses the `bcrypt` package directly rather than `passlib`. Two reasons:

1. `passlib` 1.7.4 is its last release (2020) and reads `bcrypt.__about__`,
   which bcrypt removed in 4.1. On bcrypt 5.x, `passlib`'s backend detection
   raises and every hash call fails — registration, login, and seeding all
   break. Pinning bcrypt below 4.1 would work but freezes a security-critical
   dependency against an unmaintained wrapper.
2. The wrapper earns little here: bcrypt's own API is three stable functions.

Passwords are SHA-256 pre-hashed before bcrypt. bcrypt only considers the
first 72 bytes of its input, and silently ignoring the rest would mean two
different long passphrases could share a hash. Pre-hashing folds the whole
password into a fixed 44-byte value, so length is never truncated. This is the
same construction as Django's `BCryptSHA256PasswordHasher` and passlib's
`bcrypt_sha256`.
"""

import base64
import hashlib

import bcrypt

# Cost factor. Raising this is safe: existing hashes carry their own cost and
# still verify, so a change only affects newly created hashes.
BCRYPT_ROUNDS = 12


def _prehash(password: str) -> bytes:
    """Fold a password into a fixed-length, NUL-free value for bcrypt.

    Base64 rather than the raw digest because bcrypt treats a NUL byte as a
    string terminator, and a raw SHA-256 digest can contain one.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(_prehash(password), salt).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison against a stored hash.

    A malformed or truncated stored hash returns False rather than raising: a
    corrupt row should fail authentication, not return a 500 that reveals the
    account exists.
    """
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


MIN_PASSWORD_LENGTH = 10


def validate_password_strength(password: str) -> list[str]:
    """Return a list of failed-requirement messages (empty = strong enough).

    Enforces the baseline from SECURITY.md §1. A breached-password check
    (HIBP k-anonymity) can be layered on later without changing callers.
    """
    errors: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if not any(c.isalpha() for c in password):
        errors.append("Password must contain at least one letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number.")
    return errors
