"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ModelSelector } from "@/components/models/ModelSelector";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { generationApi } from "@/lib/generation-api";
import { projectApi } from "@/lib/project-api";
import type { Brief } from "@/types/brief";

export default function GeneratePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const project = useQuery({
    queryKey: ["project", id],
    queryFn: () => projectApi.get(id),
  });

  const brief = (project.data?.brief ?? {}) as Brief;
  const aspectRatio = brief.campaign?.format ?? "9:16";

  const start = useMutation({
    mutationFn: (slug: string) => generationApi.start(id, slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wallet"] });
      qc.invalidateQueries({ queryKey: ["generation", id] });
      router.push(`/dashboard/projects/${id}/timeline`);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not start generation."),
  });

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold">Choose your video engine</h1>
      <p className="mt-2 text-sm text-neutral-400">
        Each engine has different strengths and credit rates. Cost is shown per engine
        for this project&apos;s scenes.
      </p>

      <div className="mt-6">
        <ModelSelector
          projectId={id}
          aspectRatio={aspectRatio}
          selected={selected}
          onSelect={(slug) => {
            setSelected(slug);
            setError(null);
          }}
        />
      </div>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      <div className="mt-8 flex items-center gap-3">
        <Button
          disabled={!selected || start.isPending}
          onClick={() => selected && start.mutate(selected)}
        >
          {start.isPending ? "Starting generation…" : "Generate video"}
        </Button>
        <span className="text-xs text-neutral-500">
          Credits are charged when generation starts. Failed scenes are refunded
          automatically.
        </span>
      </div>
    </div>
  );
}
