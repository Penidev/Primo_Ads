"""Clip-source resolution in the stitching service.

A clip URL comes from a provider response, so it is untrusted input. The
`file://` branch exists so mock and local-storage runs can stitch at all, but it
must not become a way to read arbitrary files off the worker.
"""

from pathlib import Path

import pytest

from app.config import settings
from app.services.stitch_service import StitchError, _local_source


def _uri(path: Path) -> str:
    return path.resolve().as_uri()


def _root_uri() -> str:
    """`file://` URI for the media root, correct on both POSIX and Windows.

    A POSIX root is `/tmp/x` and a Windows one is `C:/x`, so the leading slash
    is normalised rather than assumed.
    """
    posix = Path(settings.mock_media_dir).resolve().as_posix()
    return "file:///" + posix.lstrip("/")


class TestRemoteUrls:
    @pytest.mark.parametrize(
        "url",
        [
            "https://provider.test/clips/abc.mp4",
            "http://provider.test/clips/abc.mp4",
            "HTTPS://provider.test/clips/abc.mp4",
        ],
    )
    def test_http_urls_are_left_to_the_network_path(self, url):
        assert _local_source(url) is None


class TestLocalUrls:
    def test_file_inside_the_media_root_resolves(self):
        root = Path(settings.mock_media_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        clip = root / "resolves.mp4"
        clip.write_bytes(b"x")
        assert _local_source(_uri(clip)) == clip

    def test_nested_file_inside_the_root_resolves(self):
        root = Path(settings.mock_media_dir).resolve()
        nested = root / "a" / "b"
        nested.mkdir(parents=True, exist_ok=True)
        clip = nested / "deep.mp4"
        clip.write_bytes(b"x")
        assert _local_source(_uri(clip)) == clip


class TestConfinement:
    """Each of these is a path a hostile provider response could contain."""

    def test_absolute_path_outside_the_root_is_refused(self):
        outside = Path("/etc/passwd") if Path("/etc").exists() else Path("C:/Windows/win.ini")
        with pytest.raises(StitchError):
            _local_source(outside.resolve().as_uri())

    def test_traversal_out_of_the_root_is_refused(self):
        # Built by hand because as_uri() would normalise the traversal away.
        with pytest.raises(StitchError):
            _local_source(f"{_root_uri()}/../../../../etc/passwd")

    def test_encoded_traversal_is_refused(self):
        with pytest.raises(StitchError):
            _local_source(f"{_root_uri()}/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd")

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://provider.test/clip.mp4",
            "gopher://provider.test/clip.mp4",
            "data:video/mp4;base64,AAAA",
            "javascript:alert(1)",
            "//provider.test/clip.mp4",
            "not-a-url-at-all",
        ],
    )
    def test_other_schemes_are_refused(self, url):
        with pytest.raises(StitchError):
            _local_source(url)
