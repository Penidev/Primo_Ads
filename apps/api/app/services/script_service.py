"""Script & direction generation.

Flow (Requirement 5): validate the brief -> retrieve blueprint examples ->
call the LLM with separated system/user content -> strictly validate the JSON
output -> persist script + scene rows -> charge credits.

Credits are charged only after a successful, validated generation, so a provider
failure never costs the user anything.
"""

import json
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm.base import LLMAdapter
from app.models import Project, Scene
from app.schemas.script import GeneratedScript
from app.services.credit_service import CreditService
from app.services.moderation_service import moderate_payload
from app.services.rag_service import RagService
from app.utils.prompt_builder import (
    SYSTEM_INSTRUCTION,
    build_user_content,
    extract_json_object,
)

SCRIPT_ACTION_KEY = "script_generation"
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_DURATION_SECONDS = 30


class ScriptGenerationError(Exception):
    """Raised when generation fails; message is safe to show the user."""


class ContentRefusedError(Exception):
    """Raised when moderation blocks the brief or the generated output."""


class ScriptService:
    def __init__(self, db: AsyncSession, llm: LLMAdapter):
        self.db = db
        self.llm = llm
        self.credits = CreditService(db)
        self.rag = RagService(db)

    # ---------- helpers ----------

    @staticmethod
    def _campaign(brief: dict[str, Any]) -> dict[str, Any]:
        campaign = brief.get("campaign")
        return campaign if isinstance(campaign, dict) else {}

    @staticmethod
    def _brand(brief: dict[str, Any]) -> dict[str, Any]:
        brand = brief.get("brand")
        return brand if isinstance(brand, dict) else {}

    def _resolve_params(
        self,
        brief: dict[str, Any],
        ad_category: str | None,
        aspect_ratio: str | None,
        target_duration: int | None,
    ) -> tuple[str | None, str, int]:
        campaign = self._campaign(brief)
        category = ad_category or campaign.get("ad_category")
        ratio = aspect_ratio or campaign.get("format") or DEFAULT_ASPECT_RATIO
        duration = target_duration or campaign.get("duration_seconds") or DEFAULT_DURATION_SECONDS
        if ratio not in ("9:16", "16:9", "1:1"):
            ratio = DEFAULT_ASPECT_RATIO
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = DEFAULT_DURATION_SECONDS
        duration = max(5, min(duration, 180))
        return (str(category) if category else None), ratio, duration

    async def cost_preview(self, user_id) -> dict[str, float]:
        required = await self.credits.action_cost(SCRIPT_ACTION_KEY)
        balance = await self.credits.get_balance(user_id)
        usd = await self.credits.quote_usd(required)
        return {
            "credits_required": float(required),
            "estimated_usd": float(usd),
            "current_balance": float(balance),
            "sufficient": balance >= required,
        }

    # ---------- generation ----------

    async def generate(
        self,
        project: Project,
        *,
        ad_category: str | None = None,
        aspect_ratio: str | None = None,
        target_duration_seconds: int | None = None,
    ) -> GeneratedScript:
        brief = project.brief or {}
        if not self._brand(brief).get("name"):
            raise ScriptGenerationError(
                "Add your brand details to the brief before generating a script."
            )

        # Screen the brief before spending any provider budget.
        brief_check = moderate_payload(brief)
        if brief_check.blocked:
            raise ContentRefusedError(brief_check.user_message)

        category, ratio, duration = self._resolve_params(
            brief, ad_category, aspect_ratio, target_duration_seconds
        )

        # Confirm the user can pay before spending provider budget.
        required = await self.credits.action_cost(SCRIPT_ACTION_KEY)
        balance = await self.credits.get_balance(project.user_id)
        if balance < required:
            from app.services.credit_service import InsufficientCreditsError

            raise InsufficientCreditsError(required=required, available=balance)

        blueprints = await self.rag.retrieve(
            ad_category=category,
            industry=self._brand(brief).get("industry"),
            video_format=ratio,
        )
        examples = [RagService.to_example(b) for b in blueprints]

        user_content = build_user_content(
            brief,
            examples,
            ad_category=category,
            aspect_ratio=ratio,
            target_duration_seconds=duration,
        )

        raw = await self.llm.generate_json(SYSTEM_INSTRUCTION, user_content)

        # Never trust model output: parse and schema-validate before use.
        try:
            payload = json.loads(extract_json_object(raw))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ScriptGenerationError(
                "The model returned an unreadable response. Please try again."
            ) from exc
        try:
            script = GeneratedScript.model_validate(payload)
        except ValidationError as exc:
            raise ScriptGenerationError(
                "The generated script did not match the expected format. Please try again."
            ) from exc

        # Screen the model's output. Nothing is persisted or charged if it fails.
        output_check = moderate_payload(script.model_dump())
        if output_check.blocked:
            raise ContentRefusedError(
                "The generated script was withheld by our content policy. "
                "Adjust the brief and try again."
            )

        await self._persist(project, script, ratio)

        await self.credits.deduct(
            project.user_id,
            required,
            transaction_type="script_generation",
            reference_type="project",
            reference_id=str(project.id),
            description=f"Script generation for '{script.campaign_title}'",
        )
        project.total_credits_spent = Decimal(str(project.total_credits_spent)) + required
        await self.db.commit()
        return script

    async def _persist(self, project: Project, script: GeneratedScript, aspect_ratio: str) -> None:
        """Store the script on the project and rebuild its scene rows."""
        project.script = script.model_dump()
        project.status = "scripted"
        if not project.title:
            project.title = script.campaign_title

        # Regenerating replaces prior scenes for this project.
        await self.db.execute(delete(Scene).where(Scene.project_id == project.id))

        for scene in script.scenes:
            self.db.add(
                Scene(
                    project_id=project.id,
                    scene_number=scene.scene_number,
                    duration_seconds=scene.duration_seconds,
                    script_data=scene.model_dump(),
                    compiled_prompt=scene.video_prompt,
                    generation_status="pending",
                )
            )
        await self.db.flush()
