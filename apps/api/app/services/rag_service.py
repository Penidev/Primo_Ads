"""Retrieval of ad blueprints used as in-context examples for scriptwriting.

Only approved blueprints are ever retrieved (Requirement 6.4). Retrieval starts
with structured filters (category / industry / format) and, when an embedding is
available, ranks by vector similarity via pgvector.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdBlueprint

DEFAULT_LIMIT = 4


class RagService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve(
        self,
        *,
        ad_category: str | None = None,
        industry: str | None = None,
        video_format: str | None = None,
        query_embedding: list[float] | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[AdBlueprint]:
        stmt = select(AdBlueprint).where(AdBlueprint.is_approved.is_(True))

        if ad_category:
            stmt = stmt.where(AdBlueprint.ad_category == ad_category)
        if industry:
            stmt = stmt.where(AdBlueprint.industry == industry)
        if video_format:
            stmt = stmt.where(AdBlueprint.format == video_format)

        if query_embedding is not None:
            # Cosine distance ordering (pgvector); nearest first.
            stmt = stmt.order_by(AdBlueprint.embedding.cosine_distance(query_embedding))
        else:
            stmt = stmt.order_by(AdBlueprint.effectiveness_score.desc().nullslast())

        rows = await self.db.scalars(stmt.limit(limit))
        results = list(rows)

        if results or not (ad_category or industry or video_format):
            return results

        # Nothing matched the narrow filters: fall back to category-only, then
        # to the highest-rated approved blueprints, so generation still gets
        # useful structural examples.
        if ad_category:
            relaxed = await self.db.scalars(
                select(AdBlueprint)
                .where(
                    AdBlueprint.is_approved.is_(True),
                    AdBlueprint.ad_category == ad_category,
                )
                .order_by(AdBlueprint.effectiveness_score.desc().nullslast())
                .limit(limit)
            )
            results = list(relaxed)
        if not results:
            broad = await self.db.scalars(
                select(AdBlueprint)
                .where(AdBlueprint.is_approved.is_(True))
                .order_by(AdBlueprint.effectiveness_score.desc().nullslast())
                .limit(limit)
            )
            results = list(broad)
        return results

    @staticmethod
    def to_example(blueprint: AdBlueprint) -> dict[str, Any]:
        """Compact, structure-only representation for the prompt context.

        Deliberately excludes `source_video_url` and any verbatim copy so the
        model learns structure, not reproducible content (Requirement 6.5).
        """
        return {
            "ad_category": blueprint.ad_category,
            "industry": blueprint.industry,
            "psychological_triggers": blueprint.psychological_triggers or [],
            "structural_arc": blueprint.structural_arc or {},
            "hook_style": blueprint.hook_style,
            "pacing": blueprint.pacing,
            "duration_seconds": blueprint.duration_seconds,
            "camera_techniques": blueprint.camera_techniques or [],
        }
