"""Stripe adapter.

Webhook verification implements Stripe's signed-payload scheme directly
(`t=<timestamp>,v1=<signature>` over `"{t}.{raw_body}"`) so the backend does not
depend on the Stripe SDK for the security-critical path. A timestamp tolerance
blocks replay of captured events.
"""

import hashlib
import hmac
import json
import time

import httpx

from app.adapters.payments.base import (
    CheckoutRequest,
    CheckoutSession,
    PaymentAdapter,
    PaymentError,
    WebhookEvent,
    WebhookVerificationError,
)
from app.config import settings

API_ROOT = "https://api.stripe.com/v1"
REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
SIGNATURE_TOLERANCE_SECONDS = 300

_SUCCESS_EVENTS = {"checkout.session.completed", "invoice.paid"}


class StripeAdapter(PaymentAdapter):
    gateway_name = "stripe"

    def __init__(self) -> None:
        if not settings.stripe_secret_key:
            raise PaymentError("Stripe is not configured.")
        self._secret = settings.stripe_secret_key

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        # Stripe expects form-encoded input and integer minor units.
        form = {
            "mode": "payment",
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "client_reference_id": request.reference,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(
                int(round(request.amount_usd * 100))
            ),
            "line_items[0][price_data][product_data][name]": request.description,
            "metadata[reference]": request.reference,
        }
        for key, value in request.metadata.items():
            form[f"metadata[{key}]"] = str(value)

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{API_ROOT}/checkout/sessions",
                    data=form,
                    headers={
                        "Authorization": f"Bearer {self._secret}",
                        # Prevents duplicate sessions if we retry.
                        "Idempotency-Key": request.reference,
                    },
                )
        except httpx.HTTPError as exc:
            raise PaymentError("Could not reach Stripe.") from exc

        if response.status_code >= 400:
            raise PaymentError(f"Stripe rejected the request ({response.status_code}).")

        data = response.json()
        session_id, url = data.get("id"), data.get("url")
        if not session_id or not url:
            raise PaymentError("Stripe returned an incomplete session.")
        return CheckoutSession(gateway=self.gateway_name, session_id=session_id, checkout_url=url)

    @staticmethod
    def _parse_signature_header(header: str) -> tuple[int | None, list[str]]:
        timestamp: int | None = None
        signatures: list[str] = []
        for part in header.split(","):
            key, _, value = part.strip().partition("=")
            if key == "t" and value.isdigit():
                timestamp = int(value)
            elif key == "v1":
                signatures.append(value)
        return timestamp, signatures

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> WebhookEvent:
        secret = settings.stripe_webhook_secret
        if not secret:
            raise WebhookVerificationError("Stripe webhook secret is not configured.")

        header = headers.get("stripe-signature") or ""
        timestamp, signatures = self._parse_signature_header(header)
        if timestamp is None or not signatures:
            raise WebhookVerificationError("Stripe signature header was malformed.")

        if abs(time.time() - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
            raise WebhookVerificationError("Stripe webhook timestamp is outside tolerance.")

        signed_payload = f"{timestamp}.".encode() + raw_body
        expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(candidate, expected) for candidate in signatures):
            raise WebhookVerificationError("Stripe webhook signature mismatch.")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise WebhookVerificationError("Stripe webhook body was not valid JSON.") from exc

        event_type = str(payload.get("type", ""))
        obj = ((payload.get("data") or {}).get("object")) or {}
        metadata = obj.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        amount_total = obj.get("amount_total")
        amount_usd = float(amount_total) / 100 if isinstance(amount_total, (int, float)) else None

        event_id = str(payload.get("id") or "")
        if not event_id:
            raise WebhookVerificationError("Stripe webhook had no event id.")

        return WebhookEvent(
            gateway=self.gateway_name,
            event_id=event_id,
            event_type=event_type,
            is_payment_success=event_type in _SUCCESS_EVENTS,
            amount_usd=amount_usd,
            reference=metadata.get("reference") or obj.get("client_reference_id"),
            metadata={str(k): str(v) for k, v in metadata.items()},
        )
