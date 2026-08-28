"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { BriefWizard } from "@/components/brief/BriefWizard";
import { projectApi } from "@/lib/project-api";
import type { Brief } from "@/types/brief";

/**
 * Project entry point. Reads the project's status and sends the user to the
 * step they left off at (Requirement 12.2); drafts continue in the wizard.
 */
export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const { data: project, isLoading, isError } = useQuery({
    queryKey: ["project", id],
    queryFn: () => projectApi.get(id),
  });

  useEffect(() => {
    if (!project) return;
    const target: Record<string, string> = {
      scripted: `/dashboard/projects/${id}/script`,
      assets_ready: `/dashboard/projects/${id}/generate`,
      generating: `/dashboard/projects/${id}/timeline`,
      completed: `/dashboard/projects/${id}/export`,
      failed: `/dashboard/projects/${id}/timeline`,
    };
    const next = target[project.status];
    if (next) router.replace(next);
  }, [project, id, router]);

  if (isLoading) return <p className="text-neutral-500">Loading project…</p>;
  if (isError || !project) return <p className="text-red-400">Project not found.</p>;

  if (project.status !== "draft") {
    return <p className="text-neutral-500">Opening your project…</p>;
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">
        {project.title || "Untitled project"}
      </h1>
      <BriefWizard
        projectId={id}
        initialBrief={(project.brief ?? {}) as Brief}
        initialTitle={project.title}
        onComplete={() => router.push(`/dashboard/projects/${id}/script`)}
      />
    </div>
  );
}
