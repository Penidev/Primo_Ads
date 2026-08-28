"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { projectApi } from "@/lib/project-api";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  scripted: "Scripted",
  assets_ready: "Assets ready",
  generating: "Generating",
  completed: "Completed",
  failed: "Failed",
};

export default function ProjectsPage() {
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectApi.list(),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Your projects</h1>
        <Link href="/dashboard/projects/new">
          <Button>Create new ad</Button>
        </Link>
      </div>

      {isLoading && <p className="text-neutral-500">Loading…</p>}

      {!isLoading && (!projects || projects.length === 0) && (
        <div className="rounded-lg border border-dashed border-neutral-800 p-12 text-center">
          <p className="text-neutral-400">No projects yet.</p>
          <Link href="/dashboard/projects/new">
            <Button className="mt-4">Create your first ad</Button>
          </Link>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects?.map((p) => (
          <Link
            key={p.id}
            href={`/dashboard/projects/${p.id}`}
            className="rounded-lg border border-neutral-800 p-4 hover:border-neutral-600 transition"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium truncate">{p.title || "Untitled project"}</span>
              <span className="text-xs rounded-full bg-neutral-800 px-2 py-0.5 text-neutral-300">
                {STATUS_LABELS[p.status] ?? p.status}
              </span>
            </div>
            <p className="mt-3 text-xs text-neutral-500">
              {p.total_credits_spent} credits · updated{" "}
              {new Date(p.updated_at).toLocaleDateString()}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
