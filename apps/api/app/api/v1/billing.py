"""Wallet, transaction history, and public pricing endpoints.

Pricing is always read from the database so admin changes take effect
immediately with no deployment (Requirement 11.1).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.payments.base import PaymentError
from app.db.session import get_db
from app.deps import get_current_user
from app.models import CreditPackage, CreditTransaction, SubscriptionPlan, User
from app.schemas.billing import (
    CheckoutCreateRequest,
    CheckoutResponse,
    PackagePublic,
    PlanPublic,
    TransactionEntry,
    WalletBalance,
)
from app.services import analytics_service as analytics
from app.services.credit_service import CreditService
from app.services.payment_service import PaymentService, available_gateways
from app.utils.rate_limit import CHECKOUT_LIMIT, rate_limited

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/wallet", response_model=WalletBalance)
async def get_wallet(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WalletBalance:
    service = CreditService(db)
    balance = await service.get_balance(user.id)
    ratio = await service.usd_per_credit()
    return WalletBalance(
        balance_credits=float(balance),
        usd_per_credit=float(ratio),
        estimated_usd_value=float(await service.quote_usd(balance)),
    )


@router.get("/transactions", response_model=list[TransactionEntry])
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CreditTransaction]:
    rows = await db.scalars(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == user.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(limit)
    )
    return list(rows)


@router.get("/plans", response_model=list[PlanPublic])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[SubscriptionPlan]:
    """Public pricing — reflects admin-managed rows immediately."""
    rows = await db.scalars(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_enabled.is_(True))
        .order_by(SubscriptionPlan.sort_order)
    )
    return list(rows)


@router.get("/packages", response_model=list[PackagePublic])
async def list_packages(db: AsyncSession = Depends(get_db)) -> list[CreditPackage]:
    rows = await db.scalars(
        select(CreditPackage)
        .where(CreditPackage.is_enabled.is_(True))
        .order_by(CreditPackage.sort_order)
    )
    return list(rows)


@router.get("/gateways", response_model=list[str])
async def list_gateways(_user: User = Depends(get_current_user)) -> list[str]:
    """Payment gateways configured in this environment."""
    return available_gateways()


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    dependencies=[Depends(rate_limited(CHECKOUT_LIMIT))],
)
async def create_checkout(
    body: CheckoutCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """Open a hosted checkout for a credit package or subscription plan."""
    if bool(body.package_slug) == bool(body.plan_slug):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Specify exactly one of package_slug or plan_slug.",
        )

    service = PaymentService(db)
    try:
        if body.package_slug:
            session = await service.start_package_purchase(user, body.package_slug, body.gateway)
        else:
            session = await service.start_plan_purchase(user, str(body.plan_slug), body.gateway)
    except PaymentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await analytics.capture(
        analytics.EVENT_CHECKOUT_STARTED,
        distinct_id=str(user.id),
        properties={
            "gateway": body.gateway,
            "package_slug": body.package_slug,
            "plan_slug": body.plan_slug,
        },
    )
    return CheckoutResponse(
        gateway=session.gateway,
        session_id=session.session_id,
        checkout_url=session.checkout_url,
    )
