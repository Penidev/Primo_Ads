"""Builds image prompts for scene reference assets.

Brand colours are described in words (video and image models handle language far
better than hex codes), and a consistent style suffix keeps every asset in a
project visually coherent.
"""

from app.utils.video_prompt_compiler import describe_colour

MAX_PROMPT_CHARS = 1200

# Applied to every asset so a project's references share a look.
_QUALITY_SUFFIX = "High detail, professional commercial photography, clean composition."

# Character sheets need explicit framing to be reusable across scenes.
_CHARACTER_SUFFIX = (
    "Neutral studio background, consistent lighting, front-facing and "
    "three-quarter views of the same person, full head and shoulders visible."
)


def _colour_clause(brand_colours: list[str] | None, limit: int = 3) -> str | None:
    if not brand_colours:
        return None
    described = [d for d in (describe_colour(c) for c in brand_colours[:limit]) if d]
    unique = list(dict.fromkeys(described))
    if not unique:
        return None
    return f"Colour palette of {' and '.join(unique)}."


def build_asset_prompt(
    description: str,
    *,
    asset_type: str | None = None,
    style: str | None = None,
    brand_colours: list[str] | None = None,
    brand_name: str | None = None,
    voice_tone: list[str] | None = None,
) -> str:
    """Compose the prompt for a single scene reference asset."""
    parts: list[str] = [description.strip()]

    if style:
        trimmed = style.strip()
        if trimmed:
            parts.append(trimmed if trimmed.endswith(".") else f"{trimmed}.")

    colour = _colour_clause(brand_colours)
    if colour:
        parts.append(colour)

    if voice_tone:
        tones = ", ".join(t.strip().lower() for t in voice_tone[:3] if t.strip())
        if tones:
            parts.append(f"Overall mood: {tones}.")

    # Product shots should read as the brand's own asset, without inventing a logo.
    if asset_type and asset_type.lower() in ("product", "product_shot", "packaging"):
        parts.append("Product presented cleanly as a hero shot, no text or logos rendered.")
    else:
        parts.append("No text, no watermarks, no logos rendered in the image.")

    parts.append(_QUALITY_SUFFIX)

    prompt = " ".join(p for p in parts if p)
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS].rsplit(" ", 1)[0].rstrip(",;") + "."
    return prompt


def build_character_sheet_prompt(
    description: str,
    *,
    brand_colours: list[str] | None = None,
    voice_tone: list[str] | None = None,
) -> str:
    """Compose a reusable character reference so a person stays consistent."""
    parts: list[str] = [description.strip(), _CHARACTER_SUFFIX]

    colour = _colour_clause(brand_colours, limit=2)
    if colour:
        parts.append(colour)
    if voice_tone:
        tones = ", ".join(t.strip().lower() for t in voice_tone[:2] if t.strip())
        if tones:
            parts.append(f"Overall mood: {tones}.")

    parts.append("No text, no watermarks, no logos rendered in the image.")
    parts.append(_QUALITY_SUFFIX)

    prompt = " ".join(p for p in parts if p)
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS].rsplit(" ", 1)[0].rstrip(",;") + "."
    return prompt
