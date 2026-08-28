"""FFmpeg command construction tests.

These assert the two security properties that matter here (SECURITY.md §4):
commands are argument lists (never shell strings), and inputs cannot escape the
work directory.
"""

from pathlib import Path

import pytest

from app.utils.ffmpeg import (
    DIMENSIONS,
    TARGET_FPS,
    FFmpegError,
    _validate_inside,
    build_concat_command,
    build_thumbnail_command,
)


class TestConcatCommand:
    def test_returns_argument_list_not_string(self):
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"))
        assert isinstance(cmd, list)
        assert all(isinstance(part, str) for part in cmd)

    def test_starts_with_ffmpeg_binary(self):
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"))
        assert cmd[0] == "ffmpeg"

    def test_disables_stdin_interaction(self):
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"))
        assert "-nostdin" in cmd

    def test_one_input_flag_per_clip(self):
        clips = [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")]
        cmd = build_concat_command(clips, Path("out.mp4"))
        assert cmd.count("-i") == 3

    def test_concat_count_matches_clip_count(self):
        clips = [Path("a.mp4"), Path("b.mp4")]
        cmd = build_concat_command(clips, Path("out.mp4"))
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "concat=n=2:v=1:a=1" in graph

    def test_normalises_frame_rate(self):
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"))
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert f"fps={TARGET_FPS}" in graph

    def test_reencodes_rather_than_stream_copies(self):
        """Stream copy would produce broken output from mismatched clips."""
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"))
        assert "libx264" in cmd
        assert "copy" not in cmd

    def test_forces_compatible_pixel_format(self):
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"))
        assert "yuv420p" in cmd

    @pytest.mark.parametrize("ratio", ["9:16", "16:9", "1:1"])
    def test_scales_to_expected_dimensions(self, ratio):
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"), aspect_ratio=ratio)
        graph = cmd[cmd.index("-filter_complex") + 1]
        width, height = DIMENSIONS[ratio]
        assert f"scale={width}:{height}" in graph

    def test_unknown_ratio_falls_back_to_vertical(self):
        cmd = build_concat_command([Path("a.mp4")], Path("out.mp4"), aspect_ratio="bogus")
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "scale=1080:1920" in graph

    def test_empty_clip_list_rejected(self):
        with pytest.raises(FFmpegError):
            build_concat_command([], Path("out.mp4"))

    def test_shell_metacharacters_stay_a_single_argument(self):
        """A malicious filename must not become extra shell tokens."""
        nasty = Path("clip; rm -rf / #.mp4")
        cmd = build_concat_command([nasty], Path("out.mp4"))
        assert str(nasty) in cmd  # present as exactly one argv entry
        assert not any(part == "rm" for part in cmd)


class TestThumbnailCommand:
    def test_extracts_single_frame(self):
        cmd = build_thumbnail_command(Path("in.mp4"), Path("out.jpg"))
        assert "-frames:v" in cmd
        assert cmd[cmd.index("-frames:v") + 1] == "1"

    def test_is_argument_list(self):
        cmd = build_thumbnail_command(Path("in.mp4"), Path("out.jpg"))
        assert isinstance(cmd, list)
        assert cmd[0] == "ffmpeg"


class TestPathConfinement:
    def test_accepts_file_inside_work_dir(self, tmp_path):
        clip = tmp_path / "scene.mp4"
        clip.write_bytes(b"data")
        assert _validate_inside(clip, tmp_path) == clip.resolve()

    def test_rejects_traversal_outside_work_dir(self, tmp_path):
        outside = tmp_path.parent / "escaped.mp4"
        outside.write_bytes(b"data")
        with pytest.raises(FFmpegError):
            _validate_inside(outside, tmp_path)

    def test_rejects_dotdot_traversal(self, tmp_path):
        work = tmp_path / "work"
        work.mkdir()
        target = tmp_path / "secret.mp4"
        target.write_bytes(b"data")
        with pytest.raises(FFmpegError):
            _validate_inside(work / ".." / "secret.mp4", work)

    def test_rejects_missing_file(self, tmp_path):
        with pytest.raises(FFmpegError):
            _validate_inside(tmp_path / "nope.mp4", tmp_path)
