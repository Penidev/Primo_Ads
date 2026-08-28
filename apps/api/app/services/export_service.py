"""Script export for users who produce the ad with their own crew.

Generates a director's treatment (Markdown) and a camera shot list (CSV) from a
stored script. Both are plain text, so no rendering dependency is required and
the output can be opened in any editor, Google Docs, or a spreadsheet.
"""

import csv
import io

from app.schemas.script import GeneratedScript


def _line(label: str, value: str | None) -> str:
    return f"**{label}:** {value}\n\n" if value else ""


def to_markdown(script: GeneratedScript, brand_name: str | None = None) -> str:
    """Render a director's treatment."""
    out = io.StringIO()
    out.write(f"# {script.campaign_title}\n\n")
    if brand_name:
        out.write(f"**Brand:** {brand_name}\n\n")
    out.write(f"**Total runtime:** {script.total_duration_seconds}s  \n")
    out.write(f"**Scenes:** {len(script.scenes)}\n\n")

    if script.target_emotion_arc:
        out.write(f"**Emotional arc:** {script.target_emotion_arc}\n\n")
    if script.overall_color_palette:
        out.write(f"**Colour palette:** {script.overall_color_palette}\n\n")
    if script.music_direction:
        out.write(f"**Music:** {script.music_direction}\n\n")

    out.write("---\n\n")

    for scene in script.scenes:
        heading = f"## Scene {scene.scene_number}"
        if scene.scene_label:
            heading += f" — {scene.scene_label}"
        out.write(f"{heading} ({scene.duration_seconds}s)\n\n")

        if scene.script_text:
            out.write(f"> {scene.script_text}\n\n")

        out.write(_line("Visual", scene.visual_description))
        out.write(_line("Camera", scene.camera_movement))
        out.write(_line("Lighting", scene.lighting))
        out.write(_line("Colour grading", scene.color_grading))
        out.write(_line("Voiceover", scene.voiceover_direction))
        out.write(_line("Audio / SFX", scene.audio_sfx))
        out.write(_line("Graphics", scene.graphics_overlay))
        out.write(_line("Brand elements", scene.brand_elements))

        if scene.image_gen_needed:
            out.write("**Assets required:**\n\n")
            for asset in scene.image_gen_needed:
                style = f" ({asset.style})" if asset.style else ""
                out.write(f"- {asset.asset_type}: {asset.description}{style}\n")
            out.write("\n")

        out.write("---\n\n")

    return out.getvalue()


def to_shot_list_csv(script: GeneratedScript) -> str:
    """Render a shot list for the camera department."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "Scene",
            "Label",
            "Duration (s)",
            "Shot / Camera",
            "Lighting",
            "Grading",
            "Action / Visual",
            "Dialogue / VO",
            "Audio",
        ]
    )
    for scene in script.scenes:
        writer.writerow(
            [
                scene.scene_number,
                scene.scene_label or "",
                scene.duration_seconds,
                scene.camera_movement or "",
                scene.lighting or "",
                scene.color_grading or "",
                scene.visual_description,
                scene.script_text or "",
                scene.audio_sfx or "",
            ]
        )
    return buffer.getvalue()


def to_prompt_list(script: GeneratedScript) -> str:
    """Plain-text prompts, for users who want to run them on another tool."""
    lines: list[str] = [f"{script.campaign_title}", ""]
    for scene in script.scenes:
        lines.append(f"Scene {scene.scene_number} ({scene.duration_seconds}s)")
        lines.append(scene.video_prompt)
        lines.append("")
    return "\n".join(lines)
