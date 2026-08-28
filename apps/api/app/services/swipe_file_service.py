"""Swipe-file curation: turn reference ads into approved, searchable blueprints.

Flow:
  upload video -> multimodal analysis -> strict schema validation
              -> blueprint row (pending) -> embedding -> curator review -> approved

Only approved blueprints are ever retrieved at script time, so nothing reaches
generation until a human has signed it off (Requirement 6.3, 6.4).
"""

import json
import logging
import uuid
from collections import Counter
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.base import LLMAdapter
from app.adapters.storage.base import StorageAdapter
from app.models import AdBlueprint
from app.schemas.blueprint import AD_CATEGORIES, BlueprintAnalysis
from app.utils.blueprint_prompt import (
    ANALYSIS_SYSTEM_INSTRUCTION,
    build_analysis_request,
    build_embedding_text,
)
from app.utils.prompt_builder import extract_json_object
from app.utils.uploads import build_blueprint_key, validate_video


logger = logging.getLogger(__name__)


class BlueprintAnalysisError(Exception):
    """User-safe analysis failure."""


class SwipeFileService:
    def __init__(
        self,
        db: AsyncSession,
        llm: LLMAdapter,
        storage: StorageAdapter | None = None,
    ):
        self.db = db
        self.llm = llm
        self.storage = storage

    # ---------------- ingestion ----------------

    async def ingest_video(
        self,
        raw: bytes,
        *,
        industry_hint: str | None = None,
        category_hint: str | None = None,
    ) -> AdBlueprint:
        """Validate, analyse, store, and embed a reference ad."""
        mime_type = validate_video(raw)

        analysis = await self._analyze(raw, mime_type, industry_hint, category_hint)
        blueprint = self._to_blueprint(analysis)
        self.db.add(blueprint)
        await self.db.flush()

        # Keep the source only for curator reference; it is never public.
        if self.storage is not None:
            try:
                key = build_blueprint_key(blueprint.id, mime_type)
                await self.storage.upload(key, raw, mime_type)
                blueprint.source_video_url = key
            except Exception:  # noqa: BLE001 - storage is optional for curation
                blueprint.source_video_url = None

        await self._attach_embedding(blueprint)
        await self.db.commit()
        await self.db.refresh(blueprint)
        return blueprint

    async def _analyze(
        self,
        raw: bytes,
        mime_type: str,
        industry_hint: str | None,
        category_hint: str | None,
    ) -> BlueprintAnalysis:
        response = await self.llm.analyze_video_json(
            ANALYSIS_SYSTEM_INSTRUCTION,
            build_analysis_request(industry_hint, category_hint),
            raw,
            mime_type,
        )
        try:
            payload = json.loads(extract_json_object(response))
        except (ValueError, json.JSONDecodeError) as exc:
            raise BlueprintAnalysisError(
                "The analysis response could not be read. Try again."
            ) from exc
        try:
            return BlueprintAnalysis.model_validate(payload)
        except ValidationError as exc:
            raise BlueprintAnalysisError(
                "The analysis did not match the expected format. Try again."
            ) from exc

    @staticmethod
    def _normalise_category(value: str) -> str:
        candidate = (value or "").strip().lower().replace(" ", "-")
        return candidate if candidate in AD_CATEGORIES else "emotional-storytelling"

    def _to_blueprint(self, analysis: BlueprintAnalysis) -> AdBlueprint:
        structural_arc: dict[str, Any] = {
            "beats": [beat.model_dump() for beat in analysis.beats],
            "why_it_works": analysis.why_it_works,
            "reusable_pattern": analysis.reusable_pattern,
        }
        return AdBlueprint(
            title=analysis.suggested_title,
            industry=analysis.industry,
            ad_category=self._normalise_category(analysis.ad_category),
            psychological_triggers=analysis.psychological_triggers or None,
            structural_arc=structural_arc,
            duration_seconds=analysis.duration_seconds,
            format=analysis.format if analysis.format in ("9:16", "16:9", "1:1") else None,
            hook_style=analysis.hook_style,
            pacing=analysis.pacing,
            color_palette=analysis.color_palette or None,
            camera_techniques=analysis.camera_techniques or None,
            full_analysis=build_embedding_text(analysis.model_dump()),
            is_approved=False,  # nothing is usable until a curator approves
        )

    async def _attach_embedding(self, blueprint: AdBlueprint) -> None:
        """Generate the similarity vector; failure leaves filter-only retrieval."""
        if not blueprint.full_analysis:
            return
        try:
            blueprint.embedding = await self.llm.embed(blueprint.full_analysis)
        except Exception:  # noqa: BLE001 - embedding is an enhancement, not a gate
            blueprint.embedding = None

    async def regenerate_embedding(self, blueprint: AdBlueprint) -> bool:
        await self._attach_embedding(blueprint)
        await self.db.commit()
        return blueprint.embedding is not None

    # ---------------- curation ----------------

    async def get(self, blueprint_id: uuid.UUID) -> AdBlueprint | None:
        return await self.db.scalar(select(AdBlueprint).where(AdBlueprint.id == blueprint_id))

    async def list_blueprints(
        self,
        *,
        approved: bool | None = None,
        ad_category: str | None = None,
        limit: int = 50,
    ) -> list[AdBlueprint]:
        stmt = select(AdBlueprint)
        if approved is not None:
            stmt = stmt.where(AdBlueprint.is_approved.is_(approved))
        if ad_category:
            stmt = stmt.where(AdBlueprint.ad_category == ad_category)
        rows = await self.db.scalars(
            stmt.order_by(AdBlueprint.created_at.desc()).limit(limit)
        )
        return list(rows)

    async def apply_edits(self, blueprint: AdBlueprint, data: dict[str, Any]) -> AdBlueprint:
        """Curator corrections. Category is normalised to a known value."""
        if "ad_category" in data and data["ad_category"]:
            data["ad_category"] = self._normalise_category(str(data["ad_category"]))
        for field, value in data.items():
            if value is not None:
                setattr(blueprint, field, value)
        await self.db.commit()
        await self.db.refresh(blueprint)
        return blueprint

    async def set_approval(
        self,
        blueprint: AdBlueprint,
        is_approved: bool,
        effectiveness_score: float | None = None,
    ) -> AdBlueprint:
        blueprint.is_approved = is_approved
        if effectiveness_score is not None:
            blueprint.effectiveness_score = effectiveness_score
        await self.db.commit()
        await self.db.refresh(blueprint)
        return blueprint

    async def delete(self, blueprint: AdBlueprint) -> None:
        if self.storage is not None and blueprint.source_video_url:
            try:
                await self.storage.delete(blueprint.source_video_url)
            except Exception:
                # The row is removed regardless, but a failed delete leaves an
                # orphaned object that costs money and outlives its retention
                # window, so it must be traceable rather than silent.
                logger.warning(
                    "Could not delete stored source video %s for blueprint %s; "
                    "the object may be orphaned.",
                    blueprint.source_video_url,
                    blueprint.id,
                    exc_info=True,
                )
        await self.db.delete(blueprint)
        await self.db.commit()

    # ---------------- coverage ----------------

    async def stats(self) -> dict[str, Any]:
        """Library coverage, so curators can see where examples are missing."""
        total = await self.db.scalar(select(func.count()).select_from(AdBlueprint)) or 0
        approved = (
            await self.db.scalar(
                select(func.count())
                .select_from(AdBlueprint)
                .where(AdBlueprint.is_approved.is_(True))
            )
            or 0
        )
        with_embeddings = (
            await self.db.scalar(
                select(func.count())
                .select_from(AdBlueprint)
                .where(AdBlueprint.embedding.isnot(None))
            )
            or 0
        )

        rows = list(await self.db.scalars(select(AdBlueprint)))
        by_category = Counter(r.ad_category or "uncategorised" for r in rows)
        by_industry = Counter(r.industry or "unspecified" for r in rows)

        return {
            "total": total,
            "approved": approved,
            "pending": total - approved,
            "with_embeddings": with_embeddings,
            "by_category": dict(by_category),
            "by_industry": dict(by_industry),
        }
