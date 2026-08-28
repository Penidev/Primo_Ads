"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useCurrentUser } from "@/hooks/useAuth";
import { billingApi } from "@/lib/billing-api";
import { projectApi } from "@/lib/project-api";

const STATUS_COPY: Record<string, string> = {
  draft: "Brief in progress",
  scripted: "Script ready",
  assets_ready: "Assets approved",
  generating: "Generating video",
  completed: "Finished",
  failed: "Needs attention",
};

export default function DashboardHome() {
  const { data: user } = useCurrentUser();

  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectApi.list(),
  });
  const wallet = useQuery({
    queryKey: ["wallet"],
    queryFn: () => billingApi.wallet(),
    retry: false,
  });

  const list = projects.data ?? [];
  const isFirstTime = !projects.isLoading && list.length === 0;
  const inProgress = list.filter((p) => p.status !== "completed").slice(0, 3);
  const firstName = user?.full_name?.split(" ")[0];

  // Guided setup: only shown until the user has actually produced something.
  const steps = [
    {
      label: "Complete your profile",
      done: Boolean(user?.onboarding_completed),
      href: "/onboarding",
    },
    {
      label: "Add credits to your wallet",
      done: (wallet.data?.balance_credits ?? 0) > 0,
      href: "/dashboard/billing",
    },
    {
      label: "Create your first ad",
      done: list.length > 0,
      href: "/dashboard/projects/new",
    },
  ];
  const remaining = steps.filter((s) => !s.done);

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold">
        {firstName ? `Welcome back, ${firstName}` : "Welcome to Primo"}
      </h1>

      {isFirstTime ? (
        <p className="mt-2 text-neutral-400">
          Write one brief and Primo returns a full directorial treatment: script,
          shot list, camera and lighting notes, then the finished video if you want it.
        </p>
      ) : (
        <p className="mt-2 text-neutral-400">
          {list.length} project{list.length === 1 ? "" : "s"}
          {wallet.data && ` · ${wallet.data.balance_credits} credits available`}
        </p>
      )}

      {remaining.length > 0 && (
        <section className="mt-6 rounded-lg border border-neutral-800 p-5">
          <h2 className="text-sm font-medium text-neutral-200">Getting started</h2>
          <ol className="mt-3 space-y-2">
            {steps.map((step) => (
              <li key={step.label} className="flex items-center gap-3 text-sm">
                <span
                  aria-hidden="true"
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] ${
                    step.done
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "border border-neutral-700 text-neutral-500"
                  }`}
                >
                  {step.done ? "\u2713" : ""}
                </span>
                {step.done ? (
                  <span className="text-neutral-500 line-through">{step.label}</span>
                ) : (
                  <Link href={step.href} className="text-neutral-200 hover:underline">
                    {step.label}
                  </Link>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="mt-6 flex flex-wrap gap-3">
        <Link href="/dashboard/projects/new">
          <Button>Create new ad</Button>
        </Link>
        {list.length > 0 && (
          <Link href="/dashboard/projects">
            <Button variant="outline">All projects</Button>
          </Link>
        )}
      </div>

      {inProgress.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm font-medium text-neutral-200">Pick up where you left off</h2>
          <div className="mt-3 space-y-2">
            {inProgress.map((project) => (
              <Link
                key={project.id}
                href={`/dashboard/projects/${project.id}`}
                className="flex items-center justify-between gap-4 rounded-lg border border-neutral-800 p-4 transition hover:border-neutral-600"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm text-neutral-100">
                    {project.title || "Untitled project"}
                  </p>
                  <p className="mt-0.5 text-xs text-neutral-500">
                    {STATUS_COPY[project.status] ?? project.status} · updated{" "}
                    {new Date(project.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-brand-highlight">Continue</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {isFirstTime && (
        <section className="mt-10 rounded-lg border border-dashed border-neutral-800 p-6">
          <h2 className="text-sm font-medium text-neutral-200">
            What you will need
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-neutral-400">
            <li>Your brand name and a one-sentence description of what you do</li>
            <li>The specific product or feature this ad should sell</li>
            <li>Who it is for, and their biggest frustration</li>
            <li>
              Anything real customers say about you or your competitors — this makes
              the biggest difference to the script
            </li>
          </ul>
        </section>
      )}
    </div>
  );
}
