"""Script schema validation — the guard against untrusted model output.

Any LLM response must pass these models before the pipeline uses it
(SECURITY.md §4: never act on unvalidated model output).
"""

import pytest
from pydantic import ValidationError

from app.schemas.script import GeneratedScript, SceneScript


def _scene(**overrides) -> dict:
    base = {
        "scene_number": 1,
        "scene_label": "The Hook",
        "duration_seconds": 6,
        "script_text": "Tired of losing customers at checkout?",
        "visual_description": "Close-up of a thumb hovering over a cluttered form.",
        "video_prompt": "Close-up tracking shot of a hesitant thumb over a phone.",
        "image_gen_needed": [],
    }
    base.update(overrides)
    return base


def _script(**overrides) -> dict:
    base = {
        "campaign_title": "Stop the Checkout Chaos",
        "total_duration_seconds": 6,
        "scenes": [_scene()],
    }
    base.update(overrides)
    return base


class TestValidScripts:
    def test_minimal_script_validates(self):
        script = GeneratedScript.model_validate(_script())
        assert script.campaign_title == "Stop the Checkout Chaos"
        assert len(script.scenes) == 1

    def test_optional_fields_default_to_none(self):
        scene = SceneScript.model_validate(_scene())
        assert scene.camera_movement is None
        assert scene.image_gen_needed == []

    def test_asset_requirements_parse(self):
        scene = SceneScript.model_validate(
            _scene(
                image_gen_needed=[
                    {
                        "asset_type": "background",
                        "description": "Cluttered checkout UI",
                        "style": "photorealistic",
                    }
                ]
            )
        )
        assert scene.image_gen_needed[0].asset_type == "background"


class TestRejectsMalformedOutput:
    def test_missing_scenes_rejected(self):
        with pytest.raises(ValidationError):
            GeneratedScript.model_validate({"campaign_title": "x", "total_duration_seconds": 6})

    def test_empty_scene_list_rejected(self):
        with pytest.raises(ValidationError):
            GeneratedScript.model_validate(_script(scenes=[]))

    def test_missing_video_prompt_rejected(self):
        broken = _scene()
        del broken["video_prompt"]
        with pytest.raises(ValidationError):
            SceneScript.model_validate(broken)

    def test_zero_scene_number_rejected(self):
        with pytest.raises(ValidationError):
            SceneScript.model_validate(_scene(scene_number=0))

    def test_absurd_duration_rejected(self):
        with pytest.raises(ValidationError):
            SceneScript.model_validate(_scene(duration_seconds=9999))

    def test_overlong_text_rejected(self):
        with pytest.raises(ValidationError):
            SceneScript.model_validate(_scene(visual_description="x" * 5000))

    def test_too_many_scenes_rejected(self):
        with pytest.raises(ValidationError):
            GeneratedScript.model_validate(
                _script(scenes=[_scene(scene_number=i + 1) for i in range(60)])
            )

    def test_excessive_total_duration_rejected(self):
        with pytest.raises(ValidationError):
            GeneratedScript.model_validate(_script(total_duration_seconds=99999))

    def test_non_integer_scene_number_rejected(self):
        with pytest.raises(ValidationError):
            SceneScript.model_validate(_scene(scene_number="first"))
