"""PII/secret scrubbing tests (SECURITY.md §10).

These guard the promise that error reports and logs never carry credentials or
personal data out of the process.
"""

import pytest

from app.utils.scrubbing import REDACTED, scrub, scrub_text


class TestScrubText:
    @pytest.mark.parametrize(
        "value",
        [
            "contact me at user@example.com",
            "reply to first.last+tag@sub.domain.co.uk please",
        ],
    )
    def test_redacts_emails(self, value):
        assert REDACTED in scrub_text(value)
        assert "@" not in scrub_text(value).replace(REDACTED, "")

    def test_redacts_bearer_tokens(self):
        result = scrub_text("Authorization: Bearer abc123XYZ.def")
        assert REDACTED in result
        assert "abc123XYZ" not in result

    def test_redacts_key_prefixed_credentials(self):
        # Deliberately a test-prefixed value: fixtures should never be shaped
        # like live credentials, or they create false leads during an incident.
        result = scrub_text("Key czp_test_sk_notarealvalue")
        assert "czp_test_sk_notarealvalue" not in result

    def test_redacts_card_numbers(self):
        result = scrub_text("card 4111 1111 1111 1111 on file")
        assert "4111" not in result

    def test_leaves_ordinary_text_intact(self):
        text = "Close-up tracking shot of a thumb over a phone screen."
        assert scrub_text(text) == text


class TestScrubStructures:
    def test_redacts_sensitive_keys(self):
        result = scrub({"password": "hunter2", "api_key": "sk_live_x"})
        assert result["password"] == REDACTED
        assert result["api_key"] == REDACTED

    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "secret",
            "token",
            "api_key",
            "api-key",
            "apikey",
            "Authorization",
            "Cookie",
            "X-Signature",
            "pin",
            "cvv",
        ],
    )
    def test_key_variants_are_caught(self, key):
        assert scrub({key: "value"})[key] == REDACTED

    def test_recurses_into_nested_dicts(self):
        result = scrub({"outer": {"token": "t", "safe": "keep me"}})
        assert result["outer"]["token"] == REDACTED
        assert result["outer"]["safe"] == "keep me"

    def test_recurses_into_lists(self):
        result = scrub({"items": ["user@example.com", "fine"]})
        assert result["items"][0] == REDACTED
        assert result["items"][1] == "fine"

    def test_preserves_non_string_scalars(self):
        result = scrub({"count": 7, "ratio": 1.5, "flag": True, "none": None})
        assert result == {"count": 7, "ratio": 1.5, "flag": True, "none": None}

    def test_guards_against_runaway_depth(self):
        deep: dict = {"a": "x"}
        for _ in range(20):
            deep = {"a": deep}
        # Should terminate and redact past the limit rather than recursing forever.
        assert scrub(deep) is not None

    def test_scrubs_values_even_under_safe_keys(self):
        result = scrub({"description": "reach me at user@example.com"})
        assert REDACTED in result["description"]
