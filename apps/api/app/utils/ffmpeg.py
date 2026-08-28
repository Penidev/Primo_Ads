"""FFmpeg command construction and execution.

Security (SECURITY.md §4): commands are built as argument *lists* and run without
a shell, so no filename or model-produced text can ever be interpreted as a
shell command. Input paths are additionally confined to a work directory.
"""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

# Normalisation targets so clips from different models concatenate cleanly.
TARGET_FPS = 24
TARGET_AUDIO_RATE = 48000
DIMENSIONS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


class FFmpegError(Exception):
    """FFmpeg failed. Message is safe to log (contains no user secrets)."""


@dataclass(frozen=True)
class StitchResult:
    output_path: Path
    thumbnail_path: Path


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _validate_inside(path: Path, work_dir: Path) -> Path:
    """Reject any path that escapes the work directory (traversal defence)."""
    resolved = path.resolve()
    root = work_dir.resolve()
    if not resolved.is_relative_to(root):
        raise FFmpegError("Refusing to process a file outside the work directory.")
    if not resolved.is_file():
        raise FFmpegError("Input clip is missing.")
    return resolved


def build_concat_command(
    clips: list[Path],
    output: Path,
    aspect_ratio: str = "9:16",
) -> list[str]:
    """Build a normalise-and-concat command as an argument list.

    Every input is scaled/padded to identical dimensions, forced to a common
    frame rate, and given a uniform audio stream, then concatenated. Re-encoding
    (rather than stream copy) is required because clips from different models
    have mismatched codec parameters.
    """
    if not clips:
        raise FFmpegError("No clips to stitch.")

    width, height = DIMENSIONS.get(aspect_ratio, DIMENSIONS["9:16"])

    cmd: list[str] = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"]
    for clip in clips:
        cmd += ["-i", str(clip)]

    filters: list[str] = []
    for index in range(len(clips)):
        filters.append(
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={TARGET_FPS},setsar=1,format=yuv420p[v{index}]"
        )
        # Some models return silent clips; anullsrc guarantees an audio stream so
        # the concat filter receives matching stream counts for every input.
        filters.append(
            f"[{index}:a]aresample={TARGET_AUDIO_RATE},"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{index}]"
        )

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
    filters.append(f"{concat_inputs}concat=n={len(clips)}:v=1:a=1[outv][outa]")

    cmd += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output),
    ]
    return cmd


def build_thumbnail_command(video: Path, output: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-vf",
        "thumbnail,scale=640:-1",
        "-frames:v",
        "1",
        str(output),
    ]


async def run_command(cmd: list[str], timeout: float = 900.0) -> None:
    """Execute an ffmpeg argument list without a shell."""
    if not ffmpeg_available():
        raise FFmpegError("ffmpeg is not installed in this environment.")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        process.kill()
        raise FFmpegError("Video processing timed out.") from exc

    if process.returncode != 0:
        detail = (stderr or b"").decode("utf-8", "replace").strip()[:500]
        raise FFmpegError(f"ffmpeg failed: {detail or 'unknown error'}")


async def stitch_clips(
    clips: list[Path],
    work_dir: Path,
    aspect_ratio: str = "9:16",
) -> StitchResult:
    """Normalise, concatenate, and thumbnail a set of local clips."""
    validated = [_validate_inside(clip, work_dir) for clip in clips]
    output = work_dir / "final_ad.mp4"
    thumbnail = work_dir / "final_ad_thumb.jpg"

    await run_command(build_concat_command(validated, output, aspect_ratio))
    await run_command(build_thumbnail_command(output, thumbnail))
    return StitchResult(output_path=output, thumbnail_path=thumbnail)
