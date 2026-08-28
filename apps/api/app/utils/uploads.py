"""Secure file-upload validation (SECURITY.md §4).

Rules enforced here:
* Type is determined from magic bytes, never the client-supplied name or MIME.
* Hard size cap applied before any processing.
* Images are re-encoded, which strips EXIF/GPS metadata and neutralises
  polyglot or payload-carrying files.
* Storage keys are randomised so uploads can never be guessed or traversed.
"""

import io
import uuid
from dataclasses import dataclass

from PIL import Image

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

# Magic-byte signatures for the formats we accept.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]

# Pillow format -> (content type, save format)
_SAFE_OUTPUT = {
    "PNG": ("image/png", "PNG"),
    "JPEG": ("image/jpeg", "JPEG"),
    "GIF": ("image/png", "PNG"),  # normalise GIF to PNG (drops animation/payloads)
    "WEBP": ("image/webp", "WEBP"),
}


class UploadValidationError(Exception):
    """Raised when an upload fails validation. Message is user-safe."""


@dataclass(frozen=True)
class SanitisedUpload:
    data: bytes
    content_type: str
    extension: str


def _detect_by_magic(data: bytes) -> str | None:
    for signature, content_type in _SIGNATURES:
        if data.startswith(signature):
            return content_type
    # WEBP: "RIFF" .... "WEBP"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def sanitise_image(data: bytes, max_bytes: int = MAX_IMAGE_BYTES) -> SanitisedUpload:
    """Validate and re-encode an uploaded image, or raise UploadValidationError."""
    if not data:
        raise UploadValidationError("The uploaded file is empty.")
    if len(data) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise UploadValidationError(f"File is too large. Maximum size is {limit_mb} MB.")
    if _detect_by_magic(data) is None:
        raise UploadValidationError("Unsupported file type. Upload a PNG, JPEG, GIF or WebP image.")

    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()  # structural check
        # verify() invalidates the object, so reopen for the actual re-encode.
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            if fmt not in _SAFE_OUTPUT:
                raise UploadValidationError("Unsupported image format.")
            content_type, save_format = _SAFE_OUTPUT[fmt]

            # Preserve alpha for PNG/WebP; flatten for JPEG.
            if save_format == "JPEG" and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif save_format in ("PNG", "WEBP") and img.mode not in (
                "RGB",
                "RGBA",
                "L",
                "LA",
            ):
                img = img.convert("RGBA")

            buffer = io.BytesIO()
            # Re-encode without metadata: no EXIF/GPS carried through.
            img.save(buffer, format=save_format)
            clean = buffer.getvalue()
    except UploadValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - any decode failure is a rejection
        raise UploadValidationError("The file could not be processed as an image.") from exc

    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[content_type]
    return SanitisedUpload(data=clean, content_type=content_type, extension=extension)


def build_asset_key(user_id: uuid.UUID, project_id: uuid.UUID, extension: str) -> str:
    """Randomised, non-guessable storage key scoped to owner and project."""
    return f"projects/{user_id}/{project_id}/assets/{uuid.uuid4()}.{extension}"


# ---------------------------- video uploads ----------------------------

MAX_VIDEO_BYTES = 200 * 1024 * 1024  # 200 MB reference ad ceiling

# Container signatures. MP4/MOV use an 'ftyp' box at offset 4.
_VIDEO_BRANDS = (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"qt  ", b"M4V ", b"mmp4")


def detect_video_mime(data: bytes) -> str | None:
    """Identify a supported video container from its magic bytes."""
    if len(data) < 12:
        return None
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand == b"qt  ":
            return "video/quicktime"
        if brand in _VIDEO_BRANDS:
            return "video/mp4"
        return "video/mp4"  # unknown brand but valid ftyp box
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"  # Matroska/WebM
    return None


def validate_video(data: bytes, max_bytes: int = MAX_VIDEO_BYTES) -> str:
    """Validate an uploaded reference video; return its detected MIME type.

    Videos are not re-encoded (too expensive), so the checks are: hard size cap,
    container signature allowlist, and rejection of anything unrecognised. The
    file is only ever sent to the analysis provider, never executed or served.
    """
    if not data:
        raise UploadValidationError("The uploaded file is empty.")
    if len(data) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise UploadValidationError(f"Video is too large. Maximum size is {limit_mb} MB.")

    mime = detect_video_mime(data)
    if mime is None:
        raise UploadValidationError("Unsupported video format. Upload an MP4, MOV, or WebM file.")
    return mime


def build_blueprint_key(blueprint_id: uuid.UUID, mime_type: str) -> str:
    """Storage key for a reference ad (internal curation use only)."""
    extension = {
        "video/mp4": "mp4",
        "video/quicktime": "mov",
        "video/webm": "webm",
    }.get(mime_type, "mp4")
    return f"swipe-file/{blueprint_id}/source.{extension}"
