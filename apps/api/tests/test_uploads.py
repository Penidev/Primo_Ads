"""Upload sanitisation tests (SECURITY.md §4)."""

import io
import uuid

import pytest
from PIL import Image

from app.utils.uploads import (
    MAX_IMAGE_BYTES,
    UploadValidationError,
    build_asset_key,
    sanitise_image,
)


def _png(size: tuple[int, int] = (8, 8)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, (10, 20, 30, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_with_exif() -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (8, 8), (200, 100, 50))
    # Attach EXIF so we can assert it is stripped on re-encode.
    exif = image.getexif()
    exif[271] = "SecretCameraMake"
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


class TestAcceptedFormats:
    def test_accepts_png(self):
        result = sanitise_image(_png())
        assert result.content_type == "image/png"
        assert result.extension == "png"

    def test_accepts_jpeg(self):
        result = sanitise_image(_jpeg_with_exif())
        assert result.content_type == "image/jpeg"
        assert result.extension == "jpg"

    def test_output_is_a_valid_image(self):
        result = sanitise_image(_png())
        with Image.open(io.BytesIO(result.data)) as reopened:
            assert reopened.size == (8, 8)


class TestRejections:
    def test_rejects_empty_file(self):
        with pytest.raises(UploadValidationError):
            sanitise_image(b"")

    def test_rejects_non_image_bytes(self):
        with pytest.raises(UploadValidationError):
            sanitise_image(b"this is definitely not an image")

    def test_rejects_disguised_executable(self):
        """A file named like an image but carrying an EXE header is refused."""
        with pytest.raises(UploadValidationError):
            sanitise_image(b"MZ\x90\x00" + b"\x00" * 128)

    def test_rejects_svg_payload(self):
        """SVG can carry script; it is not in the allowlist."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        with pytest.raises(UploadValidationError):
            sanitise_image(svg)

    def test_rejects_oversized_file(self):
        oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_IMAGE_BYTES
        with pytest.raises(UploadValidationError):
            sanitise_image(oversized)

    def test_respects_custom_size_limit(self):
        with pytest.raises(UploadValidationError):
            sanitise_image(_png(), max_bytes=10)


class TestMetadataStripping:
    def test_exif_is_removed_on_reencode(self):
        original = _jpeg_with_exif()
        with Image.open(io.BytesIO(original)) as before:
            assert before.getexif().get(271) == "SecretCameraMake"

        cleaned = sanitise_image(original)
        with Image.open(io.BytesIO(cleaned.data)) as after:
            assert after.getexif().get(271) is None

    def test_trailing_appended_data_is_dropped(self):
        """Bytes appended after the image payload do not survive re-encoding."""
        polyglot = _png() + b"<?php system($_GET[0]); ?>"
        cleaned = sanitise_image(polyglot)
        assert b"<?php" not in cleaned.data


class TestAssetKeys:
    def test_key_is_scoped_to_owner_and_project(self):
        user_id, project_id = uuid.uuid4(), uuid.uuid4()
        key = build_asset_key(user_id, project_id, "png")
        assert key.startswith(f"projects/{user_id}/{project_id}/assets/")
        assert key.endswith(".png")

    def test_keys_are_unique(self):
        user_id, project_id = uuid.uuid4(), uuid.uuid4()
        a = build_asset_key(user_id, project_id, "png")
        b = build_asset_key(user_id, project_id, "png")
        assert a != b

    def test_key_contains_no_path_traversal(self):
        key = build_asset_key(uuid.uuid4(), uuid.uuid4(), "png")
        assert ".." not in key
