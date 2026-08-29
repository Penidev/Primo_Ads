"""Assembles completed scene clips into the final advertisement.

Downloads each scene clip into an isolated temporary directory, normalises and
concatenates them with FFmpeg, then uploads the master file and thumbnail to
object storage. The temp directory is always removed, so provider URLs and
intermediate media never linger on the worker.
"""

import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage.base import StorageAdapter
from app.config import settings
from app.models import Project, Scene
from app.utils.ffmpeg import FFmpegError, stitch_clips

DOWNLOAD_TIMEOUT = httpx.Timeout(300.0, connect=15.0)
MAX_CLIP_BYTES = 200 * 1024 * 1024  # 200 MB per scene clip
REMOTE_SCHEMES = {"http", "https"}


class StitchError(Exception):
    """User-safe stitching failure."""


def _local_source(url: str) -> Path | None:
    """Resolve a `file://` clip URL to a path inside the media sandbox.

    Returns None for ordinary http(s) URLs, which are fetched over the network.

    The mock video adapter and the local storage adapter both hand back
    `file://` URIs, so without this branch the stitching path is unreachable in
    any environment that is not backed by S3 — which is exactly how it stayed
    unexercised despite the unit tests passing.

    Confined to `mock_media_dir` deliberately. A clip URL originates from a
    provider response, which is untrusted input; honouring an arbitrary local
    path would turn a compromised or misbehaving provider into an
    arbitrary-file-read primitive.
    """
    parsed = urlparse(url)
    if parsed.scheme in REMOTE_SCHEMES:
        return None
    if parsed.scheme != "file":
        raise StitchError("A generated clip has an unsupported URL scheme.")

    raw = unquote(parsed.path)
    # A Windows file URI carries its drive as `/C:/...`; drop the leading slash.
    if len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]

    candidate = Path(raw).resolve()
    root = Path(settings.mock_media_dir).resolve()
    if not candidate.is_relative_to(root):
        raise StitchError("A generated clip resolved outside the media directory.")
    return candidate


class StitchService:
    def __init__(self, db: AsyncSession, storage: StorageAdapter):
        self.db = db
        self.storage = storage

    @staticmethod
    def _aspect_ratio(project: Project) -> str:
        campaign = (project.brief or {}).get("campaign") or {}
        ratio = campaign.get("format")
        return ratio if ratio in ("9:16", "16:9", "1:1") else "9:16"

    async def _completed_scenes(self, project_id: uuid.UUID) -> list[Scene]:
        rows = await self.db.scalars(
            select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_number)
        )
        return [s for s in rows if s.generation_status == "completed" and s.video_url]

    async def _download(self, url: str, destination: Path) -> None:
        local = _local_source(url)
        if local is not None:
            if not local.is_file():
                raise StitchError("A generated clip could not be found.")
            if local.stat().st_size > MAX_CLIP_BYTES:
                raise StitchError("A generated clip exceeded the size limit.")
            shutil.copyfile(local, destination)
            return

        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise StitchError("A generated clip could not be downloaded.")
                written = 0
                with destination.open("wb") as handle:
                    async for chunk in response.aiter_bytes(chunk_size=1 << 20):
                        written += len(chunk)
                        if written > MAX_CLIP_BYTES:
                            raise StitchError("A generated clip exceeded the size limit.")
                        handle.write(chunk)

    async def stitch_project(self, project: Project) -> str:
        """Produce the final video and return its storage key."""
        scenes = await self._completed_scenes(project.id)
        if not scenes:
            raise StitchError("No completed scenes to assemble yet.")

        expected = list(await self.db.scalars(select(Scene).where(Scene.project_id == project.id)))
        if len(scenes) != len(expected):
            raise StitchError("Some scenes are still generating or have failed.")

        with tempfile.TemporaryDirectory(prefix="primo-stitch-") as tmp:
            work_dir = Path(tmp)
            clips: list[Path] = []
            for scene in scenes:
                # Sequential, predictable filenames inside the sandbox: the
                # provider URL never influences the local path.
                target = work_dir / f"scene_{scene.scene_number:03d}.mp4"
                await self._download(str(scene.video_url), target)
                clips.append(target)

            try:
                result = await stitch_clips(
                    clips, work_dir, aspect_ratio=self._aspect_ratio(project)
                )
            except FFmpegError as exc:
                raise StitchError(str(exc)) from exc

            video_key = f"projects/{project.user_id}/{project.id}/final/{uuid.uuid4()}.mp4"
            thumb_key = f"projects/{project.user_id}/{project.id}/final/{uuid.uuid4()}.jpg"

            await self.storage.upload(video_key, result.output_path.read_bytes(), "video/mp4")
            if result.thumbnail_path.exists():
                await self.storage.upload(
                    thumb_key, result.thumbnail_path.read_bytes(), "image/jpeg"
                )

        project.final_video_url = video_key
        project.status = "completed"
        await self.db.commit()
        return video_key

    async def signed_download_url(self, project: Project, expires_seconds: int = 3600) -> str:
        if not project.final_video_url:
            raise StitchError("This project has no finished video yet.")
        return await self.storage.signed_url(
            project.final_video_url, expires_seconds=expires_seconds
        )
