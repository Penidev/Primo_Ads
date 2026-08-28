"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { swipeFileApi, type BlueprintEdits } from "@/lib/swipe-file-api";
import { BLUEPRINT_CATEGORIES } from "@/types/blueprint";

interface Props {
  blueprintId: string;
  onClose: () => void;
}

export function BlueprintReview({ blueprintId, onClose }: Props) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<BlueprintEdits>({});
  const [score, setScore] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const { data: bp, isLoading } = useQuery({
    queryKey: ["blueprint", blueprintId],
    queryFn: () => swipeFileApi.get(blueprintId),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["blueprint", blueprintId] });
    qc.invalidateQueries({ queryKey: ["swipe-list"] });
    qc.invalidateQueries({ queryKey: ["swipe-stats"] });
  };

  const save = useMutation({
    mutationFn: () => swipeFileApi.update(blueprintId, edits),
    onSuccess: () => {
      setEdits({});
      setError(null);
      refresh();
    },
    onError: () => setError("Could not save changes."),
  });

  const approve = useMutation({
    mutationFn: (isApproved: boolean) =>
      swipeFileApi.setApproval(
        blueprintId,
        isApproved,
        score ? Number(score) : undefined
      ),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: () => setError("Could not update approval."),
  });

  const rebuildVector = useMutation({
    mutationFn: () => swipeFileApi.regenerateEmbedding(blueprintId),
    onSuccess: refresh,
    onError: () => setError("Could not rebuild the search vector."),
  });

  const remove = useMutation({
    mutationFn: () => swipeFileApi.remove(blueprintId),
    onSuccess: () => {
      refresh();
      onClose();
    },
    onError: () => setError("Could not delete this blueprint."),
  });

  if (isLoading) return <p className="text-sm text-neutral-500">Loading blueprint…</p>;
  if (!bp) return null;

  const arc = bp.structural_arc ?? {};

  return (
    <section className="rounded-lg border border-neutral-700 bg-neutral-950/60 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-medium">{bp.title ?? "Untitled pattern"}</h2>
          <p className="mt-1 text-xs text-neutral-500">
            {[bp.ad_category, bp.industry, bp.format, `${bp.duration_seconds ?? "?"}s`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-neutral-400 hover:text-white"
        >
          Close
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

      {/* --- extracted analysis --- */}
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {bp.psychological_triggers && bp.psychological_triggers.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">
              Psychological triggers
            </p>
            <p className="mt-1 text-sm text-neutral-200">
              {bp.psychological_triggers.join(", ")}
            </p>
          </div>
        )}
        {bp.camera_techniques && bp.camera_techniques.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">
              Camera techniques
            </p>
            <p className="mt-1 text-sm text-neutral-200">
              {bp.camera_techniques.join(", ")}
            </p>
          </div>
        )}
        {bp.hook_style && (
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">Hook</p>
            <p className="mt-1 text-sm text-neutral-200">{bp.hook_style}</p>
          </div>
        )}
        {bp.color_palette && bp.color_palette.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">Palette</p>
            <p className="mt-1 text-sm text-neutral-200">{bp.color_palette.join(", ")}</p>
          </div>
        )}
      </div>

      {arc.beats && arc.beats.length > 0 && (
        <div className="mt-5">
          <p className="text-xs uppercase tracking-wide text-neutral-500">Structure</p>
          <div className="mt-2 space-y-2">
            {arc.beats.map((beat) => (
              <div
                key={beat.beat_number}
                className="rounded-md border border-neutral-800 p-3"
              >
                <div className="flex items-center gap-2">
                  <span className="rounded bg-brand/20 px-2 py-0.5 text-[11px] text-brand-highlight">
                    {beat.label}
                  </span>
                  <span className="text-[11px] text-neutral-500">
                    {beat.start_second}s–{beat.end_second}s
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-neutral-300">
                  {beat.narrative_function}
                </p>
                <p className="mt-1 text-xs text-neutral-500">{beat.visual_technique}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {arc.why_it_works && (
        <div className="mt-5">
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Why it works
          </p>
          <p className="mt-1 text-sm text-neutral-300">{arc.why_it_works}</p>
        </div>
      )}
      {arc.reusable_pattern && (
        <div className="mt-4">
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Reusable pattern
          </p>
          <p className="mt-1 text-sm text-neutral-300">{arc.reusable_pattern}</p>
        </div>
      )}

      {/* --- curator corrections --- */}
      <div className="mt-6 border-t border-neutral-800 pt-5">
        <p className="text-sm font-medium">Corrections</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Input
            placeholder={bp.title ?? "Title"}
            value={edits.title ?? ""}
            onChange={(e) => setEdits((p) => ({ ...p, title: e.target.value }))}
          />
          <Input
            placeholder={bp.industry ?? "Industry"}
            value={edits.industry ?? ""}
            onChange={(e) => setEdits((p) => ({ ...p, industry: e.target.value }))}
          />
          <select
            className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
            value={edits.ad_category ?? bp.ad_category ?? ""}
            onChange={(e) => setEdits((p) => ({ ...p, ad_category: e.target.value }))}
          >
            {BLUEPRINT_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <Input
            placeholder="Platform (e.g. TikTok)"
            value={edits.platform ?? ""}
            onChange={(e) => setEdits((p) => ({ ...p, platform: e.target.value }))}
          />
        </div>
        <Button
          className="mt-3"
          variant="outline"
          onClick={() => save.mutate()}
          disabled={Object.keys(edits).length === 0 || save.isPending}
        >
          {save.isPending ? "Saving…" : "Save corrections"}
        </Button>
      </div>

      {/* --- approval --- */}
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-neutral-800 pt-5">
        <Input
          type="number"
          min={0}
          max={10}
          step={0.5}
          placeholder="Score 0-10"
          value={score}
          onChange={(e) => setScore(e.target.value)}
          className="w-32"
        />
        {bp.is_approved ? (
          <Button
            variant="outline"
            onClick={() => approve.mutate(false)}
            disabled={approve.isPending}
          >
            Unapprove
          </Button>
        ) : (
          <Button onClick={() => approve.mutate(true)} disabled={approve.isPending}>
            {approve.isPending ? "Approving…" : "Approve for generation"}
          </Button>
        )}
        {!bp.has_embedding && (
          <Button
            variant="outline"
            onClick={() => rebuildVector.mutate()}
            disabled={rebuildVector.isPending}
          >
            {rebuildVector.isPending ? "Building…" : "Rebuild search vector"}
          </Button>
        )}
        <button
          type="button"
          onClick={() => remove.mutate()}
          disabled={remove.isPending}
          className="ml-auto text-xs text-red-400 hover:text-red-300"
        >
          Delete
        </button>
      </div>
    </section>
  );
}
