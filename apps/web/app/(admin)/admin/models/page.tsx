"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { adminApi, type VideoModelCreate } from "@/lib/admin-api";

const EMPTY_MODEL: VideoModelCreate = {
  slug: "",
  display_name: "",
  provider: "fal",
  model_id: "",
  max_duration_seconds: 8,
  supported_resolutions: ["1080p"],
  supported_aspect_ratios: ["9:16", "16:9"],
  supports_audio: false,
  supports_image_reference: true,
  cost_per_second_usd: 0.1,
  credit_multiplier: 1,
  quality_tier: "standard",
};

export default function AdminModelsPage() {
  const qc = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [showAdd, setShowAdd] = useState(false);
  const [newModel, setNewModel] = useState<VideoModelCreate>(EMPTY_MODEL);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const models = useQuery({
    queryKey: ["admin-models"],
    queryFn: () => adminApi.listModels(),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["admin-models"] });
    qc.invalidateQueries({ queryKey: ["admin-margins"] });
  };

  const toggle = useMutation({
    mutationFn: ({ slug, enabled }: { slug: string; enabled: boolean }) =>
      adminApi.updateModel(slug, { is_enabled: enabled }),
    onSuccess: refresh,
    onError: () => setError("Could not toggle that model."),
  });

  const saveMultiplier = useMutation({
    mutationFn: ({ slug, value }: { slug: string; value: number }) =>
      adminApi.updateModel(slug, { credit_multiplier: value }),
    onSuccess: (_d, v) => {
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[v.slug];
        return next;
      });
      setMessage("Multiplier updated.");
      setError(null);
      refresh();
    },
    onError: () => setError("Could not update the multiplier."),
  });

  const create = useMutation({
    mutationFn: () => adminApi.createModel(newModel),
    onSuccess: () => {
      setShowAdd(false);
      setNewModel(EMPTY_MODEL);
      setMessage("Model registered and available to users immediately.");
      setError(null);
      refresh();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Could not register that model."),
  });

  return (
    <div className="max-w-5xl space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Video models</h1>
          <p className="mt-2 text-sm text-neutral-400">
            The generation engines users can choose from. Adding a model on a supported
            provider needs no deployment.
          </p>
        </div>
        <Button variant="outline" onClick={() => setShowAdd((v) => !v)}>
          {showAdd ? "Cancel" : "Add model"}
        </Button>
      </div>

      {message && <p className="text-sm text-emerald-400">{message}</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {showAdd && (
        <section className="rounded-lg border border-neutral-700 p-5">
          <h2 className="font-medium">Register a model</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Input
              placeholder="Slug (e.g. kling-3.5)"
              value={newModel.slug}
              onChange={(e) => setNewModel({ ...newModel, slug: e.target.value })}
            />
            <Input
              placeholder="Display name"
              value={newModel.display_name}
              onChange={(e) =>
                setNewModel({ ...newModel, display_name: e.target.value })
              }
            />
            <Input
              placeholder="Provider (fal)"
              value={newModel.provider}
              onChange={(e) => setNewModel({ ...newModel, provider: e.target.value })}
            />
            <Input
              placeholder="Provider model id (e.g. fal-ai/kling-video/v3)"
              value={newModel.model_id}
              onChange={(e) => setNewModel({ ...newModel, model_id: e.target.value })}
            />
            <label className="text-xs text-neutral-500">
              Cost per second (USD)
              <Input
                type="number"
                step="0.001"
                value={newModel.cost_per_second_usd}
                onChange={(e) =>
                  setNewModel({
                    ...newModel,
                    cost_per_second_usd: Number(e.target.value),
                  })
                }
              />
            </label>
            <label className="text-xs text-neutral-500">
              Credit multiplier
              <Input
                type="number"
                step="0.1"
                value={newModel.credit_multiplier}
                onChange={(e) =>
                  setNewModel({ ...newModel, credit_multiplier: Number(e.target.value) })
                }
              />
            </label>
            <label className="text-xs text-neutral-500">
              Max duration (s)
              <Input
                type="number"
                value={newModel.max_duration_seconds}
                onChange={(e) =>
                  setNewModel({
                    ...newModel,
                    max_duration_seconds: Number(e.target.value),
                  })
                }
              />
            </label>
            <label className="text-xs text-neutral-500">
              Quality tier
              <select
                className="mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
                value={newModel.quality_tier}
                onChange={(e) =>
                  setNewModel({ ...newModel, quality_tier: e.target.value })
                }
              >
                <option value="budget">budget</option>
                <option value="standard">standard</option>
                <option value="premium">premium</option>
              </select>
            </label>
          </div>
          <div className="mt-3 flex gap-4 text-sm text-neutral-300">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={newModel.supports_audio}
                onChange={(e) =>
                  setNewModel({ ...newModel, supports_audio: e.target.checked })
                }
              />
              Native audio
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={newModel.supports_image_reference}
                onChange={(e) =>
                  setNewModel({
                    ...newModel,
                    supports_image_reference: e.target.checked,
                  })
                }
              />
              Image references
            </label>
          </div>
          <Button
            className="mt-4"
            onClick={() => create.mutate()}
            disabled={
              !newModel.slug || !newModel.model_id || !newModel.display_name || create.isPending
            }
          >
            {create.isPending ? "Registering…" : "Register model"}
          </Button>
        </section>
      )}

      <div className="overflow-x-auto rounded-lg border border-neutral-800">
        <table className="w-full text-sm">
          <thead className="bg-neutral-900/60 text-left text-xs text-neutral-500">
            <tr>
              <th className="p-3">Model</th>
              <th className="p-3">Provider</th>
              <th className="p-3">Tier</th>
              <th className="p-3">Cost/s</th>
              <th className="p-3">Multiplier</th>
              <th className="p-3">Caps</th>
              <th className="p-3">State</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800">
            {models.data?.map((m) => (
              <tr key={m.slug}>
                <td className="p-3">
                  <p className="text-neutral-100">{m.display_name ?? m.slug}</p>
                  <p className="text-xs text-neutral-500">{m.model_id}</p>
                </td>
                <td className="p-3 text-neutral-400">{m.provider}</td>
                <td className="p-3 text-neutral-400">{m.quality_tier}</td>
                <td className="p-3 text-neutral-400">
                  {m.cost_per_second_usd !== null
                    ? `$${m.cost_per_second_usd.toFixed(3)}`
                    : "—"}
                </td>
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-neutral-300">x{m.credit_multiplier}</span>
                    <Input
                      type="number"
                      step="0.1"
                      min="0.1"
                      placeholder="New"
                      value={drafts[m.slug] ?? ""}
                      onChange={(e) =>
                        setDrafts((prev) => ({ ...prev, [m.slug]: e.target.value }))
                      }
                      className="w-20"
                    />
                    {drafts[m.slug] && (
                      <button
                        type="button"
                        onClick={() =>
                          saveMultiplier.mutate({
                            slug: m.slug,
                            value: Number(drafts[m.slug]),
                          })
                        }
                        className="text-xs text-brand-highlight hover:underline"
                      >
                        Save
                      </button>
                    )}
                  </div>
                </td>
                <td className="p-3 text-xs text-neutral-500">
                  {[
                    m.supports_audio ? "audio" : null,
                    m.supports_image_reference ? "refs" : null,
                    m.max_duration_seconds ? `${m.max_duration_seconds}s` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </td>
                <td className="p-3">
                  <button
                    type="button"
                    onClick={() =>
                      toggle.mutate({ slug: m.slug, enabled: !m.is_enabled })
                    }
                    className={`rounded-full px-2 py-0.5 text-[11px] ${
                      m.is_enabled
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-neutral-700/50 text-neutral-400"
                    }`}
                  >
                    {m.is_enabled ? "Enabled" : "Disabled"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
