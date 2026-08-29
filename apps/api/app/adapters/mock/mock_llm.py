"""Mock LLM adapter.

Returns schema-valid output for the same prompts the live adapter handles, so the
strict validation in `ScriptService` and `SwipeFileService` runs for real. Output
is deterministic (seeded from the input) so tests are stable.

Failure injection: include the token ``__FAIL_LLM__`` anywhere in the user
content to raise `LLMRequestError`, which exercises the provider-failure path.
"""

import hashlib
import json
import re
from typing import Any

from app.adapters.llm.base import LLMAdapter
from app.adapters.llm.gemini import LLMRequestError

FAIL_TOKEN = "__FAIL_LLM__"  # noqa: S105 - a marker string, not a credential
EMBEDDING_DIM = 1536

_SCENE_TEMPLATES = [
    ("The Hook", "Open on the friction the audience already recognises."),
    ("The Agitation", "Let the cost of that friction land."),
    ("The Reveal", "Introduce the product as the effortless alternative."),
    ("The Payoff", "Show the outcome the audience wants."),
    ("The Call to Action", "State the single next step plainly."),
]

_CAMERA = [
    "Slow push-in, shallow depth of field",
    "Handheld medium shot, subtle movement",
    "Macro tracking shot across the product",
    "Static tripod, centred composition",
    "Slow pull-out revealing the wider scene",
]


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def _extract(pattern: str, text: str, fallback: str) -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else fallback


class MockLLMAdapter(LLMAdapter):
    """Deterministic stand-in for the Gemini adapter."""

    def _guard(self, user_content: str) -> None:
        if FAIL_TOKEN in user_content:
            raise LLMRequestError("Mock LLM failure requested via test token.")

    async def generate_json(
        self,
        system_instruction: str,
        user_content: str,
        *,
        temperature: float = 0.8,
        max_output_tokens: int = 8192,
    ) -> str:
        self._guard(user_content)

        brand = _extract(r'"name"\s*:\s*"([^"]{1,80})"', user_content, "Your Brand")
        product = _extract(
            r'"product"\s*:\s*\{[^}]*?"name"\s*:\s*"([^"]{1,80})"',
            user_content,
            "the product",
        )
        aspect_ratio = _extract(r'"aspect_ratio"\s*:\s*"([^"]{1,10})"', user_content, "9:16")
        try:
            target = int(_extract(r'"target_duration_seconds"\s*:\s*(\d{1,3})', user_content, "30"))
        except ValueError:
            target = 30

        # Build whole scenes that sum exactly to the target duration, because the
        # live prompt requires that and downstream code relies on it.
        scene_count = max(2, min(len(_SCENE_TEMPLATES), target // 6 or 2))
        base = target // scene_count
        remainder = target - (base * scene_count)

        seed = _seed(user_content)
        scenes: list[dict[str, Any]] = []
        for index in range(scene_count):
            label, intent = _SCENE_TEMPLATES[index % len(_SCENE_TEMPLATES)]
            duration = base + (1 if index < remainder else 0)
            scenes.append(
                {
                    "scene_number": index + 1,
                    "scene_label": label,
                    "duration_seconds": duration,
                    "script_text": f"{intent}",
                    "voiceover_direction": "Calm, confident, unhurried delivery.",
                    "visual_description": (
                        f"{label}: a considered shot establishing {product} for {brand}."
                    ),
                    "camera_movement": _CAMERA[(seed + index) % len(_CAMERA)],
                    "color_grading": "Cool shadows warming toward the resolution",
                    "lighting": "Soft key with a controlled falloff",
                    "audio_sfx": "Restrained ambience with a single accent hit",
                    "graphics_overlay": None,
                    "brand_elements": (
                        f"{brand} appears in the final beat" if index == scene_count - 1 else None
                    ),
                    "video_prompt": (
                        f"{_CAMERA[(seed + index) % len(_CAMERA)]} of a scene "
                        f"establishing {product}. Soft key lighting, cool graded "
                        f"shadows, restrained ambience. {aspect_ratio} aspect ratio."
                    ),
                    "image_gen_needed": (
                        [
                            {
                                "asset_type": "background",
                                "description": f"Environment for {label.lower()} of the {brand} ad",
                                "style": "photorealistic",
                            }
                        ]
                        if index % 2 == 0
                        else []
                    ),
                }
            )

        return json.dumps(
            {
                "campaign_title": f"{brand}: {_SCENE_TEMPLATES[seed % len(_SCENE_TEMPLATES)][0]}",
                "total_duration_seconds": sum(s["duration_seconds"] for s in scenes),
                "scenes": scenes,
                "music_direction": "Sparse percussion building to a single resolve",
                "overall_color_palette": "Cool neutrals resolving to brand accents",
                "target_emotion_arc": "recognition to relief to confidence",
            }
        )

    async def analyze_video_json(
        self,
        system_instruction: str,
        user_content: str,
        video_bytes: bytes,
        mime_type: str,
        *,
        temperature: float = 0.3,
        max_output_tokens: int = 8192,
    ) -> str:
        self._guard(user_content)

        seed = _seed(str(len(video_bytes)) + user_content)
        categories = [
            "problem-agitation-solution",
            "us-vs-competitor",
            "social-proof",
            "high-energy-disruptor",
            "emotional-storytelling",
            "product-demo",
        ]
        category = _extract(
            r'"category_hint"\s*:\s*"([^"]{1,60})"',
            user_content,
            categories[seed % len(categories)],
        )
        industry = _extract(r'"industry_hint"\s*:\s*"([^"]{1,60})"', user_content, "General")

        beats = []
        for index in range(3):
            label, intent = _SCENE_TEMPLATES[index]
            beats.append(
                {
                    "beat_number": index + 1,
                    "label": label,
                    "start_second": float(index * 5),
                    "end_second": float((index + 1) * 5),
                    "narrative_function": intent,
                    "visual_technique": _CAMERA[(seed + index) % len(_CAMERA)],
                    "message_intent": "Communicates the beat's purpose without quoting copy.",
                }
            )

        return json.dumps(
            {
                "suggested_title": f"{category} pattern ({industry})",
                "industry": industry,
                "ad_category": category,
                "psychological_triggers": ["friction relief", "social proof"],
                "hook_style": "Opens on a recognisable frustration",
                "pacing": "moderate",
                "duration_seconds": 15,
                "format": "9:16",
                "color_palette": ["cool blue", "warm amber"],
                "camera_techniques": _CAMERA[:3],
                "beats": beats,
                "why_it_works": (
                    "It earns attention with a familiar problem before asking for any."
                ),
                "reusable_pattern": (
                    "Open on friction, quantify the cost, resolve with one gesture."
                ),
            }
        )

    async def embed(self, text: str) -> list[float]:
        """Deterministic pseudo-embedding with a stable magnitude.

        Similar text yields similar vectors, so pgvector ordering behaves
        sensibly in tests without calling a real embedding model.
        """
        digest = hashlib.sha512(text.encode()).digest()
        # Repeat and normalise the digest to fill the expected dimensionality.
        raw = (digest * ((EMBEDDING_DIM // len(digest)) + 1))[:EMBEDDING_DIM]
        return [((byte / 255.0) * 2.0) - 1.0 for byte in raw]
