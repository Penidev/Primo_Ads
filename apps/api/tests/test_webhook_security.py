"""Webhook signature verification tests (SECURITY.md §3).

These are the guards that stop a forged request from minting credits.
"""

import hashlib
import hmac
import json
import time

import pytest

from app.adapters.payments.base import WebhookVerificationError
from app.adapters.payments.cozzipay_adapter import CozzipayAdapter
from app.adapters.payments.stripe_adapter import StripeAdapter

COZZI_SECRET = "test_cozzipay_webhook_secret"  # noqa: S105 - test fixture
STRIPE_SECRET = "whsec_test_stripe_secret"  # noqa: S105 - test fixture


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    """Point the adapters at deterministic test secrets."""
    from app.config import settings

    monkeypatch.setattr(settings, "cozzipay_secret_key", "czp_test_sk_x", raising=False)
    monkeypatch.setattr(settings, "cozzipay_webhook_secret", COZZI_SECRET, raising=False)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(settings, "stripe_webhook_secret", STRIPE_SECRET, raising=False)


# --------------------------- Cozzipay ---------------------------


def _cozzi_body(reference: str = "pur_abc123", event: str = "checkout.completed") -> bytes:
    return json.dumps(
        {
            "event": event,
            "webhook_id": "wh_test_1",
            "data": {
                "session_id": "cs_test_1",
                "amount": 49.0,
                "currency": "USD",
                "metadata": {"reference": reference, "user_id": "u1"},
            },
        }
    ).encode()


def _cozzi_signature(body: bytes, secret: str = COZZI_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestCozzipayVerification:
    def test_accepts_correct_signature(self):
        body = _cozzi_body()
        event = CozzipayAdapter().verify_webhook(
            body, {"x-cozzipay-signature": _cozzi_signature(body)}
        )
        assert event.is_payment_success is True
        assert event.reference == "pur_abc123"
        assert event.event_id == "wh_test_1"

    def test_rejects_missing_signature(self):
        with pytest.raises(WebhookVerificationError):
            CozzipayAdapter().verify_webhook(_cozzi_body(), {})

    def test_rejects_wrong_signature(self):
        with pytest.raises(WebhookVerificationError):
            CozzipayAdapter().verify_webhook(
                _cozzi_body(), {"x-cozzipay-signature": "sha256=" + "0" * 64}
            )

    def test_rejects_signature_from_another_secret(self):
        body = _cozzi_body()
        forged = _cozzi_signature(body, secret="wrong-test-secret")
        with pytest.raises(WebhookVerificationError):
            CozzipayAdapter().verify_webhook(body, {"x-cozzipay-signature": forged})

    def test_rejects_tampered_body(self):
        """A signature valid for one body must not validate a modified body."""
        original = _cozzi_body()
        signature = _cozzi_signature(original)
        tampered = original.replace(b'"amount": 49.0', b'"amount": 9999.0')
        with pytest.raises(WebhookVerificationError):
            CozzipayAdapter().verify_webhook(tampered, {"x-cozzipay-signature": signature})

    def test_rejects_malformed_json(self):
        body = b"not json at all"
        with pytest.raises(WebhookVerificationError):
            CozzipayAdapter().verify_webhook(body, {"x-cozzipay-signature": _cozzi_signature(body)})

    def test_non_success_event_is_not_marked_as_payment(self):
        body = _cozzi_body(event="checkout.expired")
        event = CozzipayAdapter().verify_webhook(
            body, {"x-cozzipay-signature": _cozzi_signature(body)}
        )
        assert event.is_payment_success is False

    def test_subscription_renewal_counts_as_payment(self):
        body = _cozzi_body(event="subscription.renewed")
        event = CozzipayAdapter().verify_webhook(
            body, {"x-cozzipay-signature": _cozzi_signature(body)}
        )
        assert event.is_payment_success is True

    def test_missing_webhook_secret_refuses_verification(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "cozzipay_webhook_secret", None, raising=False)
        body = _cozzi_body()
        with pytest.raises(WebhookVerificationError):
            CozzipayAdapter().verify_webhook(body, {"x-cozzipay-signature": _cozzi_signature(body)})


# --------------------------- Stripe ---------------------------


def _stripe_body(reference: str = "pur_xyz789", event: str = "checkout.session.completed") -> bytes:
    return json.dumps(
        {
            "id": "evt_test_1",
            "type": event,
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "amount_total": 4900,
                    "client_reference_id": reference,
                    "metadata": {"reference": reference},
                }
            },
        }
    ).encode()


def _stripe_header(body: bytes, timestamp: int | None = None, secret: str = STRIPE_SECRET) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    signed = f"{ts}.".encode() + body
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={signature}"


class TestStripeVerification:
    def test_accepts_correct_signature(self):
        body = _stripe_body()
        event = StripeAdapter().verify_webhook(body, {"stripe-signature": _stripe_header(body)})
        assert event.is_payment_success is True
        assert event.reference == "pur_xyz789"
        assert event.amount_usd == 49.0

    def test_rejects_missing_header(self):
        with pytest.raises(WebhookVerificationError):
            StripeAdapter().verify_webhook(_stripe_body(), {})

    def test_rejects_malformed_header(self):
        with pytest.raises(WebhookVerificationError):
            StripeAdapter().verify_webhook(_stripe_body(), {"stripe-signature": "garbage"})

    def test_rejects_wrong_secret(self):
        body = _stripe_body()
        forged = _stripe_header(body, secret="whsec_wrong_test_value")
        with pytest.raises(WebhookVerificationError):
            StripeAdapter().verify_webhook(body, {"stripe-signature": forged})

    def test_rejects_replayed_old_timestamp(self):
        """Captured events cannot be replayed once outside the tolerance window."""
        body = _stripe_body()
        stale = _stripe_header(body, timestamp=int(time.time()) - 3600)
        with pytest.raises(WebhookVerificationError):
            StripeAdapter().verify_webhook(body, {"stripe-signature": stale})

    def test_rejects_tampered_body(self):
        original = _stripe_body()
        header = _stripe_header(original)
        tampered = original.replace(b'"amount_total": 4900', b'"amount_total": 999999')
        with pytest.raises(WebhookVerificationError):
            StripeAdapter().verify_webhook(tampered, {"stripe-signature": header})

    def test_accepts_multiple_v1_signatures(self):
        """Stripe may send several v1 entries during secret rotation."""
        body = _stripe_body()
        valid = _stripe_header(body)
        ts = valid.split(",")[0].removeprefix("t=")
        real_sig = valid.split("v1=")[1]
        header = f"t={ts},v1={'0' * 64},v1={real_sig}"
        event = StripeAdapter().verify_webhook(body, {"stripe-signature": header})
        assert event.is_payment_success is True

    def test_non_success_event_is_not_marked_as_payment(self):
        body = _stripe_body(event="checkout.session.expired")
        event = StripeAdapter().verify_webhook(body, {"stripe-signature": _stripe_header(body)})
        assert event.is_payment_success is False

    def test_missing_webhook_secret_refuses_verification(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "stripe_webhook_secret", None, raising=False)
        body = _stripe_body()
        with pytest.raises(WebhookVerificationError):
            StripeAdapter().verify_webhook(body, {"stripe-signature": _stripe_header(body)})


class TestPayPalRefusesLocalVerification:
    def test_sync_verify_always_raises(self, monkeypatch):
        """PayPal must be verified remotely; the sync path must never assert trust."""
        from app.adapters.payments.paypal_adapter import PayPalAdapter
        from app.config import settings

        monkeypatch.setattr(settings, "paypal_client_id", "id", raising=False)
        monkeypatch.setattr(settings, "paypal_client_secret", "secret", raising=False)
        with pytest.raises(WebhookVerificationError):
            PayPalAdapter().verify_webhook(b"{}", {})
