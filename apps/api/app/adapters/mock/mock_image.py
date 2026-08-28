"""Mock image adapter.

Generates a real PNG (a deterministic gradient) rather than returning a fake URL,
so downstream code that fetches, stores, or re-encodes the image behaves exactly
as it will with a live provider.

Failure injection: include ``__FAIL_IMAGE__`` in the prompt to raise
`ImageProviderError`, which exercises the per-image refund path.
"""

import hashlib
import io
import uuid
from pathlib import Path

from PIL import Image

from app.adapters.image.base import (
    ImageAdapter,
    ImageGenConfig,
    ImageGenResult,
    ImageProviderError,
)
from app.config import settings

FAIL_TOKEN = "__FAIL_IMAGE__"  # noqa: S105 - a marker string, not a credential

_SIZES = {
    "9:16": (576, 1024),
    "16:9": (1024, 576),
    "1:1": (768, 768),
}


class MockImageAdapter(ImageAdapter):
    provider_name = "mock"

    def _media_dir(self) -> Path:
        path = Path(settings.mock_media_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def generate(self, config: ImageGenConfig) -> ImageGenResult:
        if FAIL_TOKEN in config.prompt:
            raise ImageProviderError("Mock image failure requested via test token.")

        width, height = _SIZES.get(config.aspect_ratio, _SIZES["9:16"])
        seed = int(hashlib.sha256(config.prompt.encode()).hexdigest()[:6], 16)

        # A deterministic two-tone gradient: visually distinct per prompt, so a
        # reviewer can tell scenes apart while testing.
        top = ((seed >> 16) & 0xFF, (seed >> 8) & 0xFF, seed & 0xFF)
        bottom = (255 - top[0], 255 - top[1], 255 - top[2])
        image = Image.new("RGB", (width, height))
        for y in range(height):
            ratio = y / max(height - 1, 1)
            row = tuple(
                int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)
            )
            for x in range(width):
                image.putpixel((x, y), row)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        filename = f"mock-image-{uuid.uuid4().hex}.png"
        destination = self._media_dir() / filename
        destination.write_bytes(buffer.getvalue())

        return ImageGenResult(
            image_url=destination.as_uri(),
            provider=self.provider_name,
            seed=seed,
        )
