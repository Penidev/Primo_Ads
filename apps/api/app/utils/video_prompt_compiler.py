"""Compiles a scene's video prompt for a specific model.

Takes the script's base prompt and layers on brand consistency (colour accents,
tone) plus format hints, then clamps length so providers do not reject it.
Brand colours are expressed as descriptive accents rather than raw hex codes,
which video models handle far better.
"""

import re

MAX_PROMPT_CHARS = 1800

# Common brand hex values mapped to language a video model understands.
_NAMED_HUES: list[tuple[tuple[int, int], str]] = [
    ((0, 15), "deep red"),
    ((16, 40), "warm orange"),
    ((41, 65), "golden yellow"),
    ((66, 160), "vivid green"),
    ((161, 200), "cyan teal"),
    ((201, 250), "electric blue"),
    ((251, 290), "royal violet"),
    ((291, 330), "vibrant magenta"),
    ((331, 360), "crimson pink"),
]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def describe_colour(value: str) -> str | None:
    """Translate a hex colour into a short natural-language descriptor."""
    match = _HEX_RE.match(value.strip())
    if not match:
        # Already a word like "royal blue" — pass it through.
        cleaned = value.strip()
        return cleaned if cleaned and len(cleaned) <= 40 else None

    r, g, b = (int(match.group(1)[i : i + 2], 16) for i in (0, 2, 4))
    high, low = max(r, g, b), min(r, g, b)
    delta = high - low

    if delta < 20:
        if high < 60:
            return "near-black"
        if high > 200:
            return "bright white"
        return "neutral grey"

    if high == r:
        hue = (60 * ((g - b) / delta) + 360) % 360
    elif high == g:
        hue = 60 * ((b - r) / delta) + 120
    else:
        hue = 60 * ((r - g) / delta) + 240

    for (start, end), name in _NAMED_HUES:
        if start <= hue <= end:
            return name
    return None


def compile_prompt(
    base_prompt: str,
    *,
    aspect_ratio: str,
    brand_colours: list[str] | None = None,
    style_notes: str | None = None,
) -> str:
    """Return the final prompt string sent to the video provider."""
    parts: list[str] = [base_prompt.strip()]

    if brand_colours:
        described = [d for d in (describe_colour(c) for c in brand_colours[:3]) if d]
        # Drop duplicates while preserving order.
        unique = list(dict.fromkeys(described))
        if unique:
            accents = " and ".join(unique)
            parts.append(f"Colour accents of {accents} in the lighting and set dressing.")

    if style_notes:
        trimmed = style_notes.strip()
        if trimmed:
            parts.append(trimmed if trimmed.endswith(".") else f"{trimmed}.")

    parts.append(f"{aspect_ratio} aspect ratio.")

    prompt = " ".join(p for p in parts if p)
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS].rsplit(" ", 1)[0].rstrip(",;") + "."
    return prompt
