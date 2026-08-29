"""Admin endpoints: pricing, model registry, users, credits, feature flags.

Every route requires an admin account (`get_current_admin`, which returns 404 to
non-admins so the surface is not discoverable). All pricing lives in the database
and takes effect immediately, with no deployment (Requirement 11).
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_admin
from app.models import (
    ActionPricing,
    AuditLog,
    CreditPackage,
    FeatureFlag,
    PlatformSetting,
    SecurityEvent,
    SubscriptionPlan,
    User,
    VideoModel,
)
from app.schemas.admin import (
    ActionPricingAdmin,
    ActionPricingUpdate,
    AlertEntry,
    AuditEntry,
    CreditRatioUpdate,
    FeatureFlagAdmin,
    FeatureFlagUpdate,
    ManualCreditGrant,
    ModelMargin,
    PackageUpsert,
    PlanUpsert,
    SecurityEventEntry,
    UserAdmin,
    UserStatusUpdate,
    VideoModelAdmin,
    VideoModelCreate,
    VideoModelUpdate,
)
from app.services.audit_service import (
    ACTION_CREDITS_GRANTED,
    ACTION_FLAG_TOGGLED,
    ACTION_MODEL_CREATED,
    ACTION_MODEL_UPDATED,
    ACTION_PRICING_ACTION_CHANGED,
    ACTION_PRICING_RATIO_CHANGED,
    ACTION_USER_STATUS_CHANGED,
    AuditService,
)
from app.services.credit_service import (
    CREDIT_USD_RATIO_KEY,
    CreditService,
    PricingNotConfiguredError,
)
from app.services.monitoring_service import MonitoringService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
)

# Reference scene length used for margin analysis.
MARGIN_SCENE_SECONDS = 6


# ---------------- credit-to-USD ratio ----------------


@router.get("/pricing/ratio")
async def get_credit_ratio(db: AsyncSession = Depends(get_db)) -> dict[str, float]:
    return {"usd_per_credit": float(await CreditService(db).usd_per_credit())}


@router.put("/pricing/ratio")
async def set_credit_ratio(
    body: CreditRatioUpdate,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, float]:
    """Set the global credit value. Applies to all pricing math immediately."""
    setting = await db.scalar(
        select(PlatformSetting).where(PlatformSetting.key == CREDIT_USD_RATIO_KEY)
    )
    previous = None
    if setting is None:
        setting = PlatformSetting(
            key=CREDIT_USD_RATIO_KEY,
            value={"usd_per_credit": body.usd_per_credit},
            description="How much one credit is worth in USD (pricing anchor).",
            updated_by=admin.id,
        )
        db.add(setting)
    else:
        previous = setting.value
        setting.value = {"usd_per_credit": body.usd_per_credit}
        setting.updated_by = admin.id
    await db.commit()

    await AuditService(db).record(
        ACTION_PRICING_RATIO_CHANGED,
        actor=admin,
        target_type="platform_setting",
        target_id=CREDIT_USD_RATIO_KEY,
        detail={"before": previous, "after": {"usd_per_credit": body.usd_per_credit}},
        request=request,
    )
    return {"usd_per_credit": body.usd_per_credit}


# ---------------- per-action pricing ----------------


@router.get("/pricing/actions", response_model=list[ActionPricingAdmin])
async def list_action_pricing(db: AsyncSession = Depends(get_db)) -> list[ActionPricing]:
    rows = await db.scalars(select(ActionPricing).order_by(ActionPricing.action_key))
    return list(rows)


@router.patch("/pricing/actions/{action_key}", response_model=ActionPricingAdmin)
async def update_action_pricing(
    action_key: str,
    body: ActionPricingUpdate,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ActionPricing:
    pricing = await db.scalar(select(ActionPricing).where(ActionPricing.action_key == action_key))
    if pricing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown action")

    before = {
        "base_credits": float(pricing.base_credits),
        "is_enabled": pricing.is_enabled,
    }
    data = body.model_dump(exclude_unset=True)
    if "base_credits" in data and data["base_credits"] is not None:
        pricing.base_credits = Decimal(str(data.pop("base_credits")))
    for field, value in data.items():
        if value is not None:
            setattr(pricing, field, value)
    pricing.updated_by = admin.id
    await db.commit()
    await db.refresh(pricing)

    await AuditService(db).record(
        ACTION_PRICING_ACTION_CHANGED,
        actor=admin,
        target_type="action_pricing",
        target_id=action_key,
        detail={
            "before": before,
            "after": {
                "base_credits": float(pricing.base_credits),
                "is_enabled": pricing.is_enabled,
            },
        },
        request=request,
    )
    return pricing


# ---------------- video model registry ----------------


@router.get("/models", response_model=list[VideoModelAdmin])
async def list_models_admin(db: AsyncSession = Depends(get_db)) -> list[VideoModel]:
    rows = await db.scalars(select(VideoModel).order_by(VideoModel.slug))
    return list(rows)


@router.post("/models", response_model=VideoModelAdmin, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: VideoModelCreate,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> VideoModel:
    """Register a new engine. No deployment needed for supported providers."""
    from app.adapters.video.registry import available_providers

    if body.provider not in available_providers():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"No adapter for provider '{body.provider}'. Available: "
            f"{', '.join(available_providers())}.",
        )
    if await db.scalar(select(VideoModel).where(VideoModel.slug == body.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A model with that slug exists")

    model = VideoModel(
        **body.model_dump(exclude={"cost_per_second_usd", "credit_multiplier"}),
        cost_per_second_usd=Decimal(str(body.cost_per_second_usd)),
        credit_multiplier=Decimal(str(body.credit_multiplier)),
        is_enabled=True,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    await AuditService(db).record(
        ACTION_MODEL_CREATED,
        actor=admin,
        target_type="video_model",
        target_id=body.slug,
        detail={"provider": body.provider, "model_id": body.model_id},
        request=request,
    )
    return model


@router.patch("/models/{slug}", response_model=VideoModelAdmin)
async def update_model(
    slug: str,
    body: VideoModelUpdate,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> VideoModel:
    """Reprice or enable/disable an engine; takes effect immediately."""
    model = await db.scalar(select(VideoModel).where(VideoModel.slug == slug))
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown model")

    before = {
        "credit_multiplier": float(model.credit_multiplier),
        "is_enabled": model.is_enabled,
    }
    data = body.model_dump(exclude_unset=True)
    for decimal_field in ("credit_multiplier", "cost_per_second_usd"):
        if data.get(decimal_field) is not None:
            setattr(model, decimal_field, Decimal(str(data.pop(decimal_field))))
    for field, value in data.items():
        if value is not None:
            setattr(model, field, value)
    await db.commit()
    await db.refresh(model)

    await AuditService(db).record(
        ACTION_MODEL_UPDATED,
        actor=admin,
        target_type="video_model",
        target_id=slug,
        detail={
            "before": before,
            "after": {
                "credit_multiplier": float(model.credit_multiplier),
                "is_enabled": model.is_enabled,
            },
        },
        request=request,
    )
    return model


@router.get("/models/margins", response_model=list[ModelMargin])
async def model_margins(
    seconds_per_scene: int = Query(default=MARGIN_SCENE_SECONDS, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
) -> list[ModelMargin]:
    """Live margin per engine: provider cost vs. what a user pays per scene."""
    service = CreditService(db)
    usd_per_credit = await service.usd_per_credit()
    try:
        base_credits = await service.action_cost("video_scene")
    except PricingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    results: list[ModelMargin] = []
    for model in await db.scalars(select(VideoModel).order_by(VideoModel.slug)):
        cost_per_second = Decimal(str(model.cost_per_second_usd or 0))
        platform_cost = cost_per_second * Decimal(seconds_per_scene)
        user_price = base_credits * Decimal(str(model.credit_multiplier)) * usd_per_credit
        margin = user_price - platform_cost
        percent = float(margin / user_price * 100) if user_price > 0 else None

        results.append(
            ModelMargin(
                slug=model.slug,
                display_name=model.display_name,
                seconds_per_scene=seconds_per_scene,
                platform_cost_usd=float(round(platform_cost, 4)),
                user_price_usd=float(round(user_price, 2)),
                margin_usd=float(round(margin, 2)),
                margin_percent=round(percent, 1) if percent is not None else None,
                is_profitable=margin > 0,
            )
        )
    return results


# ---------------- plans & packages ----------------


@router.put("/plans/{slug}")
async def upsert_plan(
    slug: str, body: PlanUpsert, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if slug != body.slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Slug mismatch")

    plan = await db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.slug == slug))
    payload = body.model_dump(exclude={"price_usd"})
    if plan is None:
        plan = SubscriptionPlan(**payload, price_usd=Decimal(str(body.price_usd)))
        db.add(plan)
    else:
        for field, value in payload.items():
            setattr(plan, field, value)
        plan.price_usd = Decimal(str(body.price_usd))
    await db.commit()
    return {"slug": slug, "status": "saved"}


@router.put("/packages/{slug}")
async def upsert_package(
    slug: str, body: PackageUpsert, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    if slug != body.slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Slug mismatch")

    package = await db.scalar(select(CreditPackage).where(CreditPackage.slug == slug))
    payload = body.model_dump(exclude={"price_usd"})
    if package is None:
        package = CreditPackage(**payload, price_usd=Decimal(str(body.price_usd)))
        db.add(package)
    else:
        for field, value in payload.items():
            setattr(package, field, value)
        package.price_usd = Decimal(str(body.price_usd))
    await db.commit()
    return {"slug": slug, "status": "saved"}


# ---------------- users & credits ----------------


@router.get("/users", response_model=list[UserAdmin])
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    rows = await db.scalars(select(User).order_by(User.created_at.desc()).limit(limit))
    return list(rows)


@router.patch("/users/{user_id}/status", response_model=UserAdmin)
async def set_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    if user_id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "You cannot change your own account status."
        )
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    before = user.is_active
    user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)

    await AuditService(db).record(
        ACTION_USER_STATUS_CHANGED,
        actor=admin,
        target_type="user",
        target_id=str(user_id),
        detail={"before": before, "after": body.is_active},
        request=request,
    )
    return user


@router.post("/users/{user_id}/credits")
async def grant_credits(
    user_id: uuid.UUID,
    body: ManualCreditGrant,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, float]:
    """Manually grant credits. Recorded in the ledger and the audit log."""
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    balance = await CreditService(db).grant(
        user_id,
        Decimal(str(body.amount)),
        transaction_type="admin_grant",
        reference_type="admin",
        reference_id=str(admin.id),
        description=f"Manual grant by admin: {body.reason}",
    )

    await AuditService(db).record(
        ACTION_CREDITS_GRANTED,
        actor=admin,
        target_type="user",
        target_id=str(user_id),
        detail={
            "amount": body.amount,
            "reason": body.reason,
            "balance_after": float(balance),
        },
        request=request,
    )
    return {"balance_credits": float(balance)}


# ---------------- feature flags ----------------


@router.get("/features", response_model=list[FeatureFlagAdmin])
async def list_flags(db: AsyncSession = Depends(get_db)) -> list[FeatureFlag]:
    rows = await db.scalars(select(FeatureFlag).order_by(FeatureFlag.key))
    return list(rows)


@router.patch("/features/{key}", response_model=FeatureFlagAdmin)
async def update_flag(
    key: str,
    body: FeatureFlagUpdate,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> FeatureFlag:
    """Toggle a capability globally or per tier/user without deployment."""
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
    if flag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown flag")

    before = flag.is_enabled
    flag.is_enabled = body.is_enabled
    if body.applies_to is not None:
        flag.applies_to = body.applies_to
    await db.commit()
    await db.refresh(flag)

    await AuditService(db).record(
        ACTION_FLAG_TOGGLED,
        actor=admin,
        target_type="feature_flag",
        target_id=key,
        detail={"before": before, "after": body.is_enabled},
        request=request,
    )
    return flag


# ---------------- audit trail & security telemetry ----------------


@router.get("/audit-log", response_model=list[AuditEntry])
async def list_audit_log(
    action: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    """Immutable record of administrative actions."""
    return await AuditService(db).list_entries(action=action, limit=limit)


@router.get("/security-events", response_model=list[SecurityEventEntry])
async def list_security_events(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[SecurityEvent]:
    """Recent anomaly signals (failed logins, webhook forgeries, unusual spend)."""
    return await MonitoringService(db).recent_events(limit=limit)


@router.get("/alerts", response_model=list[AlertEntry])
async def list_alerts(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Alert thresholds currently breached."""
    return await MonitoringService(db).active_alerts()
