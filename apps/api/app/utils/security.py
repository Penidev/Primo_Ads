"""Password hashing and verification (SECURITY.md §1)."""

from passlib.context import CryptContext

# bcrypt with a strong cost factor; passlib handles salting.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


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
