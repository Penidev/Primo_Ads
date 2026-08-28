"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";
import { assetApi } from "@/lib/asset-api";
import type { SceneAssetPublic } from "@/types/asset";

interface Props {
  projectId: string;
  asset: SceneAssetPublic;
  onChanged: () => void;
  onError: (message: string) => void;
}

const STATUS_STYLE: Record<string, string> = {
  approved: "bg-emerald-500/20 text-emerald-300",
  user_uploaded: "bg-sky-500/20 text-sky-300",
  generated: "bg-neutral-700/50 text-neutral-300",
  rejected: "bg-red-500/20 text-red-300",
  failed: "bg-red-500/20 text-red-300",
  pending: "bg-neutral-800 text-neutral-400",
};

const STATUS_LABEL: Record<string, string> = {
  approved: "Approved",
  user_uploaded: "Your image",
  generated: "Generated",
  rejected: "Rejected",
  failed: "Failed",
  pending: "Not generated",
};

export function AssetCard({ projectId, asset, onChanged, onError }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);

  const regenerate = useMutation({
    mutationFn: () => assetApi.regenerate(projectId, asset.id),
    onSuccess: onChanged,
    onError: () => onError("Could not regenerate that asset."),
  });

  const setStatus = useMutation({
    mutationFn: (status: "approved" | "rejected") =>
      assetApi.setStatus(projectId, asset.id, status),
    onSuccess: onChanged,
    onError: () => onError("Could not update that asset."),
  });

  const replace = useMutation({
    mutationFn: (file: File) => assetApi.replace(projectId, asset.id, file),
    onSuccess: onChanged,
    onError: (err) =>
      onError(err instanceof Error ? err.message : "Upload failed."),
  });

  const busy = regenerate.isPending || setStatus.isPending || replace.isPending;

  return (
    <div className="rounded-lg border border-neutral-800 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-xs text-neutral-400">
          {asset.asset_type ?? "asset"}
        </span>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] ${
            STATUS_STYLE[asset.status] ?? STATUS_STYLE.pending
          }`}
        >
          {STATUS_LABEL[asset.status] ?? asset.status}
        </span>
      </div>

      <div className="mt-2 aspect-square overflow-hidden rounded bg-neutral-950">
        {asset.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={asset.image_url}
            alt={asset.description ?? "Reference asset"}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center px-3 text-center text-[11px] text-neutral-600">
            {asset.status === "failed"
              ? "Generation failed — credits refunded"
              : "Not generated yet"}
          </div>
        )}
      </div>

      {asset.description && (
        <p className="mt-2 line-clamp-3 text-[11px] text-neutral-500">
          {asset.description}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        <button
          type="button"
          onClick={() => regenerate.mutate()}
          disabled={busy}
          className="rounded border border-neutral-700 px-2 py-1 text-neutral-300 hover:bg-neutral-900 disabled:opacity-50"
        >
          {regenerate.isPending ? "Regenerating…" : "Regenerate"}
        </button>

        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={busy}
          className="rounded border border-neutral-700 px-2 py-1 text-neutral-300 hover:bg-neutral-900 disabled:opacity-50"
        >
          {replace.isPending ? "Uploading…" : "Upload own"}
        </button>

        {asset.status === "generated" && (
          <>
            <button
              type="button"
              onClick={() => setStatus.mutate("approved")}
              disabled={busy}
              className="rounded border border-emerald-700/60 px-2 py-1 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              onClick={() => setStatus.mutate("rejected")}
              disabled={busy}
              className="rounded border border-neutral-700 px-2 py-1 text-neutral-400 hover:bg-neutral-900 disabled:opacity-50"
            >
              Reject
            </button>
          </>
        )}
      </div>

      <input
        ref={fileInput}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) replace.mutate(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
