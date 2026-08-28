"""Blueprint analysis prompt tests — pure logic, no dependencies.

The instruction text carries the legal guardrails for the swipe file, so these
assertions are deliberately about content, not just structure.
"""

from app.utils.blueprint_prompt import (
    ANALYSIS_SYSTEM_INSTRUCTION,
    build_analysis_request,
    build_embedding_text,
)


class TestAnalysisInstruction:
    def test_requests_json_only(self):
        assert "JSON" in ANALYSIS_SYSTEM_INSTRUCTION
        assert "no markdown fences" in ANALYSIS_SYSTEM_INSTRUCTION.lower()

    def test_forbids_transcription(self):
        """No verbatim copy may be extracted from a reference ad."""
        lowered = ANALYSIS_SYSTEM_INSTRUCTION.lower()
        assert "do not transcribe" in lowered
        assert "paraphrase" in lowered

    def test_forbids_naming_the_brand(self):
        lowered = ANALYSIS_SYSTEM_INSTRUCTION.lower()
        assert "do not name the advertised brand" in lowered

    def test_forbids_recreating_identifiable_people(self):
        lowered = ANALYSIS_SYSTEM_INSTRUCTION.lower()
        assert "identifiable people" in lowered

    def test_lists_every_supported_category(self):
        for category in (
            "problem-agitation-solution",
            "us-vs-competitor",
            "social-proof",
            "high-energy-disruptor",
            "emotional-storytelling",
            "product-demo",
        ):
            assert category in ANALYSIS_SYSTEM_INSTRUCTION


class TestAnalysisRequest:
    def test_bare_request_has_no_hint_block(self):
        content = build_analysis_request()
        assert "CURATOR HINTS" not in content

    def test_industry_hint_included(self):
        content = build_analysis_request(industry_hint="Fintech")
        assert "CURATOR HINTS" in content
        assert "Fintech" in content

    def test_category_hint_included(self):
        content = build_analysis_request(category_hint="social-proof")
        assert "social-proof" in content

    def test_hints_are_marked_as_overridable(self):
        content = build_analysis_request(industry_hint="Fintech")
        assert "correct them if the video disagrees" in content


class TestEmbeddingText:
    def _analysis(self) -> dict:
        return {
            "ad_category": "problem-agitation-solution",
            "industry": "Fintech",
            "hook_style": "Relatable frustration in the first two seconds",
            "pacing": "fast",
            "psychological_triggers": ["loss aversion", "friction relief"],
            "camera_techniques": ["macro tracking", "slow push-in"],
            "color_palette": ["cold blue", "warm violet"],
            "beats": [
                {"label": "Hook", "narrative_function": "Surface the pain"},
                {"label": "Reveal", "narrative_function": "Introduce the fix"},
            ],
            "why_it_works": "It dramatises a familiar cost of inaction.",
            "reusable_pattern": "Open on friction, resolve with one gesture.",
        }

    def test_includes_structural_fields(self):
        text = build_embedding_text(self._analysis())
        assert "Category: problem-agitation-solution" in text
        assert "Industry: Fintech" in text
        assert "Pacing: fast" in text

    def test_flattens_lists(self):
        text = build_embedding_text(self._analysis())
        assert "loss aversion, friction relief" in text

    def test_summarises_beats(self):
        text = build_embedding_text(self._analysis())
        assert "Hook: Surface the pain" in text
        assert "Reveal: Introduce the fix" in text

    def test_includes_reasoning_fields(self):
        text = build_embedding_text(self._analysis())
        assert "familiar cost of inaction" in text
        assert "resolve with one gesture" in text

    def test_skips_empty_values(self):
        text = build_embedding_text({"ad_category": "social-proof", "industry": ""})
        assert "Industry:" not in text

    def test_handles_empty_analysis(self):
        assert build_embedding_text({}) == ""

    def test_ignores_malformed_beats(self):
        text = build_embedding_text({"beats": ["not-a-dict"], "pacing": "fast"})
        assert "Pacing: fast" in text
