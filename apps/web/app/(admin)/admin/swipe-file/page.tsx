"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { BlueprintReview } from "@/components/admin/BlueprintReview";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { swipeFileApi } from "@/lib/swipe-file-api";
import { BLUEPRINT_CATEGORIES } from "@/types/blueprint";

type Filter = "all" | "pending" | "approved";

export default function SwipeFilePage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [industry, setIndustry] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);

  const stats = useQuery({
    queryKey: ["swipe-stats"],
    queryFn: () => swipeFileApi.stats(),
  });

  const approvedFilter =
    filter === "all" ? undefined : filter === "approved" ? true : false;

  const blueprints = useQuery({
    queryKey: ["swipe-list", filter],
    queryFn: () => swipeFileApi.list({ approved: approvedFilter }),
  });

  const analyze = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a video file first.");
      return swipeFileApi.analyze(file, {
        industry: industry || undefined,
        category: category || undefined,
      });
    },
    onSuccess: (created) => {
      setFile(null);
      setError(null);
      setSelectedId(created.id);
      qc.invalidateQueries({ queryKey: ["swipe-list"] });
      qc.invalidateQueries({ queryKey: ["swipe-stats"] });
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : "Analysis failed."),
  });

  return (
    <div className="max-w-5xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Swipe file</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Deconstruct winning ads into reusable creative frameworks. Only approved
          blueprints are used when generating scripts.
        </p>
      </div>

      {stats.data && (
        <div className="grid gap-3 sm:grid-cols-4">
          {[
            { label: "Total", value: stats.data.total },
            { label: "Approved", value: stats.data.approved },
            { label: "Pending review", value: stats.data.pending },
            { label: "Searchable", value: stats.data.with_embeddings },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-neutral-800 p-4">
              <p className="text-xs text-neutral-500">{item.label}</p>
              <p className="mt-1 text-2xl font-semibold">{item.value}</p>
            </div>
          ))}
        </div>
      )}

      {stats.data && stats.data.approved === 0 && (
        <p className="rounded-md border border-amber-900/60 bg-amber-500/10 p-3 text-sm text-amber-300">
          No approved blueprints yet. Until at least a few are approved, script
          generation runs without reference patterns.
        </p>
      )}

      <section className="rounded-lg border border-neutral-800 p-5">
        <h2 className="font-medium">Analyse a reference ad</h2>
        <p className="mt-1 text-xs text-neutral-500">
          MP4, MOV or WebM, up to 200 MB. The source file is kept privately for
          curation only and is never shown to users.
        </p>

        <div className="mt-4 space-y-3">
          <input
            type="file"
            accept="video/mp4,video/quicktime,video/webm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-neutral-300 file:mr-3 file:rounded-md file:border-0 file:bg-neutral-800 file:px-3 file:py-2 file:text-sm file:text-neutral-200"
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              placeholder="Industry hint (optional)"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
            />
            <select
              className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">Category hint (optional)</option>
              {BLUEPRINT_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <Button
            onClick={() => analyze.mutate()}
            disabled={!file || analyze.isPending}
          >
            {analyze.isPending ? "Analysing (this can take a minute)…" : "Analyse"}
          </Button>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between">
          <h2 className="font-medium">Library</h2>
          <div className="flex gap-1">
            {(["all", "pending", "approved"] as Filter[]).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setFilter(option)}
                className={`rounded-md px-3 py-1 text-xs capitalize transition ${
                  filter === option
                    ? "bg-brand/20 text-white"
                    : "text-neutral-400 hover:bg-neutral-900"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-3 divide-y divide-neutral-800 rounded-lg border border-neutral-800">
          {blueprints.isLoading && (
            <p className="p-4 text-sm text-neutral-500">Loading…</p>
          )}
          {blueprints.data?.length === 0 && (
            <p className="p-4 text-sm text-neutral-500">Nothing here yet.</p>
          )}
          {blueprints.data?.map((bp) => (
            <button
              key={bp.id}
              type="button"
              onClick={() => setSelectedId(bp.id)}
              className={`flex w-full items-center justify-between gap-4 p-3 text-left transition hover:bg-neutral-900/60 ${
                selectedId === bp.id ? "bg-neutral-900" : ""
              }`}
            >
              <div className="min-w-0">
                <p className="truncate text-sm text-neutral-100">
                  {bp.title ?? "Untitled pattern"}
                </p>
                <p className="mt-0.5 text-xs text-neutral-500">
                  {[bp.ad_category, bp.industry, bp.format, bp.pacing]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2 text-xs">
                {!bp.has_embedding && (
                  <span className="text-amber-400/80">no vector</span>
                )}
                <span
                  className={`rounded-full px-2 py-0.5 ${
                    bp.is_approved
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-neutral-700/50 text-neutral-300"
                  }`}
                >
                  {bp.is_approved ? "Approved" : "Pending"}
                </span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {selectedId && (
        <BlueprintReview
          blueprintId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
