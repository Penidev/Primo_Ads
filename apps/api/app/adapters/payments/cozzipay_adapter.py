"""Cozzipay adapter.

Implements the requirements from docs.cozzipay.com:
* Write requests are signed with HMAC-SHA512 over the raw JSON body, plus a
  fresh timestamp and a unique nonce (replay protection).
* An idempotency key is sent on money-moving calls.
* Inbound webhooks are verified as sha256=HMAC-SHA256(raw_body, webhook_secret)
  using constant-time comparison.
"""

import hashlib
import hmac
import json
import time
import uuid

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

API_ROOT = "https://api.cozzipay.com/v1"
REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Events that mean money actually arrived.
_SUCCESS_EVENTS = {"checkout.completed", "subscription.renewed"}


class CozzipayAdapter(PaymentAdapter):
    gateway_name = "cozzipay"

    def __init__(self) -> None:
        if not settings.cozzipay_secret_key:
            raise PaymentError("Cozzipay is not configured.")
        self._secret = settings.cozzipay_secret_key

    def _signed_headers(self, body: str, idempotency_key: str) -> dict[str, str]:
        signature = hmac.new(self._secret.encode(), body.encode(), hashlib.sha512).hexdigest()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._secret}",
            "X-Signature": signature,
            "X-Timestamp": str(int(time.time())),
            "X-Nonce": str(uuid.uuid4()),
            "X-Idempotency-Key": idempotency_key,
        }

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        payload = {
            "amount": round(request.amount_usd, 2),
            "currency": "USD",
            "description": request.description,
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "metadata": {**request.metadata, "reference": request.reference},
        }
        # Sign exactly the bytes we send: no re-serialisation anywhere.
        body = json.dumps(payload)

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{API_ROOT}/checkout/sessions",
                    content=body,
                    headers=self._signed_headers(body, request.reference),
                )
        except httpx.HTTPError as exc:
            raise PaymentError("Could not reach Cozzipay.") from exc

        if response.status_code >= 400:
            raise PaymentError(f"Cozzipay rejected the request ({response.status_code}).")

        data = response.json()
        session_id = data.get("session_id")
        checkout_url = data.get("checkout_url")
        if not session_id or not checkout_url:
            raise PaymentError("Cozzipay returned an incomplete session.")
        return CheckoutSession(
            gateway=self.gateway_name, session_id=session_id, checkout_url=checkout_url
        )

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> WebhookEvent:
        secret = settings.cozzipay_webhook_secret
        if not secret:
            raise WebhookVerificationError("Cozzipay webhook secret is not configured.")

        provided = headers.get("x-cozzipay-signature") or ""
        expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(provided, expected):
            raise WebhookVerificationError("Cozzipay webhook signature mismatch.")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise WebhookVerificationError("Cozzipay webhook body was not valid JSON.") from exc

        event_type = str(payload.get("event", ""))
        data = payload.get("data") or {}
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        event_id = str(payload.get("webhook_id") or data.get("session_id") or "")
        if not event_id:
            raise WebhookVerificationError("Cozzipay webhook had no identifier.")

        amount = data.get("amount")
        return WebhookEvent(
            gateway=self.gateway_name,
            event_id=event_id,
            event_type=event_type,
            is_payment_success=event_type in _SUCCESS_EVENTS,
            amount_usd=float(amount) if isinstance(amount, (int, float)) else None,
            reference=metadata.get("reference"),
            metadata={str(k): str(v) for k, v in metadata.items()},
        )
