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
