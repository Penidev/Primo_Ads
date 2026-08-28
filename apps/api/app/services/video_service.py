"""Video generation orchestration.

Responsibilities:
* Validate the project is ready and the chosen model is enabled.
* Compute and charge the exact credit cost up front (locked at confirmation).
* Compile each scene's prompt with brand consistency and reference images.
* Submit scenes to the provider and track per-scene state so a partially
  generated project can resume without re-charging finished scenes.
* Refund per-scene credits when a scene fails permanently (Requirement 9.4).
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_video_adapter
from app.adapters.video.base import (
    JobState,
    VideoGenConfig,
    VideoProviderError,
)
from app.models import GenerationJob, Project, Scene, VideoModel
from app.services.credit_service import CreditService
from app.utils.video_prompt_compiler import compile_prompt

MAX_ATTEMPTS = 3
VIDEO_ACTION_KEY = "video_scene"
REROLL_ACTION_KEY = "scene_reroll"


class VideoGenerationError(Exception):
    """User-safe orchestration failure."""


class VideoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.credits = CreditService(db)

    # ---------- helpers ----------

    async def _model(self, slug: str) -> VideoModel:
        model = await self.db.scalar(
            select(VideoModel).where(VideoModel.slug == slug, VideoModel.is_enabled.is_(True))
        )
        if model is None:
            raise VideoGenerationError(f"Video model '{slug}' is not available.")
        return model

    async def _scenes(self, project_id: uuid.UUID) -> list[Scene]:
        rows = await self.db.scalars(
            select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_number)
        )
        return list(rows)

    @staticmethod
    def _brand_colours(project: Project) -> list[str]:
        brand = (project.brief or {}).get("brand") or {}
        colours = brand.get("colors")
        return [c for c in colours if isinstance(c, str)] if isinstance(colours, list) else []

    @staticmethod
    def _aspect_ratio(project: Project) -> str:
        campaign = (project.brief or {}).get("campaign") or {}
        ratio = campaign.get("format")
        return ratio if ratio in ("9:16", "16:9", "1:1") else "9:16"

    def _build_config(
        self, project: Project, scene: Scene, model: VideoModel
    ) -> VideoGenConfig:
        aspect_ratio = self._aspect_ratio(project)
        script_data = scene.script_data or {}
        base_prompt = scene.compiled_prompt or script_data.get("video_prompt") or ""
        if not base_prompt:
            raise VideoGenerationError(
                f"Scene {scene.scene_number} has no prompt. Regenerate the script."
            )

        prompt = compile_prompt(
            base_prompt,
            aspect_ratio=aspect_ratio,
            brand_colours=self._brand_colours(project),
            style_notes=script_data.get("color_grading"),
        )

        duration = scene.duration_seconds or 6
        if model.max_duration_seconds:
            duration = min(duration, model.max_duration_seconds)

        resolutions = model.supported_resolutions or ["1080p"]
        resolution = "1080p" if "1080p" in resolutions else resolutions[0]

        references = (
            list(scene.reference_image_urls or [])
            if model.supports_image_reference
            else []
        )

        return VideoGenConfig(
            model_id=model.model_id or model.slug,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration,
            resolution=resolution,
            reference_image_urls=references,
            generate_audio=bool(model.supports_audio),
        )

    # ---------- cost ----------

    async def cost_for_project(self, project: Project, model_slug: str) -> Decimal:
        pending = [
            s
            for s in await self._scenes(project.id)
            if s.generation_status != "completed"
        ]
        if not pending:
            return Decimal(0)
        return await self.credits.video_scene_cost(model_slug, len(pending))

    # ---------- generation ----------

    async def start_generation(self, project: Project, model_slug: str) -> list[Scene]:
        """Charge for and submit every scene that is not already completed."""
        model = await self._model(model_slug)
        scenes = await self._scenes(project.id)
        if not scenes:
            raise VideoGenerationError("Generate a script before creating video.")

        pending = [s for s in scenes if s.generation_status != "completed"]
        if not pending:
            return scenes

        # Charge once, for pending scenes only — resuming never double-charges.
        cost = await self.credits.video_scene_cost(model_slug, len(pending))
        await self.credits.deduct(
            project.user_id,
            cost,
            transaction_type="video_generation",
            reference_type="project",
            reference_id=str(project.id),
            description=f"Video generation ({len(pending)} scenes, {model_slug})",
        )

        project.selected_model_slug = model_slug
        project.status = "generating"
        project.total_credits_spent = Decimal(str(project.total_credits_spent)) + cost

        per_scene = (cost / Decimal(len(pending))).quantize(Decimal("0.01"))
        for scene in pending:
            await self._submit_scene(project, scene, model, per_scene)

        await self.db.commit()
        return await self._scenes(project.id)

    async def _submit_scene(
        self, project: Project, scene: Scene, model: VideoModel, charged: Decimal
    ) -> None:
        adapter = get_video_adapter(model.provider or "")
        config = self._build_config(project, scene, model)

        job = GenerationJob(
            project_id=project.id,
            scene_id=scene.id,
            job_type="video",
            status="queued",
            provider=model.provider,
            credits_charged=charged,
        )
        self.db.add(job)

        scene.model_slug = model.slug
        scene.compiled_prompt = config.prompt
        scene.generation_attempts = (scene.generation_attempts or 0) + 1

        try:
            submission = await adapter.submit(config)
        except VideoProviderError as exc:
            scene.generation_status = "failed"
            scene.error_message = str(exc)
            job.status = "failed"
            job.error_message = str(exc)
            return

        scene.generation_status = "generating"
        scene.generation_job_id = submission.provider_job_id
        scene.error_message = None
        job.status = "processing"
        job.provider_job_id = submission.provider_job_id

    async def poll_scene(self, scene: Scene) -> Scene:
        """Refresh one scene from the provider, handling retries and refunds."""
        if scene.generation_status != "generating" or not scene.generation_job_id:
            return scene

        model = await self.db.scalar(select(VideoModel).where(VideoModel.slug == scene.model_slug))
        if model is None:
            return scene

        adapter = get_video_adapter(model.provider or "")
        try:
            result = await adapter.check_status(scene.generation_job_id)
        except VideoProviderError as exc:
            scene.error_message = str(exc)
            await self.db.commit()
            return scene

        if result.state is JobState.COMPLETED and result.video_url:
            scene.generation_status = "completed"
            scene.video_url = result.video_url
            scene.error_message = None
            await self._close_job(scene, "completed")
        elif result.state is JobState.FAILED:
            if (scene.generation_attempts or 0) >= MAX_ATTEMPTS:
                scene.generation_status = "failed"
                scene.error_message = result.error_message or "Generation failed."
                await self._close_job(scene, "failed")
                await self._refund_scene(scene)
            else:
                # Leave as generating so the worker can resubmit on next pass.
                scene.generation_status = "pending"
                scene.error_message = result.error_message

        await self.db.commit()
        return scene

    async def _close_job(self, scene: Scene, status: str) -> None:
        job = await self.db.scalar(
            select(GenerationJob)
            .where(GenerationJob.scene_id == scene.id, GenerationJob.job_type == "video")
            .order_by(GenerationJob.created_at.desc())
            .limit(1)
        )
        if job is not None:
            job.status = status

    async def _refund_scene(self, scene: Scene) -> None:
        """Return the credits charged for a permanently failed scene."""
        job = await self.db.scalar(
            select(GenerationJob)
            .where(GenerationJob.scene_id == scene.id, GenerationJob.job_type == "video")
            .order_by(GenerationJob.created_at.desc())
            .limit(1)
        )
        if job is None or job.credits_charged is None or job.status == "refunded":
            return
        project = await self.db.scalar(select(Project).where(Project.id == scene.project_id))
        if project is None:
            return

        amount = Decimal(str(job.credits_charged))
        if amount <= 0:
            return
        await self.credits.refund(
            project.user_id,
            amount,
            reference_type="scene",
            reference_id=str(scene.id),
            description=f"Refund for failed scene {scene.scene_number}",
        )
        job.status = "refunded"
        project.total_credits_spent = max(
            Decimal("0"), Decimal(str(project.total_credits_spent)) - amount
        )

    async def reroll_scene(self, project: Project, scene: Scene, model_slug: str | None) -> Scene:
        """Regenerate a single scene, charging only for that scene."""
        slug = model_slug or scene.model_slug or project.selected_model_slug
        if not slug:
            raise VideoGenerationError("Choose a video model first.")
        model = await self._model(slug)

        cost = await self.credits.video_scene_cost(slug, 1, action_key=REROLL_ACTION_KEY)
        await self.credits.deduct(
            project.user_id,
            cost,
            transaction_type="scene_reroll",
            reference_type="scene",
            reference_id=str(scene.id),
            description=f"Re-roll of scene {scene.scene_number}",
        )
        project.total_credits_spent = Decimal(str(project.total_credits_spent)) + cost

        scene.generation_attempts = 0
        scene.video_url = None
        await self._submit_scene(project, scene, model, cost)
        await self.db.commit()
        return scene

    async def refresh_project(self, project: Project) -> list[Scene]:
        """Poll all in-flight scenes and advance the project state."""
        scenes = await self._scenes(project.id)
        for scene in scenes:
            if scene.generation_status == "generating":
                await self.poll_scene(scene)

        scenes = await self._scenes(project.id)
        statuses = {s.generation_status for s in scenes}
        if statuses == {"completed"}:
            project.status = "assets_ready" if project.status == "draft" else "completed"
        elif "failed" in statuses and not {"pending", "generating"} & statuses:
            project.status = "failed"
        await self.db.commit()
        return scenes
