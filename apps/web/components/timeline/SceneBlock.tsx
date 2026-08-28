"use client";

import type { ScenePublic } from "@/types/generation";

const STATUS_STYLE: Record<string, string> = {
  completed: "border-emerald-600/60 bg-emerald-500/10",
  generating: "border-brand/60 bg-brand/10 animate-pulse",
  failed: "border-red-600/60 bg-red-500/10",
  pending: "border-neutral-700 bg-neutral-900/40",
};

const STATUS_LABEL: Record<string, string> = {
  completed: "Ready",
  generating: "Generating…",
  failed: "Failed",
  pending: "Queued",
};

interface Props {
  scene: ScenePublic;
  isSelected: boolean;
  onSelect: () => void;
}

export function SceneBlock({ scene, isSelected, onSelect }: Props) {
  const style = STATUS_STYLE[scene.generation_status] ?? STATUS_STYLE.pending;

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={isSelected}
      aria-label={`Scene ${scene.scene_number}, ${
        STATUS_LABEL[scene.generation_status] ?? scene.generation_status
      }`}
      className={`w-36 shrink-0 rounded-lg border p-3 text-left transition ${style} ${
        isSelected ? "ring-2 ring-brand" : ""
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-neutral-200">
          Scene {scene.scene_number}
        </span>
        {scene.duration_seconds && (
          <span className="text-[11px] text-neutral-500">{scene.duration_seconds}s</span>
        )}
      </div>

      <div className="mt-2 aspect-[9/16] max-h-24 overflow-hidden rounded bg-neutral-950">
        {scene.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={scene.thumbnail_url}
            alt={`Scene ${scene.scene_number} preview`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[11px] text-neutral-600">
            {STATUS_LABEL[scene.generation_status] ?? scene.generation_status}
          </div>
        )}
      </div>

      <p className="mt-2 truncate text-[11px] text-neutral-500">
        {STATUS_LABEL[scene.generation_status] ?? scene.generation_status}
      </p>
    </button>
  );
}
