"""Mock video adapter.

Reproduces the live provider's asynchronous contract exactly:

* `submit` returns a job handle immediately,
* the first `check_status` call reports QUEUED, the next RUNNING, then COMPLETED.

That staged progression matters — it means the polling loop, the per-scene status
transitions, and the progress UI are all genuinely exercised rather than
short-circuited by an instantly-complete job.

When ffmpeg is available a real MP4 is produced, so FFmpeg stitching downstream
operates on genuine media. Without ffmpeg it falls back to a marker file and the
pipeline still completes.

Failure injection: include ``__FAIL_VIDEO__`` in the prompt to make the job
report FAILED, exercising retry and per-scene refund.
"""

import asyncio
import hashlib
import shutil
import uuid
from pathlib import Path

from app.adapters.video.base import (
    JobState,
    VideoGenConfig,
    VideoGenStatus,
    VideoGenSubmission,
    VideoModelAdapter,
    VideoProviderError,
)
from app.config import settings

FAIL_TOKEN = "__FAIL_VIDEO__"  # noqa: S105 - a marker string, not a credential

_DIMENSIONS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}

# Poll count at which a job transitions to completed, so callers observe progress.
_POLLS_BEFORE_COMPLETE = 2

# Module-level so job state survives across the separate adapter instances the
# API creates per request, mirroring how a real provider holds job state.
_JOBS: dict[str, dict] = {}


class MockVideoAdapter(VideoModelAdapter):
    provider_name = "mock"

    def _media_dir(self) -> Path:
        path = Path(settings.mock_media_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def submit(self, config: VideoGenConfig) -> VideoGenSubmission:
        job_id = f"mock_{uuid.uuid4().hex}"
        _JOBS[job_id] = {
            "polls": 0,
            "config": config,
            "should_fail": FAIL_TOKEN in config.prompt,
        }
        return VideoGenSubmission(provider=self.provider_name, provider_job_id=job_id)

    async def check_status(self, provider_job_id: str) -> VideoGenStatus:
        job = _JOBS.get(provider_job_id)
        if job is None:
            return VideoGenStatus(state=JobState.FAILED, error_message="Unknown mock job id.")

        job["polls"] += 1

        if job["should_fail"]:
            return VideoGenStatus(
                state=JobState.FAILED,
                error_message="Mock video failure requested via test token.",
            )

        if job["polls"] == 1:
            return VideoGenStatus(state=JobState.QUEUED)
        if job["polls"] < _POLLS_BEFORE_COMPLETE + 1:
            return VideoGenStatus(state=JobState.RUNNING)

        url = await self._render(job["config"])
        return VideoGenStatus(state=JobState.COMPLETED, video_url=url)

    async def _render(self, config: VideoGenConfig) -> str:
        """Produce a real clip when ffmpeg is present, else a marker file."""
        destination = self._media_dir() / f"mock-video-{uuid.uuid4().hex}.mp4"
        width, height = _DIMENSIONS.get(config.aspect_ratio, _DIMENSIONS["9:16"])
        duration = max(1, min(config.duration_seconds or 6, 30))

        if shutil.which("ffmpeg") is None:
            destination.write_bytes(b"mock-video-placeholder")
            return destination.as_uri()

        # Deterministic colour per prompt so scenes are visually distinguishable.
        seed = int(hashlib.sha256(config.prompt.encode()).hexdigest()[:6], 16)
        colour = f"0x{seed:06X}"

        command = [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={colour}:s={width}x{height}:d={duration}:r=24",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=48000:d={duration}",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(destination),
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except TimeoutError as exc:
            process.kill()
            raise VideoProviderError("Mock render timed out.") from exc

        if process.returncode != 0:
            detail = (stderr or b"").decode("utf-8", "replace")[:200]
            raise VideoProviderError(f"Mock render failed: {detail}")

        return destination.as_uri()


def reset_jobs() -> None:
    """Clear in-memory job state. Used between tests."""
    _JOBS.clear()
