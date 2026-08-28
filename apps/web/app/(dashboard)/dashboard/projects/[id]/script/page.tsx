"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { SceneCard } from "@/components/script/SceneCard";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { scriptApi } from "@/lib/script-api";

export default function ScriptPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const script = useQuery({
    queryKey: ["script", id],
    queryFn: async () => {
      try {
        return await scriptApi.get(id);
      } catch (err) {
        // 404 simply means "not generated yet".
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
  });

  const cost = useQuery({
    queryKey: ["script-cost", id],
    queryFn: () => scriptApi.cost(id),
  });

  const generate = useMutation({
    mutationFn: () => scriptApi.generate(id),
    onSuccess: (data) => {
      qc.setQueryData(["script", id], data);
      qc.invalidateQueries({ queryKey: ["project", id] });
      qc.invalidateQueries({ queryKey: ["wallet"] });
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Generation failed. Try again."),
  });

  const data = script.data;

  return (
    <div className="max-w-3xl">
      {!data && (
        <div className="rounded-lg border border-neutral-800 p-8 text-center">
          <h1 className="text-xl font-semibold">Generate your script</h1>
          <p className="mt-2 text-sm text-neutral-400">
            Your AI director will turn the brief into a scene-by-scene shooting script
            with full creative direction.
          </p>

          {cost.data && (
            <p className="mt-4 text-sm text-neutral-300">
              Cost: <strong>{cost.data.credits_required} credits</strong> (approx. $
              {cost.data.estimated_usd.toFixed(2)}). Your balance:{" "}
              {cost.data.current_balance}.
            </p>
          )}
          {cost.data && !cost.data.sufficient && (
            <p className="mt-2 text-sm text-amber-400">
              You need more credits to generate this script.
            </p>
          )}

          <Button
            className="mt-6"
            onClick={() => generate.mutate()}
            disabled={generate.isPending || (cost.data ? !cost.data.sufficient : false)}
          >
            {generate.isPending ? "Directing your ad…" : "Generate script"}
          </Button>
          {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
        </div>
      )}

      {data && (
        <div>
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">{data.campaign_title}</h1>
              <p className="mt-1 text-sm text-neutral-400">
                {data.scenes.length} scenes · {data.total_duration_seconds}s total
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button
                variant="outline"
                onClick={() => generate.mutate()}
                disabled={generate.isPending}
              >
                {generate.isPending ? "Regenerating…" : "Regenerate"}
              </Button>
              <Link href={`/dashboard/projects/${id}/assets`}>
                <Button>Continue</Button>
              </Link>
            </div>
          </div>

          {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

          <div className="space-y-3">
            {data.scenes.map((scene) => (
              <SceneCard key={scene.scene_number} scene={scene} />
            ))}
          </div>

          <div className="mt-8 rounded-lg border border-neutral-800 p-4">
            <h2 className="mb-3 text-sm font-medium text-neutral-200">Overall direction</h2>
            {data.music_direction && (
              <p className="text-sm text-neutral-400">
                <span className="text-neutral-500">Music:</span> {data.music_direction}
              </p>
            )}
            {data.overall_color_palette && (
              <p className="mt-1 text-sm text-neutral-400">
                <span className="text-neutral-500">Palette:</span>{" "}
                {data.overall_color_palette}
              </p>
            )}
            {data.target_emotion_arc && (
              <p className="mt-1 text-sm text-neutral-400">
                <span className="text-neutral-500">Emotional arc:</span>{" "}
                {data.target_emotion_arc}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
