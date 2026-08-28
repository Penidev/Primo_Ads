"""Video prompt compiler tests — pure logic, no external dependencies."""

from app.utils.video_prompt_compiler import (
    MAX_PROMPT_CHARS,
    compile_prompt,
    describe_colour,
)


class TestDescribeColour:
    def test_maps_blue_hex_to_language(self):
        assert describe_colour("#3400D1") == "royal violet"

    def test_accepts_hex_without_hash(self):
        assert describe_colour("3400D1") == "royal violet"

    def test_maps_yellow(self):
        assert describe_colour("#FFD600") == "golden yellow"

    def test_maps_magenta(self):
        assert describe_colour("#FF007A") == "crimson pink"

    def test_detects_near_black(self):
        assert describe_colour("#000000") == "near-black"

    def test_detects_white(self):
        assert describe_colour("#FFFFFF") == "bright white"

    def test_detects_grey(self):
        assert describe_colour("#808080") == "neutral grey"

    def test_passes_through_plain_words(self):
        assert describe_colour("royal blue") == "royal blue"

    def test_rejects_overlong_free_text(self):
        assert describe_colour("x" * 80) is None

    def test_rejects_empty(self):
        assert describe_colour("   ") is None


class TestCompilePrompt:
    def test_includes_base_prompt(self):
        result = compile_prompt("Close-up of a phone screen", aspect_ratio="9:16")
        assert "Close-up of a phone screen" in result

    def test_always_appends_aspect_ratio(self):
        result = compile_prompt("A shot", aspect_ratio="16:9")
        assert "16:9 aspect ratio." in result

    def test_translates_brand_colours_to_language(self):
        result = compile_prompt(
            "A shot", aspect_ratio="9:16", brand_colours=["#3400D1", "#FFD600"]
        )
        assert "royal violet" in result
        assert "golden yellow" in result
        # Raw hex should not leak into the prompt.
        assert "#3400D1" not in result

    def test_deduplicates_similar_colours(self):
        result = compile_prompt(
            "A shot", aspect_ratio="9:16", brand_colours=["#3400D1", "#3500D2"]
        )
        assert result.count("royal violet") == 1

    def test_limits_to_three_colours(self):
        result = compile_prompt(
            "A shot",
            aspect_ratio="9:16",
            brand_colours=["#FF0000", "#00FF00", "#0000FF", "#FFD600"],
        )
        assert "golden yellow" not in result

    def test_omits_colour_clause_when_none_given(self):
        result = compile_prompt("A shot", aspect_ratio="9:16")
        assert "Colour accents" not in result

    def test_includes_style_notes(self):
        result = compile_prompt(
            "A shot", aspect_ratio="9:16", style_notes="Handheld documentary feel"
        )
        assert "Handheld documentary feel." in result

    def test_does_not_double_punctuate_style_notes(self):
        result = compile_prompt("A shot", aspect_ratio="9:16", style_notes="Moody.")
        assert "Moody.." not in result

    def test_truncates_overlong_prompts(self):
        result = compile_prompt("word " * 1000, aspect_ratio="9:16")
        assert len(result) <= MAX_PROMPT_CHARS + 1

    def test_ignores_unparseable_colours(self):
        result = compile_prompt(
            "A shot", aspect_ratio="9:16", brand_colours=["not-a-colour-" + "x" * 60]
        )
        assert "Colour accents" not in result
