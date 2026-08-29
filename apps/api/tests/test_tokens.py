"""JWT token tests (SECURITY.md §1)."""

import pytest

from app.utils.security import hash_password, validate_password_strength, verify_password
from app.utils.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestAccessTokens:
    def test_round_trip_preserves_subject(self):
        token = create_access_token("user-123")
        assert decode_token(token, "access")["sub"] == "user-123"

    def test_carries_extra_claims(self):
        token = create_access_token("user-123", extra={"admin": True})
        assert decode_token(token, "access")["admin"] is True

    def test_each_token_has_unique_jti(self):
        a = decode_token(create_access_token("u"), "access")["jti"]
        b = decode_token(create_access_token("u"), "access")["jti"]
        assert a != b

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token("user-123")
        with pytest.raises(TokenError):
            decode_token(token, "refresh")

    def test_tampered_token_rejected(self):
        token = create_access_token("user-123")
        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
        with pytest.raises(TokenError):
            decode_token(tampered, "access")

    def test_garbage_rejected(self):
        with pytest.raises(TokenError):
            decode_token("not-a-token", "access")


class TestRefreshTokens:
    def test_returns_family_and_jti(self):
        token, family, jti = create_refresh_token("user-1")
        payload = decode_token(token, "refresh")
        assert payload["fam"] == family
        assert payload["jti"] == jti

    def test_rotation_keeps_family_changes_jti(self):
        _, family, first_jti = create_refresh_token("user-1")
        _, same_family, second_jti = create_refresh_token("user-1", family_id=family)
        assert same_family == family
        assert first_jti != second_jti

    def test_refresh_token_rejected_as_access(self):
        token, _, _ = create_refresh_token("user-1")
        with pytest.raises(TokenError):
            decode_token(token, "access")


class TestPasswords:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("correct horse 9")
        assert hashed != "correct horse 9"

    def test_hash_is_salted(self):
        assert hash_password("same password 1") != hash_password("same password 1")

    def test_verify_accepts_correct_password(self):
        hashed = hash_password("correct horse 9")
        assert verify_password("correct horse 9", hashed) is True

    def test_verify_rejects_wrong_password(self):
        hashed = hash_password("correct horse 9")
        assert verify_password("wrong horse 9", hashed) is False

    @pytest.mark.parametrize(
        "password,expected_ok",
        [
            ("short1", False),  # too short
            ("alllettersonly", False),  # no digit
            ("1234567890", False),  # no letter
            ("valid pass 1", True),
        ],
    )
    def test_strength_rules(self, password, expected_ok):
        errors = validate_password_strength(password)
        assert (errors == []) is expected_ok

    # --- bcrypt's 72-byte limit -------------------------------------------
    # bcrypt ignores input past 72 bytes. Without SHA-256 pre-hashing, any two
    # passwords sharing a 72-byte prefix would be interchangeable, and bcrypt
    # 5.x raises outright on longer input. These pin both behaviours.

    def test_password_longer_than_72_bytes_round_trips(self):
        long_password = "a" * 100 + "1"
        hashed = hash_password(long_password)
        assert verify_password(long_password, hashed) is True

    def test_passwords_sharing_a_72_byte_prefix_are_distinguished(self):
        base = "x" * 72
        first = base + "aaa1"
        second = base + "bbb2"
        hashed = hash_password(first)
        assert verify_password(first, hashed) is True
        assert verify_password(second, hashed) is False

    def test_multibyte_password_round_trips(self):
        # 40 emoji is 160 UTF-8 bytes, well past the bcrypt ceiling.
        password = "🔒" * 40 + "1a"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_returns_false_for_malformed_hash(self):
        # A corrupt stored hash must fail closed, not raise.
        assert verify_password("anything 1", "not-a-bcrypt-hash") is False
        assert verify_password("anything 1", "") is False

    def test_hash_is_bcrypt_formatted(self):
        assert hash_password("correct horse 9").startswith("$2b$12$")
