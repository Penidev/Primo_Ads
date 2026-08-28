"use client";

import { useQuery } from "@tanstack/react-query";
import { generationApi } from "@/lib/generation-api";
import type { VideoModelPublic } from "@/types/generation";

interface Props {
  projectId: string;
  aspectRatio?: string;
  requiresAudio?: boolean;
  selected: string | null;
  onSelect: (slug: string) => void;
}

const TIER_LABEL: Record<string, string> = {
  budget: "Budget",
  standard: "Standard",
  premium: "Premium",
};

function tierStyle(tier: string | null): string {
  if (tier === "premium") return "bg-amber-500/20 text-amber-300";
  if (tier === "budget") return "bg-emerald-500/20 text-emerald-300";
  return "bg-neutral-700/50 text-neutral-300";
}

function ModelCard({
  model,
  projectId,
  isSelected,
  onSelect,
}: {
  model: VideoModelPublic;
  projectId: string;
  isSelected: boolean;
  onSelect: () => void;
}) {
  // Cost is computed server-side from admin-managed pricing.
  const { data: cost } = useQuery({
    queryKey: ["model-cost", model.slug, projectId],
    queryFn: () => generationApi.modelCost(model.slug, projectId),
    retry: false,
  });

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={isSelected}
      className={`rounded-lg border p-4 text-left transition ${
        isSelected
          ? "border-brand bg-brand/10"
          : "border-neutral-800 hover:border-neutral-600"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-neutral-100">
          {model.display_name ?? model.slug}
        </span>
        {model.quality_tier && (
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] ${tierStyle(model.quality_tier)}`}
          >
            {TIER_LABEL[model.quality_tier] ?? model.quality_tier}
          </span>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-neutral-500">
        {model.supports_audio && <span>Native audio</span>}
        {model.supports_image_reference && <span>· Brand references</span>}
        {model.max_duration_seconds && <span>· up to {model.max_duration_seconds}s/scene</span>}
      </div>

      <div className="mt-3 text-sm">
        {cost ? (
          <>
            <span className="font-medium text-neutral-100">
              {cost.credits_required} credits
            </span>
            <span className="text-neutral-500">
              {" "}
              (~${cost.estimated_usd.toFixed(2)}) for {cost.scene_count} scenes
            </span>
            {!cost.sufficient && (
              <p className="mt-1 text-xs text-amber-400">Not enough credits</p>
            )}
          </>
        ) : (
          <span className="text-neutral-500">Calculating cost…</span>
        )}
      </div>
    </button>
  );
}

export function ModelSelector({
  projectId,
  aspectRatio,
  requiresAudio,
  selected,
  onSelect,
}: Props) {
  const { data: models, isLoading } = useQuery({
    queryKey: ["video-models", aspectRatio, requiresAudio],
    queryFn: () => generationApi.listModels({ aspectRatio, requiresAudio }),
  });

  if (isLoading) return <p className="text-neutral-500">Loading engines…</p>;
  if (!models || models.length === 0) {
    return <p className="text-neutral-500">No video engines are available right now.</p>;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {models.map((model) => (
        <ModelCard
          key={model.slug}
          model={model}
          projectId={projectId}
          isSelected={selected === model.slug}
          onSelect={() => onSelect(model.slug)}
        />
      ))}
    </div>
  );
}
