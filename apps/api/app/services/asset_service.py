"""Scene asset pre-generation and review.

Why this exists: video models produce inconsistent results when they must imagine
brand elements. Generating precise reference frames first, then feeding them into
video generation, materially improves brand and character consistency
(ARCHITECTURE.md Module 4).

Credits are charged per generated image, priced from `action_pricing`. User
uploads are free.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.image.base import ImageAdapter, ImageGenConfig, ImageProviderError
from app.adapters.storage.base import StorageAdapter
from app.models import Project, Scene, SceneAsset
from app.services.credit_service import CreditService
from app.utils.image_prompt_builder import (
    build_asset_prompt,
    build_character_sheet_prompt,
)
from app.utils.uploads import build_asset_key, sanitise_image

logger = logging.getLogger(__name__)

ASSET_ACTION_KEY = "asset_image"
CHARACTER_ASSET_TYPE = "character"


class AssetError(Exception):
    """User-safe asset failure."""


class AssetService:
    """Storage-only operations plus image generation when an adapter is supplied."""

    def __init__(
        self,
        storage: StorageAdapter,
        db: AsyncSession | None = None,
        image: ImageAdapter | None = None,
    ):
        self.storage = storage
        self.db = db
        self.image = image

    # ---------------- uploads (no charge) ----------------

    async def upload_brand_asset(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        raw: bytes,
    ) -> dict[str, str]:
        """Validate, re-encode and store an image. Returns key + signed URL."""
        clean = sanitise_image(raw)
        key = build_asset_key(user_id, project_id, clean.extension)
        await self.storage.upload(key, clean.data, clean.content_type)
        url = await self.storage.signed_url(key)
        return {"key": key, "url": url, "content_type": clean.content_type}

    async def refresh_url(self, key: str, expires_seconds: int = 3600) -> str:
        return await self.storage.signed_url(key, expires_seconds=expires_seconds)

    async def attach_user_upload(
        self,
        scene: Scene,
        raw: bytes,
        user_id: uuid.UUID,
        description: str | None = None,
    ) -> SceneAsset:
        """Replace or add a scene asset from a user's own image. Never charged."""
        self._require_db()
        stored = await self.upload_brand_asset(user_id, scene.project_id, raw)
        asset = SceneAsset(
            scene_id=scene.id,
            asset_type="user_upload",
            description=description or "Uploaded by user",
            image_url=stored["key"],
            status="user_uploaded",
        )
        self.db.add(asset)  # type: ignore[union-attr]
        await self.db.commit()  # type: ignore[union-attr]
        await self.db.refresh(asset)  # type: ignore[union-attr]
        return asset

    # ---------------- planning ----------------

    def _require_db(self) -> AsyncSession:
        if self.db is None:
            raise AssetError("Asset service was constructed without a database session.")
        return self.db

    def _require_image(self) -> ImageAdapter:
        if self.image is None:
            raise AssetError("Image generation is not configured on this environment.")
        return self.image

    @staticmethod
    def _brand(project: Project) -> dict[str, Any]:
        brand = (project.brief or {}).get("brand") or {}
        return brand if isinstance(brand, dict) else {}

    @staticmethod
    def _aspect_ratio(project: Project) -> str:
        campaign = (project.brief or {}).get("campaign") or {}
        ratio = campaign.get("format")
        return ratio if ratio in ("9:16", "16:9", "1:1") else "9:16"

    async def plan_assets(self, project: Project) -> list[SceneAsset]:
        """Create pending asset rows from the script's `image_gen_needed` entries.

        Idempotent: scenes that already have planned assets are left untouched, so
        calling this again after a partial run does not duplicate work.
        """
        db = self._require_db()
        scenes = list(
            await db.scalars(
                select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_number)
            )
        )
        if not scenes:
            raise AssetError("Generate a script before planning assets.")

        existing_scene_ids = {
            row.scene_id
            for row in await db.scalars(
                select(SceneAsset).where(
                    SceneAsset.scene_id.in_([s.id for s in scenes]),
                    SceneAsset.asset_type != "user_upload",
                )
            )
        }

        created: list[SceneAsset] = []
        for scene in scenes:
            if scene.id in existing_scene_ids:
                continue
            requirements = (scene.script_data or {}).get("image_gen_needed") or []
            if not isinstance(requirements, list):
                continue
            for requirement in requirements:
                if not isinstance(requirement, dict):
                    continue
                description = str(requirement.get("description") or "").strip()
                if not description:
                    continue
                asset = SceneAsset(
                    scene_id=scene.id,
                    asset_type=str(requirement.get("asset_type") or "background")[:50],
                    description=description[:2000],
                    status="pending",
                )
                db.add(asset)
                created.append(asset)

        await db.flush()
        return created

    async def pending_count(self, project: Project) -> int:
        db = self._require_db()
        scene_ids = [
            s.id for s in await db.scalars(select(Scene).where(Scene.project_id == project.id))
        ]
        if not scene_ids:
            return 0
        rows = await db.scalars(
            select(SceneAsset).where(
                SceneAsset.scene_id.in_(scene_ids), SceneAsset.status == "pending"
            )
        )
        return len(list(rows))

    async def cost_preview(self, project: Project) -> dict[str, float]:
        db = self._require_db()
        credits = CreditService(db)
        pending = await self.pending_count(project)
        required = (
            await credits.action_cost(ASSET_ACTION_KEY, quantity=pending) if pending else Decimal(0)
        )
        balance = await credits.get_balance(project.user_id)
        return {
            "pending_assets": pending,
            "credits_required": float(required),
            "estimated_usd": float(await credits.quote_usd(required)),
            "current_balance": float(balance),
            "sufficient": balance >= required,
        }

    # ---------------- generation ----------------

    async def generate_pending(self, project: Project) -> list[SceneAsset]:
        """Charge for and generate every pending asset on this project."""
        db = self._require_db()
        image = self._require_image()
        credits = CreditService(db)

        await self.plan_assets(project)
        await db.commit()

        scene_ids = [
            s.id for s in await db.scalars(select(Scene).where(Scene.project_id == project.id))
        ]
        pending = list(
            await db.scalars(
                select(SceneAsset).where(
                    SceneAsset.scene_id.in_(scene_ids), SceneAsset.status == "pending"
                )
            )
        )
        if not pending:
            return []

        cost = await credits.action_cost(ASSET_ACTION_KEY, quantity=len(pending))
        await credits.deduct(
            project.user_id,
            cost,
            transaction_type="asset_generation",
            reference_type="project",
            reference_id=str(project.id),
            description=f"Asset pre-generation ({len(pending)} images)",
        )
        project.total_credits_spent = Decimal(str(project.total_credits_spent)) + cost

        brand = self._brand(project)
        colours = brand.get("colors") if isinstance(brand.get("colors"), list) else None
        tones = brand.get("voice_tone") if isinstance(brand.get("voice_tone"), list) else None
        aspect_ratio = self._aspect_ratio(project)

        # Character assets reuse one sheet so the same person appears throughout.
        character_reference = await self._ensure_character_sheet(
            project, pending, colours, tones, aspect_ratio
        )

        failed_credits = Decimal(0)
        for asset in pending:
            is_character = (asset.asset_type or "").lower() == CHARACTER_ASSET_TYPE
            prompt = build_asset_prompt(
                asset.description or "",
                asset_type=asset.asset_type,
                brand_colours=colours,
                brand_name=brand.get("name"),
                voice_tone=tones,
            )
            references: list[str] = []
            if is_character and character_reference:
                references = [character_reference]

            asset.prompt_used = prompt
            try:
                result = await image.generate(
                    ImageGenConfig(
                        prompt=prompt,
                        aspect_ratio=aspect_ratio,
                        reference_image_urls=references,
                    )
                )
                asset.image_url = result.image_url
                asset.status = "generated"
            except ImageProviderError:
                asset.status = "failed"
                failed_credits += await credits.action_cost(ASSET_ACTION_KEY, quantity=1)

        # Refund only the images that could not be produced.
        if failed_credits > 0:
            await credits.refund(
                project.user_id,
                failed_credits,
                reference_type="project",
                reference_id=str(project.id),
                description="Refund for failed asset generation",
            )
            project.total_credits_spent = max(
                Decimal("0"), Decimal(str(project.total_credits_spent)) - failed_credits
            )

        await db.commit()
        return pending

    async def _ensure_character_sheet(
        self,
        project: Project,
        pending: list[SceneAsset],
        colours: list[str] | None,
        tones: list[str] | None,
        aspect_ratio: str,
    ) -> str | None:
        """Generate one shared character reference, if any scene needs a person.

        Prefers a user-uploaded character image when one exists, so real people
        supplied by the brand are always used ahead of a synthetic one.
        """
        character_assets = [
            a for a in pending if (a.asset_type or "").lower() == CHARACTER_ASSET_TYPE
        ]
        if not character_assets:
            return None

        brand = self._brand(project)
        uploaded = brand.get("character_keys")
        if isinstance(uploaded, list) and uploaded:
            first = uploaded[0]
            if isinstance(first, str) and first:
                try:
                    return await self.storage.signed_url(first)
                except Exception:
                    # Falls through to generating a synthetic sheet. Logged because
                    # the user supplied a character and we are silently not using
                    # it, which is surprising behaviour worth being able to trace.
                    logger.warning(
                        "Could not sign uploaded character key for project %s; "
                        "generating a synthetic character sheet instead.",
                        project.id,
                        exc_info=True,
                    )

        image = self._require_image()
        prompt = build_character_sheet_prompt(
            character_assets[0].description or "A person featured in the advertisement",
            brand_colours=colours,
            voice_tone=tones,
        )
        try:
            result = await image.generate(ImageGenConfig(prompt=prompt, aspect_ratio=aspect_ratio))
        except ImageProviderError:
            return None
        return result.image_url

    # ---------------- review ----------------

    async def regenerate(self, project: Project, asset: SceneAsset) -> SceneAsset:
        """Re-run a single asset, charging for one image."""
        db = self._require_db()
        image = self._require_image()
        credits = CreditService(db)

        cost = await credits.action_cost(ASSET_ACTION_KEY, quantity=1)
        await credits.deduct(
            project.user_id,
            cost,
            transaction_type="asset_generation",
            reference_type="scene_asset",
            reference_id=str(asset.id),
            description="Asset regeneration",
        )
        project.total_credits_spent = Decimal(str(project.total_credits_spent)) + cost

        brand = self._brand(project)
        colours = brand.get("colors") if isinstance(brand.get("colors"), list) else None
        tones = brand.get("voice_tone") if isinstance(brand.get("voice_tone"), list) else None

        prompt = build_asset_prompt(
            asset.description or "",
            asset_type=asset.asset_type,
            brand_colours=colours,
            brand_name=brand.get("name"),
            voice_tone=tones,
        )
        asset.prompt_used = prompt
        try:
            result = await image.generate(
                ImageGenConfig(prompt=prompt, aspect_ratio=self._aspect_ratio(project))
            )
            asset.image_url = result.image_url
            asset.status = "generated"
        except ImageProviderError:
            asset.status = "failed"
            await credits.refund(
                project.user_id,
                cost,
                reference_type="scene_asset",
                reference_id=str(asset.id),
                description="Refund for failed asset regeneration",
            )
            project.total_credits_spent = max(
                Decimal("0"), Decimal(str(project.total_credits_spent)) - cost
            )

        await db.commit()
        await db.refresh(asset)
        return asset

    async def set_status(self, asset: SceneAsset, status: str) -> SceneAsset:
        db = self._require_db()
        asset.status = status
        await db.commit()
        await db.refresh(asset)
        return asset

    async def approve_all(self, project: Project) -> int:
        """Approve generated assets and attach them as video references."""
        db = self._require_db()
        scenes = list(await db.scalars(select(Scene).where(Scene.project_id == project.id)))
        approved = 0
        for scene in scenes:
            assets = list(
                await db.scalars(select(SceneAsset).where(SceneAsset.scene_id == scene.id))
            )
            usable: list[str] = []
            for asset in assets:
                if asset.status in ("generated", "approved", "user_uploaded") and asset.image_url:
                    if asset.status == "generated":
                        asset.status = "approved"
                        approved += 1
                    usable.append(asset.image_url)
            if usable:
                scene.reference_image_urls = usable

        if project.status == "scripted":
            project.status = "assets_ready"
        await db.commit()
        return approved
