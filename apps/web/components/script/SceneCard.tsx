"use client";

import { useState } from "react";
import type { SceneScript } from "@/types/script";

interface Props {
  scene: SceneScript;
}

function DetailRow({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="grid grid-cols-[130px_1fr] gap-3 py-1.5">
      <span className="text-xs uppercase tracking-wide text-neutral-500">{label}</span>
      <span className="text-sm text-neutral-200">{value}</span>
    </div>
  );
}

export function SceneCard({ scene }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-950/50">
      <div className="flex items-start justify-between gap-4 p-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="rounded bg-brand/20 px-2 py-0.5 text-xs font-medium text-brand-highlight">
              Scene {scene.scene_number}
            </span>
            {scene.scene_label && (
              <span className="text-sm font-medium text-neutral-200">
                {scene.scene_label}
              </span>
            )}
            <span className="text-xs text-neutral-500">{scene.duration_seconds}s</span>
          </div>
          {scene.script_text && (
            <p className="mt-2 text-sm text-neutral-100">&ldquo;{scene.script_text}&rdquo;</p>
          )}
          <p className="mt-2 text-sm text-neutral-400">{scene.visual_description}</p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 text-xs text-neutral-400 hover:text-neutral-200"
          aria-expanded={expanded}
        >
          {expanded ? "Hide details" : "Details"}
        </button>
      </div>

      {expanded && (
        <div className="border-t border-neutral-800 px-4 py-3">
          <DetailRow label="Voiceover" value={scene.voiceover_direction} />
          <DetailRow label="Camera" value={scene.camera_movement} />
          <DetailRow label="Lighting" value={scene.lighting} />
          <DetailRow label="Grading" value={scene.color_grading} />
          <DetailRow label="Audio / SFX" value={scene.audio_sfx} />
          <DetailRow label="Graphics" value={scene.graphics_overlay} />
          <DetailRow label="Brand" value={scene.brand_elements} />

          <div className="mt-3 rounded-md bg-neutral-900 p-3">
            <p className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
              Video model prompt
            </p>
            <p className="text-xs leading-relaxed text-neutral-300">{scene.video_prompt}</p>
          </div>

          {scene.image_gen_needed.length > 0 && (
            <div className="mt-3">
              <p className="mb-1 text-xs uppercase tracking-wide text-neutral-500">
                Assets to generate
              </p>
              <ul className="list-disc pl-5 text-xs text-neutral-400">
                {scene.image_gen_needed.map((asset, i) => (
                  <li key={i}>
                    <span className="text-neutral-300">{asset.asset_type}:</span>{" "}
                    {asset.description}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
