"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { generationApi } from "@/lib/generation-api";

const DOCUMENTS = [
  {
    path: "treatment",
    title: "Director's treatment",
    description: "Full scene-by-scene script with camera, lighting and grading notes.",
    filename: "treatment.md",
  },
  {
    path: "shot-list",
    title: "Shot list (CSV)",
    description: "One row per scene for your camera department or spreadsheet.",
    filename: "shot-list.csv",
  },
  {
    path: "prompts",
    title: "Video prompts",
    description: "The raw generation prompts, for use in any other tool.",
    filename: "prompts.txt",
  },
] as const;

export default function ExportPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [error, setError] = useState<string | null>(null);

  const generation = useQuery({
    queryKey: ["generation", id],
    queryFn: () => generationApi.status(id),
  });

  const downloadDocument = async (path: string, filename: string) => {
    setError(null);
    try {
      // Documents are text; fetch through the proxy so auth cookies apply.
      const response = await fetch(`/api/backend/projects/${id}/export/${path}`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Export failed");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("That export is not available yet. Generate a script first.");
    }
  };

  const downloadVideo = async () => {
    setError(null);
    try {
      // The API returns a short-lived signed URL rather than proxying the file.
      const { url } = await api.get<{ url: string }>(`/projects/${id}/export/video`);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "The final video is not ready yet."
      );
    }
  };

  const hasVideo = Boolean(generation.data?.final_video_url);

  return (
    <div className="max-w-2xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Export</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Download the finished video, or take the script and direction to your own
          production team.
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <section className="rounded-lg border border-neutral-800 p-5">
        <h2 className="font-medium">Finished video</h2>
        <p className="mt-1 text-sm text-neutral-400">
          {hasVideo
            ? "Your stitched master file is ready."
            : "Available once all scenes are generated and stitched."}
        </p>
        <Button className="mt-4" onClick={downloadVideo} disabled={!hasVideo}>
          Download MP4
        </Button>
      </section>

      <section>
        <h2 className="font-medium">Production documents</h2>
        <div className="mt-3 space-y-3">
          {DOCUMENTS.map((doc) => (
            <div
              key={doc.path}
              className="flex items-center justify-between gap-4 rounded-lg border border-neutral-800 p-4"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-neutral-100">{doc.title}</p>
                <p className="mt-0.5 text-xs text-neutral-500">{doc.description}</p>
              </div>
              <Button
                variant="outline"
                onClick={() => downloadDocument(doc.path, doc.filename)}
              >
                Download
              </Button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-medium">Individual scene clips</h2>
        <div className="mt-3 space-y-2">
          {(generation.data?.scenes ?? [])
            .filter((scene) => scene.video_url)
            .map((scene) => (
              <a
                key={scene.id}
                href={scene.video_url ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-md border border-neutral-800 px-4 py-2 text-sm text-neutral-300 hover:border-neutral-600"
              >
                Scene {scene.scene_number}
                {scene.duration_seconds ? ` · ${scene.duration_seconds}s` : ""}
              </a>
            ))}
          {(generation.data?.scenes ?? []).every((s) => !s.video_url) && (
            <p className="text-sm text-neutral-500">
              Scene clips appear here once generation completes.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
