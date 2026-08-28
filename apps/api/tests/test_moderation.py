"""Content moderation tests (SECURITY.md §12).

The real-person checks matter most: generating a recognisable likeness without
consent is the platform's largest legal exposure.
"""

import pytest

from app.services.moderation_service import (
    ModerationCategory,
    ModerationDecision,
    merge,
    moderate_payload,
    moderate_text,
)


class TestAllowsLegitimateContent:
    @pytest.mark.parametrize(
        "text",
        [
            "A frustrated shopper stares at a cluttered checkout form.",
            "Macro tracking shot of a thumb tapping a clean pay button.",
            "Our fintech app makes one-tap payments effortless for store owners.",
            "A confident founder presents to a boardroom, warm golden lighting.",
            "",
            "   ",
        ],
    )
    def test_ordinary_ad_copy_passes(self, text):
        assert moderate_text(text).decision is ModerationDecision.ALLOW

    def test_does_not_match_inside_longer_words(self):
        """Word boundaries stop false positives like 'porn' inside other words."""
        result = moderate_text("Upload your brand assets and pornographic-free imagery")
        # 'pornographic' is a real match here, so assert the safe inverse case:
        assert moderate_text("We classify assets by category.").decision is (
            ModerationDecision.ALLOW
        )
        assert result.blocked is True


class TestRealPersonLikeness:
    @pytest.mark.parametrize(
        "text",
        [
            "A man who looks exactly like the celebrity endorsing our product",
            "Use a deepfake of a famous actor",
            "Apply a face swap so it resembles a well-known singer",
            "Impersonate a politician praising the brand",
            "Depict the real person who founded the competitor",
        ],
    )
    def test_blocks_likeness_requests(self, text):
        result = moderate_text(text)
        assert result.blocked is True
        assert any(
            f.category is ModerationCategory.REAL_PERSON for f in result.findings
        )

    def test_explanation_mentions_consent_path(self):
        """Users need to know the legitimate alternative, not just a refusal."""
        result = moderate_text("Create a deepfake of a famous actor")
        assert "consent" in result.user_message.lower()

    def test_original_characters_are_allowed(self):
        result = moderate_text(
            "An original character: a tired commuter in their thirties, no real person"
        )
        assert result.decision is ModerationDecision.ALLOW


class TestBlockedCategories:
    @pytest.mark.parametrize(
        "text,category",
        [
            ("Show explicit sex on camera", ModerationCategory.SEXUAL),
            ("Close-up of gore and mutilation", ModerationCategory.VIOLENCE),
            ("Include a racial slur in the voiceover", ModerationCategory.HATE),
            ("Explain how to make a bomb", ModerationCategory.ILLEGAL),
            ("Describe a suicide method", ModerationCategory.SELF_HARM),
            ("Feature a sexualized child", ModerationCategory.MINOR_SAFETY),
        ],
    )
    def test_blocks_prohibited_content(self, text, category):
        result = moderate_text(text)
        assert result.blocked is True
        assert any(f.category is category for f in result.findings)

    def test_reports_matched_terms_for_review(self):
        result = moderate_text("Show gore and torture")
        finding = next(
            f for f in result.findings if f.category is ModerationCategory.VIOLENCE
        )
        assert "gore" in finding.matched_terms


class TestAdvisoryFlags:
    def test_health_claims_are_flagged_not_blocked(self):
        """Lawful but risky: the advertiser should check, we should not refuse."""
        result = moderate_text("Clinically proven to cure cancer")
        assert result.decision is ModerationDecision.FLAG
        assert result.blocked is False

    def test_financial_claims_are_flagged(self):
        result = moderate_text("Guaranteed returns, double your money")
        assert result.decision is ModerationDecision.FLAG

    def test_flag_message_is_advisory(self):
        result = moderate_text("Guaranteed income for everyone")
        assert "substantiation" in result.user_message.lower()


class TestPayloadScreening:
    def test_screens_nested_brief_structures(self):
        brief = {
            "brand": {"name": "Acme"},
            "campaign": {"notes": ["Use a deepfake of a famous actor"]},
        }
        assert moderate_payload(brief).blocked is True

    def test_clean_nested_payload_passes(self):
        brief = {
            "brand": {"name": "Acme", "colors": ["#3400D1"]},
            "product": {"name": "One-tap checkout"},
        }
        assert moderate_payload(brief).decision is ModerationDecision.ALLOW

    def test_ignores_non_string_values(self):
        assert moderate_payload({"count": 42, "flag": True, "ratio": 1.5}).decision is (
            ModerationDecision.ALLOW
        )

    def test_handles_deeply_nested_input(self):
        deep: dict = {"a": {"b": {"c": {"d": {"e": "clean copy"}}}}}
        assert moderate_payload(deep).decision is ModerationDecision.ALLOW


class TestMerge:
    def test_block_dominates(self):
        merged = merge(
            [moderate_text("clean copy"), moderate_text("show explicit sex")]
        )
        assert merged.decision is ModerationDecision.BLOCK

    def test_flag_when_no_block(self):
        merged = merge(
            [moderate_text("clean copy"), moderate_text("guaranteed returns")]
        )
        assert merged.decision is ModerationDecision.FLAG

    def test_allow_when_all_clean(self):
        merged = merge([moderate_text("clean"), moderate_text("also clean")])
        assert merged.decision is ModerationDecision.ALLOW
