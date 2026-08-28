"""Payment orchestration across Stripe, PayPal and Cozzipay.

Fulfilment rules (SECURITY.md §3):
* Credits come from the `credit_purchases` row created *before* checkout, never
  from amounts supplied by the webhook body.
* Every event is recorded in `processed_webhooks`; a duplicate delivery is a
  no-op, so gateway retries cannot double-credit a wallet.
* Nothing is granted unless the adapter verified the signature.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.payments.base import (
    CheckoutRequest,
    CheckoutSession,
    PaymentAdapter,
    PaymentError,
    WebhookEvent,
)
from app.adapters.payments.cozzipay_adapter import CozzipayAdapter
from app.adapters.payments.paypal_adapter import PayPalAdapter
from app.adapters.payments.stripe_adapter import StripeAdapter
from app.config import settings
from app.models import (
    CreditPackage,
    CreditPurchase,
    ProcessedWebhook,
    SubscriptionPlan,
    User,
)
from app.services import analytics_service as analytics
from app.services.credit_service import CreditService

_ADAPTERS: dict[str, type[PaymentAdapter]] = {
    StripeAdapter.gateway_name: StripeAdapter,
    PayPalAdapter.gateway_name: PayPalAdapter,
    CozzipayAdapter.gateway_name: CozzipayAdapter,
}


def get_payment_adapter(gateway: str) -> PaymentAdapter:
    adapter_cls = _ADAPTERS.get((gateway or "").lower())
    if adapter_cls is None:
        raise PaymentError(f"Unsupported payment gateway '{gateway}'.")
    return adapter_cls()


def available_gateways() -> list[str]:
    """Gateways that are actually configured in this environment."""
    configured: list[str] = []
    if settings.stripe_secret_key:
        configured.append(StripeAdapter.gateway_name)
    if settings.paypal_client_id and settings.paypal_client_secret:
        configured.append(PayPalAdapter.gateway_name)
    if settings.cozzipay_secret_key:
        configured.append(CozzipayAdapter.gateway_name)
    return configured


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.credits = CreditService(db)

    async def start_package_purchase(
        self, user: User, package_slug: str, gateway: str
    ) -> CheckoutSession:
        package = await self.db.scalar(
            select(CreditPackage).where(
                CreditPackage.slug == package_slug,
                CreditPackage.is_enabled.is_(True),
            )
        )
        if package is None:
            raise PaymentError("That credit package is unavailable.")

        total_credits = int(package.credits) + int(package.bonus_credits or 0)
        return await self._start(
            user=user,
            gateway=gateway,
            amount_usd=float(package.price_usd),
            credits=total_credits,
            description=f"{package.display_name or package.slug} — {total_credits} credits",
            package_slug=package.slug,
            plan_slug=None,
        )

    async def start_plan_purchase(
        self, user: User, plan_slug: str, gateway: str
    ) -> CheckoutSession:
        plan = await self.db.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.slug == plan_slug,
                SubscriptionPlan.is_enabled.is_(True),
            )
        )
        if plan is None:
            raise PaymentError("That plan is unavailable.")

        return await self._start(
            user=user,
            gateway=gateway,
            amount_usd=float(plan.price_usd),
            credits=int(plan.credits_per_month),
            description=f"{plan.display_name or plan.slug} — {plan.credits_per_month} credits",
            package_slug=None,
            plan_slug=plan.slug,
        )

    async def _start(
        self,
        *,
        user: User,
        gateway: str,
        amount_usd: float,
        credits: int,
        description: str,
        package_slug: str | None,
        plan_slug: str | None,
    ) -> CheckoutSession:
        adapter = get_payment_adapter(gateway)
        reference = f"pur_{uuid.uuid4().hex}"

        # Record the intent first: fulfilment reads credits from here, not the webhook.
        purchase = CreditPurchase(
            user_id=user.id,
            reference=reference,
            gateway=adapter.gateway_name,
            package_slug=package_slug,
            plan_slug=plan_slug,
            amount_usd=Decimal(str(round(amount_usd, 2))),
            credits=credits,
            status="pending",
        )
        self.db.add(purchase)
        await self.db.flush()

        session = await adapter.create_checkout(
            CheckoutRequest(
                amount_usd=amount_usd,
                description=description,
                reference=reference,
                success_url=f"{settings.frontend_url}/dashboard/billing?purchase={reference}",
                cancel_url=f"{settings.frontend_url}/dashboard/billing?cancelled=1",
                metadata={"user_id": str(user.id), "reference": reference},
            )
        )
        purchase.gateway_session_id = session.session_id
        await self.db.commit()
        return session

    async def fulfil(self, event: WebhookEvent) -> bool:
        """Grant credits for a verified event. Returns True when credits moved."""
        # Idempotency gate: insert-or-skip on (gateway, event_id).
        marker = ProcessedWebhook(
            gateway=event.gateway,
            event_id=event.event_id,
            event_type=event.event_type,
        )
        self.db.add(marker)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            return False  # already handled

        if not event.is_payment_success or not event.reference:
            await self.db.commit()
            return False

        purchase = await self.db.scalar(
            select(CreditPurchase)
            .where(CreditPurchase.reference == event.reference)
            .with_for_update()
        )
        if purchase is None or purchase.status == "completed":
            await self.db.commit()
            return False

        purchase.status = "completed"
        purchase.fulfilled_at = datetime.now(UTC)
        await self.db.flush()

        await self.credits.grant(
            purchase.user_id,
            Decimal(purchase.credits),
            transaction_type="purchase",
            reference_type=f"{event.gateway}_purchase",
            reference_id=purchase.reference,
            description=f"Credit purchase via {event.gateway}",
            count_as_purchase=True,
        )

        await analytics.capture(
            analytics.EVENT_CREDITS_PURCHASED,
            distinct_id=str(purchase.user_id),
            properties={
                "gateway": event.gateway,
                "credits": purchase.credits,
                "amount_usd": float(purchase.amount_usd),
                "package_slug": purchase.package_slug,
                "plan_slug": purchase.plan_slug,
            },
        )
        return True
