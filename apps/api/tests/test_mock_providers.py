"""Contract tests for the mock providers.

The point of these is to prove the mocks are *interchangeable* with the live
adapters, not merely convenient. If a mock drifts from its interface, swapping to
a real API would surface bugs late — exactly the bottleneck we are avoiding.

So these assert:
  * each mock is an instance of the abstract base its live counterpart implements,
  * output passes the same strict schema validation as live output,
  * failures raise the same exception classes,
  * the video mock reproduces the queued -> running -> completed lifecycle.
"""

import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

import pytest

from app.adapters.image.base import ImageAdapter, ImageGenConfig, ImageProviderError
from app.adapters.llm.base import LLMAdapter
from app.adapters.llm.gemini import LLMRequestError
from app.adapters.mock.mock_image import MockImageAdapter
from app.adapters.mock.mock_llm import MockLLMAdapter
from app.adapters.mock.mock_video import MockVideoAdapter, reset_jobs
from app.adapters.storage.base import StorageAdapter
from app.adapters.storage.local_adapter import LocalStorageAdapter, LocalStorageError
from app.adapters.video.base import (
    JobState,
    VideoGenConfig,
    VideoModelAdapter,
)
from app.schemas.blueprint import BlueprintAnalysis
from app.schemas.script import GeneratedScript
from app.utils.prompt_builder import extract_json_object

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolate_media(tmp_path, monkeypatch):
    """Write mock media into a per-test directory."""
    from app.config import settings

    monkeypatch.setattr(settings, "mock_media_dir", str(tmp_path), raising=False)
    reset_jobs()


def _path_from_uri(uri: str) -> Path:
    """Convert a file:// URI back to a path, correctly on POSIX and Windows."""
    return Path(url2pathname(urlparse(uri).path))


BRIEF_CONTENT = json.dumps(
    {
        "brand": {"name": "Cozzipay"},
        "product": {"name": "1-click checkout"},
        "aspect_ratio": "9:16",
        "target_duration_seconds": 30,
    }
)


class TestInterfaceConformance:
    """Each mock must satisfy the same abstraction as its live counterpart."""

    def test_llm_mock_implements_interface(self):
        assert isinstance(MockLLMAdapter(), LLMAdapter)

    def test_image_mock_implements_interface(self):
        assert isinstance(MockImageAdapter(), ImageAdapter)

    def test_video_mock_implements_interface(self):
        assert isinstance(MockVideoAdapter(), VideoModelAdapter)

    def test_local_storage_implements_interface(self):
        assert isinstance(LocalStorageAdapter(), StorageAdapter)


class TestMockLlmScriptOutput:
    async def test_output_passes_strict_script_validation(self):
        raw = await MockLLMAdapter().generate_json("system", BRIEF_CONTENT)
        script = GeneratedScript.model_validate(json.loads(extract_json_object(raw)))
        assert script.scenes

    async def test_scene_durations_sum_to_total(self):
        """The live prompt requires this; the mock must honour the same rule."""
        raw = await MockLLMAdapter().generate_json("system", BRIEF_CONTENT)
        script = GeneratedScript.model_validate(json.loads(raw))
        assert sum(s.duration_seconds for s in script.scenes) == (script.total_duration_seconds)

    async def test_respects_requested_duration(self):
        content = json.dumps({"brand": {"name": "X"}, "target_duration_seconds": 15})
        raw = await MockLLMAdapter().generate_json("system", content)
        script = GeneratedScript.model_validate(json.loads(raw))
        assert script.total_duration_seconds == 15

    async def test_uses_brand_name_from_brief(self):
        raw = await MockLLMAdapter().generate_json("system", BRIEF_CONTENT)
        assert "Cozzipay" in raw

    async def test_carries_aspect_ratio_into_video_prompts(self):
        raw = await MockLLMAdapter().generate_json("system", BRIEF_CONTENT)
        script = GeneratedScript.model_validate(json.loads(raw))
        assert all("9:16" in scene.video_prompt for scene in script.scenes)

    async def test_output_is_deterministic(self):
        adapter = MockLLMAdapter()
        first = await adapter.generate_json("system", BRIEF_CONTENT)
        second = await adapter.generate_json("system", BRIEF_CONTENT)
        assert first == second

    async def test_declares_assets_for_the_pipeline_to_generate(self):
        raw = await MockLLMAdapter().generate_json("system", BRIEF_CONTENT)
        script = GeneratedScript.model_validate(json.loads(raw))
        assert any(scene.image_gen_needed for scene in script.scenes)

    async def test_failure_token_raises_live_exception_type(self):
        with pytest.raises(LLMRequestError):
            await MockLLMAdapter().generate_json("system", "__FAIL_LLM__")


class TestMockLlmVideoAnalysis:
    async def test_output_passes_strict_blueprint_validation(self):
        raw = await MockLLMAdapter().analyze_video_json(
            "system", "analyse this", b"fake-video-bytes", "video/mp4"
        )
        analysis = BlueprintAnalysis.model_validate(json.loads(raw))
        assert analysis.beats

    async def test_honours_category_hint(self):
        raw = await MockLLMAdapter().analyze_video_json(
            "system",
            json.dumps({"category_hint": "social-proof"}),
            b"bytes",
            "video/mp4",
        )
        assert BlueprintAnalysis.model_validate(json.loads(raw)).ad_category == ("social-proof")

    async def test_beats_have_ascending_non_overlapping_timings(self):
        raw = await MockLLMAdapter().analyze_video_json("system", "analyse", b"bytes", "video/mp4")
        beats = BlueprintAnalysis.model_validate(json.loads(raw)).beats
        for previous, following in zip(beats, beats[1:], strict=False):
            assert previous.end_second <= following.start_second


class TestMockEmbeddings:
    async def test_dimensionality_matches_the_column(self):
        from app.models.ad_blueprint import EMBEDDING_DIM

        assert len(await MockLLMAdapter().embed("text")) == EMBEDDING_DIM

    async def test_values_are_in_range(self):
        vector = await MockLLMAdapter().embed("text")
        assert all(-1.0 <= value <= 1.0 for value in vector)

    async def test_same_text_yields_same_vector(self):
        adapter = MockLLMAdapter()
        assert await adapter.embed("abc") == await adapter.embed("abc")

    async def test_different_text_yields_different_vector(self):
        adapter = MockLLMAdapter()
        assert await adapter.embed("abc") != await adapter.embed("xyz")


class TestMockImage:
    async def test_produces_a_real_decodable_image(self):
        """A fake URL would hide bugs in code that fetches or re-encodes."""
        from PIL import Image

        result = await MockImageAdapter().generate(ImageGenConfig(prompt="a phone"))
        with Image.open(_path_from_uri(result.image_url)) as image:
            assert image.size[0] > 0

    @pytest.mark.parametrize(
        "ratio,expected",
        [("9:16", (576, 1024)), ("16:9", (1024, 576)), ("1:1", (768, 768))],
    )
    async def test_honours_aspect_ratio(self, ratio, expected):
        from PIL import Image

        result = await MockImageAdapter().generate(
            ImageGenConfig(prompt="a phone", aspect_ratio=ratio)
        )
        with Image.open(_path_from_uri(result.image_url)) as image:
            assert image.size == expected

    async def test_failure_token_raises_live_exception_type(self):
        with pytest.raises(ImageProviderError):
            await MockImageAdapter().generate(ImageGenConfig(prompt="__FAIL_IMAGE__"))


class TestMockVideoLifecycle:
    async def test_submit_returns_a_job_handle(self):
        submission = await MockVideoAdapter().submit(
            VideoGenConfig(model_id="mock", prompt="a shot")
        )
        assert submission.provider_job_id

    async def test_reports_progress_before_completing(self):
        """Instant completion would skip the polling and progress code paths."""
        adapter = MockVideoAdapter()
        submission = await adapter.submit(
            VideoGenConfig(model_id="mock", prompt="a shot", duration_seconds=1)
        )
        states = []
        for _ in range(4):
            status = await adapter.check_status(submission.provider_job_id)
            states.append(status.state)
            if status.state is JobState.COMPLETED:
                break
        assert states[0] is JobState.QUEUED
        assert JobState.RUNNING in states
        assert states[-1] is JobState.COMPLETED

    async def test_completed_status_carries_a_video_url(self):
        adapter = MockVideoAdapter()
        submission = await adapter.submit(
            VideoGenConfig(model_id="mock", prompt="a shot", duration_seconds=1)
        )
        status = None
        for _ in range(5):
            status = await adapter.check_status(submission.provider_job_id)
            if status.state is JobState.COMPLETED:
                break
        assert status is not None
        assert status.video_url

    async def test_failure_token_reports_failed_state(self):
        adapter = MockVideoAdapter()
        submission = await adapter.submit(VideoGenConfig(model_id="mock", prompt="__FAIL_VIDEO__"))
        status = await adapter.check_status(submission.provider_job_id)
        assert status.state is JobState.FAILED
        assert status.error_message

    async def test_unknown_job_id_fails_rather_than_hanging(self):
        status = await MockVideoAdapter().check_status("does-not-exist")
        assert status.state is JobState.FAILED


class TestLocalStorage:
    async def test_round_trips_content(self, tmp_path):
        adapter = LocalStorageAdapter(root=str(tmp_path))
        key = await adapter.upload("nested/file.png", b"payload", "image/png")
        assert (tmp_path / "nested" / "file.png").read_bytes() == b"payload"
        assert key == "nested/file.png"

    async def test_signed_url_points_at_the_file(self, tmp_path):
        adapter = LocalStorageAdapter(root=str(tmp_path))
        await adapter.upload("a.png", b"x", "image/png")
        assert (await adapter.signed_url("a.png")).startswith("file:")

    async def test_delete_removes_the_file(self, tmp_path):
        adapter = LocalStorageAdapter(root=str(tmp_path))
        await adapter.upload("a.png", b"x", "image/png")
        await adapter.delete("a.png")
        assert not (tmp_path / "a.png").exists()

    async def test_delete_is_idempotent(self, tmp_path):
        adapter = LocalStorageAdapter(root=str(tmp_path))
        await adapter.delete("never-existed.png")  # must not raise

    async def test_rejects_path_traversal(self, tmp_path):
        """A key must not be able to escape the storage root."""
        adapter = LocalStorageAdapter(root=str(tmp_path))
        with pytest.raises(LocalStorageError):
            await adapter.upload("../escaped.png", b"x", "image/png")
