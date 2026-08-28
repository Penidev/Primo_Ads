"""Prompt for deconstructing a reference advertisement into a blueprint.

The instruction is written to extract *transferable structure* rather than
reproducible content: no transcripts, no brand names carried forward, no
character or mascot descriptions. This keeps the library legally defensible and
keeps generated ads original (Requirement 6.5, SECURITY.md §12).
"""

import json
from typing import Any

ANALYSIS_SYSTEM_INSTRUCTION = """\
You are an advertising strategist who reverse-engineers commercials into
reusable creative frameworks.

Watch the supplied video and deconstruct HOW it works. Return ONLY a single JSON
object with this exact shape:
{
  "suggested_title": short descriptive label for this pattern (not the brand name),
  "industry": the sector, e.g. "Fintech", "E-commerce", "FMCG",
  "ad_category": one of "problem-agitation-solution", "us-vs-competitor",
                 "social-proof", "high-energy-disruptor", "emotional-storytelling",
                 "product-demo",
  "psychological_triggers": array of mechanisms used, e.g. ["loss aversion", "social proof"],
  "hook_style": how the first three seconds capture attention,
  "pacing": one of "fast", "moderate", "slow-build",
  "duration_seconds": integer total runtime,
  "format": "9:16", "16:9", or "1:1",
  "color_palette": array of colour descriptions in plain words,
  "camera_techniques": array of shot and movement types in standard film vocabulary,
  "beats": [
    {
      "beat_number": integer starting at 1,
      "label": the beat's role, e.g. "Hook", "Agitation", "Reveal", "CTA",
      "start_second": number,
      "end_second": number,
      "narrative_function": what this beat does for the argument,
      "visual_technique": how it is shot and edited,
      "message_intent": the PURPOSE of what is communicated, paraphrased
    }
  ],
  "why_it_works": analysis of the persuasion mechanics,
  "reusable_pattern": how another brand in another sector could apply this
                      structure, described abstractly
}

Hard rules:
- Do NOT transcribe dialogue, voiceover, taglines, or on-screen copy. Paraphrase
  intent only ("introduces the product as the effortless option"), never wording.
- Do NOT name the advertised brand, its products, mascots, celebrities, or any
  music track. Refer to "the brand" and "the product".
- Do NOT describe identifiable people in a way that could be used to recreate
  them. Describe roles instead ("a frustrated commuter").
- Beat timings must be non-overlapping and ascending, and must stay within the
  video's runtime.
- Output raw JSON only. No markdown fences, no commentary.
"""


def build_analysis_request(
    industry_hint: str | None = None,
    category_hint: str | None = None,
) -> str:
    """User-turn content for the analysis call."""
    sections = [
        "Deconstruct this advertisement into a reusable creative framework.",
    ]
    hints: dict[str, Any] = {}
    if industry_hint:
        hints["industry_hint"] = industry_hint
    if category_hint:
        hints["category_hint"] = category_hint
    if hints:
        sections += [
            "",
            "CURATOR HINTS (treat as suggestions; correct them if the video disagrees)",
            json.dumps(hints, ensure_ascii=False),
        ]
    return "\n".join(sections)


def build_embedding_text(analysis: dict[str, Any]) -> str:
    """Flatten a blueprint into the text used to build its embedding vector.

    Only the structural fields are included, so similarity search matches on
    strategy and pattern rather than on any specific brand's wording.
    """
    parts: list[str] = []

    def add(label: str, value: Any) -> None:
        if not value:
            return
        if isinstance(value, list):
            joined = ", ".join(str(v) for v in value if v)
            if joined:
                parts.append(f"{label}: {joined}")
        else:
            parts.append(f"{label}: {value}")

    add("Category", analysis.get("ad_category"))
    add("Industry", analysis.get("industry"))
    add("Hook style", analysis.get("hook_style"))
    add("Pacing", analysis.get("pacing"))
    add("Psychological triggers", analysis.get("psychological_triggers"))
    add("Camera techniques", analysis.get("camera_techniques"))
    add("Colour palette", analysis.get("color_palette"))

    beats = analysis.get("beats") or []
    if isinstance(beats, list):
        beat_summary = " | ".join(
            f"{b.get('label', '')}: {b.get('narrative_function', '')}"
            for b in beats
            if isinstance(b, dict)
        )
        add("Structure", beat_summary)

    add("Why it works", analysis.get("why_it_works"))
    add("Reusable pattern", analysis.get("reusable_pattern"))
    return "\n".join(parts)
