"""fal.ai video adapter.

One adapter covers every model hosted on fal (Veo, Kling, Seedance, MiniMax,
Wan and others): the specific model is selected by the registry's `model_id`,
so new fal models need only a database row.
"""

import httpx

from app.adapters.video.base import (
    JobState,
    VideoGenConfig,
    VideoGenStatus,
    VideoGenSubmission,
    VideoModelAdapter,
    VideoProviderError,
)
from app.config import settings

QUEUE_ROOT = "https://queue.fal.run"
REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

# fal queue statuses -> our internal state machine.
_STATE_MAP = {
    "IN_QUEUE": JobState.QUEUED,
    "IN_PROGRESS": JobState.RUNNING,
    "COMPLETED": JobState.COMPLETED,
    "FAILED": JobState.FAILED,
    "ERROR": JobState.FAILED,
}


class FalVideoAdapter(VideoModelAdapter):
    provider_name = "fal"

    def __init__(self) -> None:
        if not settings.fal_key:
            raise VideoProviderError("FAL_KEY is not configured.")
        self._headers = {
            "Authorization": f"Key {settings.fal_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _build_payload(config: VideoGenConfig) -> dict:
        payload: dict = {
            "prompt": config.prompt,
            "aspect_ratio": config.aspect_ratio,
            "duration": config.duration_seconds,
            "resolution": config.resolution,
        }
        if config.generate_audio:
            payload["generate_audio"] = True
        if config.reference_image_urls:
            # First reference acts as the starting frame; the rest are style refs.
            payload["image_url"] = config.reference_image_urls[0]
            if len(config.reference_image_urls) > 1:
                payload["reference_image_urls"] = config.reference_image_urls[1:]
        payload.update(config.extra)
        return payload

    async def submit(self, config: VideoGenConfig) -> VideoGenSubmission:
        url = f"{QUEUE_ROOT}/{config.model_id}"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    url, json=self._build_payload(config), headers=self._headers
                )
        except httpx.HTTPError as exc:
            raise VideoProviderError("Could not reach the video provider.") from exc

        if response.status_code >= 400:
            raise VideoProviderError(
                f"Video provider rejected the request (status {response.status_code})."
            )
        data = response.json()
        request_id = data.get("request_id")
        if not request_id:
            raise VideoProviderError("Video provider did not return a job id.")
        return VideoGenSubmission(provider=self.provider_name, provider_job_id=request_id)

    async def check_status(self, provider_job_id: str) -> VideoGenStatus:
        url = f"{QUEUE_ROOT}/requests/{provider_job_id}/status"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, headers=self._headers)
        except httpx.HTTPError as exc:
            raise VideoProviderError("Could not reach the video provider.") from exc

        if response.status_code >= 400:
            return VideoGenStatus(
                state=JobState.FAILED,
                error_message=f"Status check failed ({response.status_code}).",
            )

        data = response.json()
        state = _STATE_MAP.get(str(data.get("status", "")).upper(), JobState.RUNNING)
        if state is not JobState.COMPLETED:
            return VideoGenStatus(
                state=state,
                error_message=data.get("error") if state is JobState.FAILED else None,
            )
        return VideoGenStatus(state=state, video_url=await self._fetch_result(provider_job_id))

    async def _fetch_result(self, provider_job_id: str) -> str:
        url = f"{QUEUE_ROOT}/requests/{provider_job_id}"
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, headers=self._headers)
        if response.status_code >= 400:
            raise VideoProviderError("Could not retrieve the finished video.")
        data = response.json()
        video = data.get("video") or {}
        video_url = video.get("url") if isinstance(video, dict) else None
        if not video_url:
            raise VideoProviderError("Provider response contained no video URL.")
        return video_url
