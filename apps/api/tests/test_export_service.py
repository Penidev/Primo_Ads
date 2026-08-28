"""Script export tests."""

import csv
import io

from app.schemas.script import GeneratedScript
from app.services.export_service import (
    to_markdown,
    to_prompt_list,
    to_shot_list_csv,
)


def _script() -> GeneratedScript:
    return GeneratedScript.model_validate(
        {
            "campaign_title": "Stop the Checkout Chaos",
            "total_duration_seconds": 12,
            "music_direction": "Tense build to uplifting synth",
            "overall_color_palette": "Cold blue to warm violet",
            "target_emotion_arc": "frustration to confidence",
            "scenes": [
                {
                    "scene_number": 1,
                    "scene_label": "The Hook",
                    "duration_seconds": 6,
                    "script_text": "Losing customers at checkout?",
                    "visual_description": "Thumb hovering over a cluttered form.",
                    "camera_movement": "Slow push-in",
                    "lighting": "Harsh phone glow",
                    "color_grading": "Desaturated blues",
                    "audio_sfx": "Digital error beeps",
                    "video_prompt": "Close-up of a hesitant thumb over a phone screen.",
                    "image_gen_needed": [
                        {
                            "asset_type": "background",
                            "description": "Cluttered checkout UI",
                            "style": "photorealistic",
                        }
                    ],
                },
                {
                    "scene_number": 2,
                    "scene_label": "The Fix",
                    "duration_seconds": 6,
                    "script_text": "One tap. Done.",
                    "visual_description": "Single tap completes the payment.",
                    "camera_movement": "Static macro",
                    "video_prompt": "Macro shot of a thumb tapping a clean pay button.",
                    "image_gen_needed": [],
                },
            ],
        }
    )


class TestMarkdownTreatment:
    def test_includes_campaign_title_as_heading(self):
        assert to_markdown(_script()).startswith("# Stop the Checkout Chaos")

    def test_includes_brand_when_supplied(self):
        assert "**Brand:** Cozzipay" in to_markdown(_script(), "Cozzipay")

    def test_omits_brand_line_when_absent(self):
        assert "**Brand:**" not in to_markdown(_script())

    def test_includes_every_scene(self):
        body = to_markdown(_script())
        assert "## Scene 1 — The Hook (6s)" in body
        assert "## Scene 2 — The Fix (6s)" in body

    def test_includes_directorial_detail(self):
        body = to_markdown(_script())
        assert "**Camera:** Slow push-in" in body
        assert "**Lighting:** Harsh phone glow" in body
        assert "**Colour grading:** Desaturated blues" in body

    def test_quotes_dialogue(self):
        assert "> Losing customers at checkout?" in to_markdown(_script())

    def test_lists_required_assets(self):
        body = to_markdown(_script())
        assert "**Assets required:**" in body
        assert "background: Cluttered checkout UI (photorealistic)" in body

    def test_includes_overall_direction(self):
        body = to_markdown(_script())
        assert "Tense build to uplifting synth" in body
        assert "Cold blue to warm violet" in body

    def test_skips_empty_optional_fields(self):
        """Scene 2 has no lighting, so no empty label should appear for it."""
        body = to_markdown(_script())
        assert "**Lighting:** \n" not in body


class TestShotListCsv:
    def _rows(self) -> list[list[str]]:
        return list(csv.reader(io.StringIO(to_shot_list_csv(_script()))))

    def test_has_header_row(self):
        assert self._rows()[0][0] == "Scene"

    def test_one_row_per_scene(self):
        assert len(self._rows()) == 3  # header + 2 scenes

    def test_carries_camera_column(self):
        header, first = self._rows()[0], self._rows()[1]
        assert first[header.index("Shot / Camera")] == "Slow push-in"

    def test_blank_for_missing_values(self):
        header, second = self._rows()[0], self._rows()[2]
        assert second[header.index("Lighting")] == ""

    def test_text_with_punctuation_survives_csv_encoding(self):
        rows = self._rows()
        column = rows[0].index("Action / Visual")
        assert rows[1][column] == "Thumb hovering over a cluttered form."


class TestPromptList:
    def test_includes_title(self):
        assert "Stop the Checkout Chaos" in to_prompt_list(_script())

    def test_includes_each_prompt(self):
        body = to_prompt_list(_script())
        assert "Close-up of a hesitant thumb over a phone screen." in body
        assert "Macro shot of a thumb tapping a clean pay button." in body

    def test_labels_scenes_with_duration(self):
        assert "Scene 1 (6s)" in to_prompt_list(_script())
