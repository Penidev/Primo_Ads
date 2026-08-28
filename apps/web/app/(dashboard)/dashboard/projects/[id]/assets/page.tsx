"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { AssetCard } from "@/components/assets/AssetCard";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { assetApi } from "@/lib/asset-api";

export default function AssetsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const plan = useQuery({
    queryKey: ["assets", id],
    queryFn: () => assetApi.list(id),
  });

  const cost = useQuery({
    queryKey: ["asset-cost", id],
    queryFn: () => assetApi.cost(id),
    retry: false,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["assets", id] });
    qc.invalidateQueries({ queryKey: ["asset-cost", id] });
    qc.invalidateQueries({ queryKey: ["wallet"] });
  };

  const generate = useMutation({
    mutationFn: () => assetApi.generate(id),
    onSuccess: (data) => {
      qc.setQueryData(["assets", id], data);
      refresh();
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Asset generation failed."),
  });

  const approveAll = useMutation({
    mutationFn: () => assetApi.approveAll(id),
    onSuccess: () => {
      refresh();
      router.push(`/dashboard/projects/${id}/generate`);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not approve assets."),
  });

  const groups = plan.data?.scenes ?? [];
  const allAssets = groups.flatMap((g) => g.assets);
  const generated = allAssets.filter((a) =>
    ["generated", "approved", "user_uploaded"].includes(a.status)
  );
  const pending = plan.data?.pending_assets ?? 0;
  const hasAny = allAssets.length > 0;

  return (
    <div className="max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Reference assets</h1>
          <p className="mt-2 text-sm text-neutral-400">
            These images are fed into the video model as visual anchors, so your brand
            and characters stay consistent instead of being imagined from scratch.
          </p>
        </div>
        {generated.length > 0 && (
          <Button onClick={() => approveAll.mutate()} disabled={approveAll.isPending}>
            {approveAll.isPending ? "Approving…" : "Approve & continue"}
          </Button>
        )}
      </div>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      {!hasAny && !plan.isLoading && (
        <div className="mt-6 rounded-lg border border-dashed border-neutral-800 p-10 text-center">
          <p className="text-neutral-400">
            This script did not request any reference assets.
          </p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => router.push(`/dashboard/projects/${id}/generate`)}
          >
            Skip to video generation
          </Button>
        </div>
      )}

      {pending > 0 && (
        <div className="mt-6 rounded-lg border border-neutral-800 p-5">
          <p className="text-sm text-neutral-200">
            {pending} asset{pending > 1 ? "s" : ""} ready to generate.
          </p>
          {cost.data && (
            <p className="mt-1 text-sm text-neutral-400">
              Cost: <strong>{cost.data.credits_required} credits</strong> (approx. $
              {cost.data.estimated_usd.toFixed(2)}). Balance:{" "}
              {cost.data.current_balance}.
            </p>
          )}
          {cost.data && !cost.data.sufficient && (
            <p className="mt-1 text-sm text-amber-400">
              You need more credits to generate these assets.
            </p>
          )}
          <Button
            className="mt-4"
            onClick={() => generate.mutate()}
            disabled={
              generate.isPending || (cost.data ? !cost.data.sufficient : false)
            }
          >
            {generate.isPending ? "Generating images…" : "Generate assets"}
          </Button>
        </div>
      )}

      <div className="mt-8 space-y-8">
        {groups.map((group) => (
          <section key={group.scene_number}>
            <h2 className="text-sm font-medium text-neutral-200">
              Scene {group.scene_number}
              {group.scene_label && (
                <span className="text-neutral-500"> — {group.scene_label}</span>
              )}
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {group.assets.map((asset) => (
                <AssetCard
                  key={asset.id}
                  projectId={id}
                  asset={asset}
                  onChanged={refresh}
                  onError={setError}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
