"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { SceneBlock } from "@/components/timeline/SceneBlock";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { generationApi } from "@/lib/generation-api";

export default function TimelinePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const qc = useQueryClient();
  const [selectedScene, setSelectedScene] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const generation = useQuery({
    queryKey: ["generation", id],
    queryFn: () => generationApi.status(id),
    // Poll while any scene is still in flight; stop once everything settles.
    refetchInterval: (query) => {
      const scenes = query.state.data?.scenes ?? [];
      const busy = scenes.some((s) =>
        ["pending", "generating"].includes(s.generation_status)
      );
      return busy ? 5000 : false;
    },
  });

  const reroll = useMutation({
    mutationFn: (sceneNumber: number) => generationApi.reroll(id, sceneNumber),
    onSuccess: (data) => {
      qc.setQueryData(["generation", id], data);
      qc.invalidateQueries({ queryKey: ["wallet"] });
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Re-roll failed."),
  });

  const scenes = generation.data?.scenes ?? [];
  const completed = scenes.filter((s) => s.generation_status === "completed").length;
  const failed = scenes.filter((s) => s.generation_status === "failed");
  const allDone = scenes.length > 0 && completed === scenes.length;
  const active = scenes.find((s) => s.scene_number === selectedScene) ?? null;

  return (
    <div className="max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Your ad timeline</h1>
          <p className="mt-1 text-sm text-neutral-400">
            {scenes.length > 0
              ? `${completed} of ${scenes.length} scenes ready`
              : "No scenes yet."}
            {generation.data?.selected_model_slug &&
              ` · ${generation.data.selected_model_slug}`}
          </p>
        </div>
        {allDone && (
          <Link href={`/dashboard/projects/${id}/export`}>
            <Button>Export</Button>
          </Link>
        )}
      </div>

      {scenes.length > 0 && (
        <div className="mt-4 h-1.5 rounded bg-neutral-800">
          <div
            className="h-1.5 rounded bg-brand transition-all"
            style={{ width: `${(completed / scenes.length) * 100}%` }}
          />
        </div>
      )}

      {failed.length > 0 && (
        <p className="mt-4 rounded-md border border-red-900/60 bg-red-500/10 p-3 text-sm text-red-300">
          {failed.length} scene{failed.length > 1 ? "s" : ""} failed. Credits for failed
          scenes were refunded automatically. You can re-roll them below.
        </p>
      )}

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      <div className="mt-6 flex gap-3 overflow-x-auto pb-2">
        {scenes.map((scene) => (
          <SceneBlock
            key={scene.id}
            scene={scene}
            isSelected={selectedScene === scene.scene_number}
            onSelect={() => setSelectedScene(scene.scene_number)}
          />
        ))}
      </div>

      {active && (
        <div className="mt-6 rounded-lg border border-neutral-800 p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-medium">Scene {active.scene_number}</h2>
              <p className="mt-1 text-sm text-neutral-400">
                Status: {active.generation_status}
                {active.model_slug && ` · ${active.model_slug}`}
              </p>
              {active.error_message && (
                <p className="mt-2 text-sm text-red-400">{active.error_message}</p>
              )}
            </div>
            <Button
              variant="outline"
              disabled={reroll.isPending || active.generation_status === "generating"}
              onClick={() => reroll.mutate(active.scene_number)}
            >
              {reroll.isPending ? "Re-rolling…" : "Re-roll scene"}
            </Button>
          </div>

          {active.video_url && (
            <video
              key={active.video_url}
              src={active.video_url}
              controls
              className="mt-4 max-h-96 w-full rounded bg-black"
            />
          )}
        </div>
      )}
    </div>
  );
}
