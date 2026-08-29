"""Payment gateway webhook receivers.

Security notes (SECURITY.md §3):
* The RAW request body is used for signature verification — never a re-encoded
  version, which would change bytes and break the signature.
* Verification failures return 400 and grant nothing.
* Handlers always return 200 for *accepted-but-ignored* events so gateways stop
  retrying deliveries we have deliberately skipped.
* These routes are intentionally unauthenticated (gateways cannot log in);
  the signature IS the authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.payments.base import PaymentError, WebhookVerificationError
from app.adapters.payments.cozzipay_adapter import CozzipayAdapter
from app.adapters.payments.paypal_adapter import PayPalAdapter
from app.adapters.payments.stripe_adapter import StripeAdapter
from app.db.session import get_db
from app.services.monitoring_service import (
    EVENT_WEBHOOK_FORGERY,
    SEVERITY_CRITICAL,
    MonitoringService,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _headers(request: Request) -> dict[str, str]:
    return {key.lower(): value for key, value in request.headers.items()}


async def _record_forgery(db: AsyncSession, request: Request, gateway: str) -> None:
    """A failed signature is either a misconfiguration or an attack. Alert on it."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    await MonitoringService(db).record_event(
        EVENT_WEBHOOK_FORGERY,
        severity=SEVERITY_CRITICAL,
        ip_address=ip,
        description=f"Webhook signature verification failed for {gateway}",
        detail={"gateway": gateway},
    )


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    raw = await request.body()
    try:
        event = StripeAdapter().verify_webhook(raw, _headers(request))
    except WebhookVerificationError as exc:
        await _record_forgery(db, request, "stripe")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook") from exc
    except PaymentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook") from exc

    granted = await PaymentService(db).fulfil(event)
    return {"received": True, "credited": granted}


@router.post("/cozzipay", status_code=status.HTTP_200_OK)
async def cozzipay_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    raw = await request.body()
    try:
        event = CozzipayAdapter().verify_webhook(raw, _headers(request))
    except WebhookVerificationError as exc:
        await _record_forgery(db, request, "cozzipay")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook") from exc
    except PaymentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook") from exc

    granted = await PaymentService(db).fulfil(event)
    return {"received": True, "credited": granted}


@router.post("/paypal", status_code=status.HTTP_200_OK)
async def paypal_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    raw = await request.body()
    try:
        # PayPal requires a remote verification round-trip.
        event = await PayPalAdapter().verify_webhook_async(raw, _headers(request))
    except WebhookVerificationError as exc:
        await _record_forgery(db, request, "paypal")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook") from exc
    except PaymentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook") from exc

    granted = await PaymentService(db).fulfil(event)
    return {"received": True, "credited": granted}
