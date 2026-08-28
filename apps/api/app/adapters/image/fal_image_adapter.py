"""fal.ai image adapter (Flux by default).

Submits to fal's queue and polls to completion. Images finish in seconds, so a
bounded synchronous poll keeps the calling worker simple; the request runs inside
a Celery task, never inside an HTTP handler.
"""

import asyncio

import httpx

from app.adapters.image.base import (
    ImageAdapter,
    ImageGenConfig,
    ImageGenResult,
    ImageProviderError,
)
from app.config import settings

QUEUE_ROOT = "https://queue.fal.run"
DEFAULT_MODEL_ID = "fal-ai/flux-pro/v1.1"
# Image-to-image endpoint used when references are supplied.
REFERENCE_MODEL_ID = "fal-ai/flux-pro/v1.1/redux"

REQUEST_TIMEOUT = httpx.Timeout(90.0, connect=10.0)
POLL_ATTEMPTS = 40
POLL_SECONDS = 3.0

# fal expects named ratios for Flux.
_RATIO_TO_SIZE = {
    "9:16": "portrait_16_9",
    "16:9": "landscape_16_9",
    "1:1": "square_hd",
}


class FalImageAdapter(ImageAdapter):
    provider_name = "fal"

    def __init__(self, model_id: str | None = None) -> None:
        if not settings.fal_key:
            raise ImageProviderError("FAL_KEY is not configured.")
        self._headers = {
            "Authorization": f"Key {settings.fal_key}",
            "Content-Type": "application/json",
        }
        self._model_id = model_id

    def _resolve_model(self, config: ImageGenConfig) -> str:
        if self._model_id:
            return self._model_id
        return REFERENCE_MODEL_ID if config.reference_image_urls else DEFAULT_MODEL_ID

    @staticmethod
    def _payload(config: ImageGenConfig) -> dict:
        payload: dict = {
            "prompt": config.prompt,
            "image_size": _RATIO_TO_SIZE.get(config.aspect_ratio, "portrait_16_9"),
            "num_images": 1,
            "enable_safety_checker": True,
        }
        if config.seed is not None:
            payload["seed"] = config.seed
        if config.reference_image_urls:
            payload["image_url"] = config.reference_image_urls[0]
        payload.update(config.extra)
        return payload

    async def generate(self, config: ImageGenConfig) -> ImageGenResult:
        model_id = self._resolve_model(config)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            try:
                submit = await client.post(
                    f"{QUEUE_ROOT}/{model_id}",
                    json=self._payload(config),
                    headers=self._headers,
                )
            except httpx.HTTPError as exc:
                raise ImageProviderError("Could not reach the image provider.") from exc

            if submit.status_code >= 400:
                raise ImageProviderError(
                    f"Image provider rejected the request ({submit.status_code})."
                )

            request_id = (submit.json() or {}).get("request_id")
            if not request_id:
                raise ImageProviderError("Image provider did not return a job id.")

            for _ in range(POLL_ATTEMPTS):
                await asyncio.sleep(POLL_SECONDS)
                try:
                    status = await client.get(
                        f"{QUEUE_ROOT}/requests/{request_id}/status",
                        headers=self._headers,
                    )
                except httpx.HTTPError as exc:
                    raise ImageProviderError("Lost contact with the image provider.") from exc

                state = str((status.json() or {}).get("status", "")).upper()
                if state in ("FAILED", "ERROR"):
                    raise ImageProviderError("Image generation failed.")
                if state != "COMPLETED":
                    continue

                result = await client.get(
                    f"{QUEUE_ROOT}/requests/{request_id}", headers=self._headers
                )
                if result.status_code >= 400:
                    raise ImageProviderError("Could not retrieve the generated image.")

                data = result.json() or {}
                images = data.get("images") or []
                url = images[0].get("url") if images and isinstance(images[0], dict) else None
                if not url:
                    raise ImageProviderError("Provider response contained no image.")
                seed = data.get("seed")
                return ImageGenResult(
                    image_url=str(url),
                    provider=self.provider_name,
                    seed=int(seed) if isinstance(seed, int) else None,
                )

        raise ImageProviderError("Image generation timed out.")
