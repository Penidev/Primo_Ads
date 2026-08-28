"""Background tasks for video generation and stitching.

Long-running work never blocks an HTTP request (Requirement 14.1). The API
submits scenes and returns immediately; these tasks poll the provider, advance
per-scene state, refund permanent failures, and stitch the master file once every
scene is ready.

Celery is synchronous, so each task drives the async services through
`asyncio.run` on its own event loop and its own database session.
"""

import asyncio
import uuid

from celery import shared_task
from sqlalchemy import select

from app.adapters.factory import get_storage_adapter
from app.db.session import AsyncSessionLocal
from app.models import Project, Scene
from app.services.stitch_service import StitchError, StitchService
from app.services.video_service import VideoService

POLL_RETRY_SECONDS = 15
MAX_POLL_ATTEMPTS = 80  # ~20 minutes at 15s intervals


async def _refresh(project_id: uuid.UUID) -> tuple[str, bool]:
    """Advance a project's scenes. Returns (status, all_scenes_complete)."""
    async with AsyncSessionLocal() as db:
        project = await db.scalar(select(Project).where(Project.id == project_id))
        if project is None:
            return "missing", False

        scenes = await VideoService(db).refresh_project(project)
        statuses = {s.generation_status for s in scenes}
        settled = not ({"pending", "generating"} & statuses)
        return project.status, settled and statuses == {"completed"}


@shared_task(
    bind=True,
    name="video.poll_project",
    max_retries=MAX_POLL_ATTEMPTS,
    default_retry_delay=POLL_RETRY_SECONDS,
)
def poll_project(self, project_id: str):  # noqa: ANN001, ANN201
    """Poll a project's scenes until they all settle, then queue stitching."""
    _status, ready_to_stitch = asyncio.run(_refresh(uuid.UUID(project_id)))

    if ready_to_stitch:
        stitch_project.delay(project_id)
        return {"project_id": project_id, "stitching": True}

    # Still in flight: retry. Exhausting retries leaves per-scene state intact
    # (failed scenes have already been refunded by the service layer).
    raise self.retry(countdown=POLL_RETRY_SECONDS)


async def _stitch(project_id: uuid.UUID) -> str | None:
    async with AsyncSessionLocal() as db:
        project = await db.scalar(select(Project).where(Project.id == project_id))
        if project is None:
            return None
        service = StitchService(db, get_storage_adapter())
        return await service.stitch_project(project)


@shared_task(bind=True, name="video.stitch_project", max_retries=2, default_retry_delay=30)
def stitch_project(self, project_id: str):  # noqa: ANN001, ANN201
    """Normalise and concatenate finished scenes into the master video."""
    try:
        key = asyncio.run(_stitch(uuid.UUID(project_id)))
    except StitchError as exc:
        # Missing or still-generating scenes: not worth retrying blindly.
        return {"project_id": project_id, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - transient infra/ffmpeg failure
        raise self.retry(exc=exc) from exc

    return {"project_id": project_id, "final_video_key": key}


async def _reset_stuck(project_id: uuid.UUID) -> int:
    """Resubmit scenes the provider dropped, so a project can self-heal."""
    async with AsyncSessionLocal() as db:
        project = await db.scalar(select(Project).where(Project.id == project_id))
        if project is None or not project.selected_model_slug:
            return 0

        pending = list(
            await db.scalars(
                select(Scene).where(
                    Scene.project_id == project_id,
                    Scene.generation_status == "pending",
                )
            )
        )
        if not pending:
            return 0

        # start_generation only charges for scenes that are not complete, and
        # retries of an already-charged scene are covered by the original charge.
        await VideoService(db).start_generation(project, project.selected_model_slug)
        return len(pending)


@shared_task(name="video.retry_pending_scenes")
def retry_pending_scenes(project_id: str):  # noqa: ANN201
    """Resubmit scenes left pending after a transient provider failure."""
    count = asyncio.run(_reset_stuck(uuid.UUID(project_id)))
    return {"project_id": project_id, "resubmitted": count}
