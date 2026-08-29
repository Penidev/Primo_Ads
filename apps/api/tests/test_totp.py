"""TOTP tests, anchored on the RFC 6238 reference vectors.

Implementing TOTP in-house means the reference vectors are the contract; if these
fail, authenticator apps will not work.
"""

import base64

import pytest

from app.utils.totp import (
    generate_code,
    generate_recovery_codes,
    generate_secret,
    provisioning_uri,
    verify_code,
)

# RFC 6238 Appendix B: ASCII seed "12345678901234567890", SHA-1, T0=0, X=30.
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()

RFC_VECTORS_8 = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


class TestRfc6238Vectors:
    @pytest.mark.parametrize("timestamp,expected", RFC_VECTORS_8)
    def test_eight_digit_vectors(self, timestamp, expected):
        assert generate_code(RFC_SECRET, timestamp=timestamp, digits=8) == expected

    @pytest.mark.parametrize("timestamp,expected8", RFC_VECTORS_8)
    def test_six_digit_codes_are_the_final_six(self, timestamp, expected8):
        assert generate_code(RFC_SECRET, timestamp=timestamp, digits=6) == expected8[-6:]


class TestCodeGeneration:
    def test_stable_within_a_window(self):
        assert generate_code(RFC_SECRET, timestamp=30) == generate_code(RFC_SECRET, timestamp=59)

    def test_changes_between_windows(self):
        assert generate_code(RFC_SECRET, timestamp=0) != generate_code(RFC_SECRET, timestamp=30)

    def test_default_length_is_six(self):
        assert len(generate_code(RFC_SECRET)) == 6

    def test_rejects_pre_epoch_timestamp(self):
        with pytest.raises(ValueError):
            generate_code(RFC_SECRET, timestamp=-100)

    def test_rejects_malformed_secret(self):
        with pytest.raises(ValueError):
            generate_code("not!valid!base32")


class TestVerification:
    def test_accepts_current_code(self):
        code = generate_code(RFC_SECRET, timestamp=1111111109)
        assert verify_code(RFC_SECRET, code, timestamp=1111111109) is True

    def test_tolerates_one_window_of_drift(self):
        """Clock skew of ±30s must not lock a user out."""
        code = generate_code(RFC_SECRET, timestamp=1111111109)
        assert verify_code(RFC_SECRET, code, timestamp=1111111109 + 30) is True
        assert verify_code(RFC_SECRET, code, timestamp=1111111109 - 30) is True

    def test_rejects_beyond_drift_window(self):
        code = generate_code(RFC_SECRET, timestamp=1111111109)
        assert verify_code(RFC_SECRET, code, timestamp=1111111109 + 300) is False

    def test_rejects_wrong_code(self):
        assert verify_code(RFC_SECRET, "000000", timestamp=1111111109) is False

    @pytest.mark.parametrize("bad", ["", "1234", "abcdef", "12345678901", "  "])
    def test_rejects_malformed_input(self, bad):
        assert verify_code(RFC_SECRET, bad, timestamp=1111111109) is False

    def test_tolerates_spacing_from_authenticator_apps(self):
        code = generate_code(RFC_SECRET, timestamp=1111111109)
        spaced = f"{code[:3]} {code[3:]}"
        assert verify_code(RFC_SECRET, spaced, timestamp=1111111109) is True

    def test_near_epoch_does_not_crash(self):
        """The negative drift window must be skipped, not packed as unsigned."""
        assert verify_code(RFC_SECRET, "000000", timestamp=1) is False


class TestSecrets:
    def test_secrets_are_unique(self):
        assert generate_secret() != generate_secret()

    def test_secret_is_base32(self):
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=")
        assert set(generate_secret()) <= allowed

    def test_generated_secret_produces_codes(self):
        assert len(generate_code(generate_secret())) == 6


class TestProvisioningUri:
    def test_uses_otpauth_scheme(self):
        assert provisioning_uri("ABC234", "a@b.com").startswith("otpauth://totp/")

    def test_carries_secret_and_issuer(self):
        uri = provisioning_uri("ABC234", "a@b.com")
        assert "secret=ABC234" in uri
        assert "issuer=Primo" in uri

    def test_url_encodes_the_label(self):
        assert "Primo%3Aa%40b.com" in provisioning_uri("ABC234", "a@b.com")


class TestRecoveryCodes:
    def test_default_count(self):
        assert len(generate_recovery_codes()) == 8

    def test_codes_are_unique(self):
        codes = generate_recovery_codes(20)
        assert len(set(codes)) == 20

    def test_custom_count(self):
        assert len(generate_recovery_codes(3)) == 3
