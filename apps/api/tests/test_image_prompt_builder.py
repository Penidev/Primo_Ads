"""Image prompt builder tests — pure logic, no dependencies."""

from app.utils.image_prompt_builder import (
    MAX_PROMPT_CHARS,
    build_asset_prompt,
    build_character_sheet_prompt,
)


class TestAssetPrompt:
    def test_includes_description(self):
        prompt = build_asset_prompt("A cluttered mobile checkout form")
        assert "A cluttered mobile checkout form" in prompt

    def test_translates_brand_colours_to_words(self):
        prompt = build_asset_prompt("A phone", brand_colours=["#3400D1", "#FFD600"])
        assert "royal violet" in prompt
        assert "golden yellow" in prompt
        assert "#3400D1" not in prompt

    def test_omits_colour_clause_without_colours(self):
        assert "Colour palette" not in build_asset_prompt("A phone")

    def test_deduplicates_near_identical_colours(self):
        prompt = build_asset_prompt("A phone", brand_colours=["#3400D1", "#3500D2"])
        assert prompt.count("royal violet") == 1

    def test_includes_style_note(self):
        prompt = build_asset_prompt("A phone", style="photorealistic product shot")
        assert "photorealistic product shot." in prompt

    def test_does_not_double_punctuate_style(self):
        assert "Moody.." not in build_asset_prompt("A phone", style="Moody.")

    def test_includes_voice_tone_as_mood(self):
        prompt = build_asset_prompt("A phone", voice_tone=["Bold", "Playful"])
        assert "Overall mood: bold, playful." in prompt

    def test_suppresses_text_rendering_by_default(self):
        prompt = build_asset_prompt("A phone")
        assert "No text, no watermarks, no logos" in prompt

    def test_product_assets_get_hero_framing(self):
        prompt = build_asset_prompt("A payment terminal", asset_type="product")
        assert "hero shot" in prompt

    def test_always_appends_quality_suffix(self):
        assert "professional commercial photography" in build_asset_prompt("A phone")

    def test_truncates_overlong_prompts(self):
        prompt = build_asset_prompt("word " * 800)
        assert len(prompt) <= MAX_PROMPT_CHARS + 1

    def test_ignores_unparseable_colours(self):
        prompt = build_asset_prompt("A phone", brand_colours=["z" * 80])
        assert "Colour palette" not in prompt


class TestCharacterSheetPrompt:
    def test_includes_description(self):
        prompt = build_character_sheet_prompt("A frustrated commuter in their thirties")
        assert "A frustrated commuter in their thirties" in prompt

    def test_requests_multiple_consistent_views(self):
        """Multiple angles are what make the sheet reusable across scenes."""
        prompt = build_character_sheet_prompt("A commuter")
        assert "three-quarter views of the same person" in prompt
        assert "consistent lighting" in prompt

    def test_uses_neutral_background(self):
        assert "Neutral studio background" in build_character_sheet_prompt("A commuter")

    def test_includes_brand_colours(self):
        prompt = build_character_sheet_prompt("A commuter", brand_colours=["#FFD600"])
        assert "golden yellow" in prompt

    def test_suppresses_text_rendering(self):
        assert "No text" in build_character_sheet_prompt("A commuter")

    def test_truncates_overlong_prompts(self):
        prompt = build_character_sheet_prompt("word " * 800)
        assert len(prompt) <= MAX_PROMPT_CHARS + 1
