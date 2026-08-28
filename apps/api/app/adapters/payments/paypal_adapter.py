"""PayPal adapter.

PayPal webhook signatures cannot be verified locally with an HMAC: the correct
approach is to call PayPal's own verification endpoint with the transmission
headers, which is what `verify_webhook_async` does. The synchronous
`verify_webhook` therefore refuses to assert authenticity, so no code path can
accidentally trust an unverified PayPal event.
"""

import json

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

LIVE_ROOT = "https://api-m.paypal.com"
REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_SUCCESS_EVENTS = {
    "CHECKOUT.ORDER.APPROVED",
    "PAYMENT.CAPTURE.COMPLETED",
}

_REQUIRED_HEADERS = (
    "paypal-auth-algo",
    "paypal-cert-url",
    "paypal-transmission-id",
    "paypal-transmission-sig",
    "paypal-transmission-time",
)


class PayPalAdapter(PaymentAdapter):
    gateway_name = "paypal"

    def __init__(self) -> None:
        if not (settings.paypal_client_id and settings.paypal_client_secret):
            raise PaymentError("PayPal is not configured.")
        self._client_id = settings.paypal_client_id
        self._client_secret = settings.paypal_client_secret

    async def _access_token(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{LIVE_ROOT}/v1/oauth2/token",
                    data={"grant_type": "client_credentials"},
                    auth=(self._client_id, self._client_secret),
                )
        except httpx.HTTPError as exc:
            raise PaymentError("Could not reach PayPal.") from exc

        if response.status_code >= 400:
            raise PaymentError("PayPal authentication failed.")
        token = response.json().get("access_token")
        if not token:
            raise PaymentError("PayPal did not return an access token.")
        return str(token)

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        token = await self._access_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": request.reference,
                    "description": request.description[:127],
                    "custom_id": request.reference,
                    "amount": {
                        "currency_code": "USD",
                        "value": f"{request.amount_usd:.2f}",
                    },
                }
            ],
            "application_context": {
                "return_url": request.success_url,
                "cancel_url": request.cancel_url,
                "user_action": "PAY_NOW",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{LIVE_ROOT}/v2/checkout/orders",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "PayPal-Request-Id": request.reference,
                    },
                )
        except httpx.HTTPError as exc:
            raise PaymentError("Could not reach PayPal.") from exc

        if response.status_code >= 400:
            raise PaymentError(f"PayPal rejected the request ({response.status_code}).")

        data = response.json()
        order_id = data.get("id")
        approve_url = next(
            (
                link.get("href")
                for link in data.get("links", [])
                if link.get("rel") in ("payer-action", "approve")
            ),
            None,
        )
        if not order_id or not approve_url:
            raise PaymentError("PayPal returned an incomplete order.")
        return CheckoutSession(
            gateway=self.gateway_name, session_id=order_id, checkout_url=approve_url
        )

    def verify_webhook(self, raw_body: bytes, headers: dict[str, str]) -> WebhookEvent:
        """Not supported synchronously — PayPal requires a remote verification call."""
        raise WebhookVerificationError(
            "PayPal webhooks must be verified via verify_webhook_async()."
        )

    async def verify_webhook_async(
        self, raw_body: bytes, headers: dict[str, str]
    ) -> WebhookEvent:
        webhook_id = settings.paypal_webhook_id
        if not webhook_id:
            raise WebhookVerificationError("PayPal webhook id is not configured.")

        missing = [name for name in _REQUIRED_HEADERS if not headers.get(name)]
        if missing:
            raise WebhookVerificationError("PayPal transmission headers were incomplete.")

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise WebhookVerificationError("PayPal webhook body was not valid JSON.") from exc

        token = await self._access_token()
        verification = {
            "auth_algo": headers["paypal-auth-algo"],
            "cert_url": headers["paypal-cert-url"],
            "transmission_id": headers["paypal-transmission-id"],
            "transmission_sig": headers["paypal-transmission-sig"],
            "transmission_time": headers["paypal-transmission-time"],
            "webhook_id": webhook_id,
            "webhook_event": payload,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{LIVE_ROOT}/v1/notifications/verify-webhook-signature",
                    json=verification,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            raise WebhookVerificationError("Could not reach PayPal for verification.") from exc

        if response.status_code >= 400:
            raise WebhookVerificationError("PayPal verification call failed.")
        if response.json().get("verification_status") != "SUCCESS":
            raise WebhookVerificationError("PayPal reported an invalid signature.")

        event_type = str(payload.get("event_type", ""))
        resource = payload.get("resource") or {}
        amount_block = resource.get("amount") or {}
        raw_amount = amount_block.get("value")
        try:
            amount_usd = float(raw_amount) if raw_amount is not None else None
        except (TypeError, ValueError):
            amount_usd = None

        event_id = str(payload.get("id") or "")
        if not event_id:
            raise WebhookVerificationError("PayPal webhook had no event id.")

        reference = resource.get("custom_id") or (
            (resource.get("purchase_units") or [{}])[0].get("custom_id")
            if isinstance(resource.get("purchase_units"), list)
            else None
        )

        return WebhookEvent(
            gateway=self.gateway_name,
            event_id=event_id,
            event_type=event_type,
            is_payment_success=event_type in _SUCCESS_EVENTS,
            amount_usd=amount_usd,
            reference=str(reference) if reference else None,
            metadata={},
        )
