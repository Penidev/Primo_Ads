"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { BriefWizard } from "@/components/brief/BriefWizard";
import { projectApi } from "@/lib/project-api";

export default function NewProjectPage() {
  const router = useRouter();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const created = useRef(false);

  // Create a draft project immediately so auto-save has somewhere to persist.
  useEffect(() => {
    if (created.current) return;
    created.current = true;
    projectApi
      .create(null, {})
      .then((p) => setProjectId(p.id))
      .catch(() => setError("Could not start a new project. Please try again."));
  }, []);

  if (error) return <p className="text-red-400">{error}</p>;
  if (!projectId) return <p className="text-neutral-500">Setting up your project…</p>;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold">Create a new ad</h1>
      <BriefWizard
        projectId={projectId}
        initialBrief={{}}
        initialTitle={null}
        onComplete={() => router.push(`/dashboard/projects/${projectId}/script`)}
      />
    </div>
  );
}
