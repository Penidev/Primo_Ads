"""Seed baseline data: admin user, pricing config, and the video model registry.

Idempotent — safe to run repeatedly. Run via: `make seed`
or `python -m app.scripts.seed` inside the api container.

The admin password is read from the ADMIN_SEED_PASSWORD env var; if unset a
random one is generated and printed once (never hardcode credentials).
"""

import asyncio
import os
import secrets

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import (
    ActionPricing,
    CreditPackage,
    FeatureFlag,
    PlatformSetting,
    SubscriptionPlan,
    User,
    VideoModel,
    Wallet,
)
from app.utils.security import hash_password

ADMIN_EMAIL = os.environ.get("ADMIN_SEED_EMAIL", "[email protected]")


async def _seed_admin(session) -> None:
    existing = await session.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if existing:
        print(f"[skip] admin user {ADMIN_EMAIL} already exists")
        return

    password = os.environ.get("ADMIN_SEED_PASSWORD") or secrets.token_urlsafe(16)
    admin = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(password),
        full_name="Primo Admin",
        is_admin=True,
        is_active=True,
        email_verified=True,
        onboarding_completed=True,
    )
    session.add(admin)
    await session.flush()  # get admin.id
    session.add(Wallet(user_id=admin.id, balance_credits=0))
    print(f"[create] admin user {ADMIN_EMAIL}")
    if not os.environ.get("ADMIN_SEED_PASSWORD"):
        print(f"[IMPORTANT] generated admin password (shown once): {password}")


async def _seed_platform_settings(session) -> None:
    rows = {
        "credit_usd_ratio": {
            "value": {"usd_per_credit": 0.50},
            "description": "How much one credit is worth in USD (pricing anchor).",
        },
    }
    for key, data in rows.items():
        existing = await session.scalar(select(PlatformSetting).where(PlatformSetting.key == key))
        if existing:
            continue
        session.add(PlatformSetting(key=key, value=data["value"], description=data["description"]))
        print(f"[create] platform_setting {key}")


async def _seed_action_pricing(session) -> None:
    actions = [
        ("script_generation", "Script & Direction", 2, "per_generation"),
        ("asset_image", "Asset Image", 0.5, "per_image"),
        ("video_scene", "Video Scene", 5, "per_scene"),
        ("scene_reroll", "Scene Re-roll", 5, "per_scene"),
        ("stitching", "Video Stitch & Export", 0, "per_generation"),
        ("script_export", "Script PDF/DOCX Export", 0, "per_generation"),
    ]
    for key, name, credits, unit in actions:
        existing = await session.scalar(
            select(ActionPricing).where(ActionPricing.action_key == key)
        )
        if existing:
            continue
        session.add(
            ActionPricing(action_key=key, display_name=name, base_credits=credits, unit=unit)
        )
        print(f"[create] action_pricing {key}")


async def _seed_plans(session) -> None:
    plans = [
        ("starter", "Starter", 29, 50, 1),
        ("growth", "Growth", 79, 200, 2),
        ("agency", "Agency", 199, 600, 3),
    ]
    for slug, name, price, credits, order in plans:
        existing = await session.scalar(
            select(SubscriptionPlan).where(SubscriptionPlan.slug == slug)
        )
        if existing:
            continue
        session.add(
            SubscriptionPlan(
                slug=slug,
                display_name=name,
                price_usd=price,
                credits_per_month=credits,
                sort_order=order,
            )
        )
        print(f"[create] subscription_plan {slug}")

    packages = [
        ("topup_small", "Starter Top-up", 10, 20, 0, 1),
        ("topup_medium", "Creator Pack", 49, 120, 0, 2),
        ("topup_large", "Studio Pack", 99, 300, 0, 3),
    ]
    for slug, name, price, credits, bonus, order in packages:
        existing = await session.scalar(select(CreditPackage).where(CreditPackage.slug == slug))
        if existing:
            continue
        session.add(
            CreditPackage(
                slug=slug,
                display_name=name,
                price_usd=price,
                credits=credits,
                bonus_credits=bonus,
                sort_order=order,
            )
        )
        print(f"[create] credit_package {slug}")


async def _seed_feature_flags(session) -> None:
    flags = [
        ("video_generation_enabled", "Master switch for video generation"),
        ("asset_pregeneration_enabled", "Master switch for asset pre-generation"),
        ("payments_enabled", "Master switch for payment/checkout flows"),
    ]
    for key, desc in flags:
        existing = await session.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
        if existing:
            continue
        session.add(FeatureFlag(key=key, description=desc, is_enabled=True))
        print(f"[create] feature_flag {key}")


async def _seed_video_models(session) -> None:
    # Launch model registry. Prices are approximate USD/sec; multipliers are the
    # admin-tunable credit rate mapping the user requested (x0.5, x1, x2, ...).
    models = [
        # slug, name, provider, model_id, max_dur, res, ar, audio, imgref, cost, mult, tier
        ("veo-3.1-lite", "Veo 3.1 Lite", "fal", "fal-ai/veo3/lite", 8,
         ["720p"], ["9:16", "16:9", "1:1"], False, True, 0.03, 0.5, "budget"),
        ("veo-3.1", "Veo 3.1", "fal", "fal-ai/veo3", 8,
         ["720p", "1080p", "4k"], ["9:16", "16:9", "1:1"], True, True, 0.20, 1.5, "premium"),
        ("kling-3.0", "Kling 3.0", "fal", "fal-ai/kling-video/v3", 15,
         ["720p", "1080p"], ["9:16", "16:9", "1:1"], True, True, 0.13, 1.0, "standard"),
        ("kling-3.0-turbo", "Kling 3.0 Turbo", "fal", "fal-ai/kling-video/v3/turbo", 15,
         ["720p", "1080p"], ["9:16", "16:9", "1:1"], True, True, 0.11, 1.0, "standard"),
        ("seedance-2.0", "Seedance 2.0", "fal", "fal-ai/bytedance/seedance/v2", 30,
         ["720p", "1080p"], ["9:16", "16:9", "1:1"], True, True, 0.20, 2.0, "premium"),
        ("minimax-hailuo", "MiniMax Hailuo", "fal", "fal-ai/minimax/hailuo", 10,
         ["720p", "1080p", "4k"], ["9:16", "16:9"], True, True, 0.08, 0.8, "standard"),
        ("wan-2.5", "Wan 2.5", "fal", "fal-ai/wan/v2.5", 10,
         ["720p", "1080p"], ["9:16", "16:9", "1:1"], False, True, 0.05, 0.5, "budget"),
    ]
    for (slug, name, provider, model_id, max_dur, res, ar, audio, imgref,
         cost, mult, tier) in models:
        existing = await session.scalar(select(VideoModel).where(VideoModel.slug == slug))
        if existing:
            continue
        session.add(
            VideoModel(
                slug=slug,
                display_name=name,
                provider=provider,
                model_id=model_id,
                max_duration_seconds=max_dur,
                supported_resolutions=res,
                supported_aspect_ratios=ar,
                supports_audio=audio,
                supports_image_reference=imgref,
                cost_per_second_usd=cost,
                credit_multiplier=mult,
                quality_tier=tier,
                is_enabled=True,
            )
        )
        print(f"[create] video_model {slug}")


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await _seed_admin(session)
        await _seed_platform_settings(session)
        await _seed_action_pricing(session)
        await _seed_plans(session)
        await _seed_feature_flags(session)
        await _seed_video_models(session)
        await session.commit()
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
