"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { FieldLabel } from "@/components/ui/field-hint";
import { Input } from "@/components/ui/input";
import { useDebouncedEffect } from "@/hooks/useDebouncedEffect";
import { projectApi } from "@/lib/project-api";
import {
  AD_CATEGORIES,
  DURATIONS,
  FORMATS,
  OBJECTIVES,
  VOICE_TONES,
  type Brief,
} from "@/types/brief";

const STEPS = ["Brand", "Product", "Competition", "Campaign", "Notes"] as const;

interface Props {
  projectId: string;
  initialBrief: Brief;
  initialTitle: string | null;
  onComplete: () => void;
}

const textareaClass =
  "w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm " +
  "text-neutral-100 placeholder:text-neutral-500 focus:border-brand focus:outline-none " +
  "focus:ring-1 focus:ring-brand";

export function BriefWizard({ projectId, initialBrief, initialTitle, onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState(initialTitle ?? "");
  const [brief, setBrief] = useState<Brief>(initialBrief);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  // Auto-save to the server so nothing is lost on refresh, logout, or crash.
  useDebouncedEffect(
    () => {
      setSaveState("saving");
      projectApi
        .updateBrief(projectId, {
          title: title || undefined,
          brief: brief as Record<string, unknown>,
        })
        .then(() => setSaveState("saved"))
        .catch(() => setSaveState("error"));
    },
    [title, JSON.stringify(brief)],
    800
  );

  const patchBrand = (value: Partial<NonNullable<Brief["brand"]>>) =>
    setBrief((b) => ({ ...b, brand: { ...b.brand, ...value } }));
  const patchProduct = (value: Partial<NonNullable<Brief["product"]>>) =>
    setBrief((b) => ({ ...b, product: { ...b.product, ...value } }));
  const patchCompetition = (value: Partial<NonNullable<Brief["competition"]>>) =>
    setBrief((b) => ({ ...b, competition: { ...b.competition, ...value } }));
  const patchCampaign = (value: Partial<NonNullable<Brief["campaign"]>>) =>
    setBrief((b) => ({ ...b, campaign: { ...b.campaign, ...value } }));

  const toggleTone = (tone: string) => {
    const current = brief.brand?.voice_tone ?? [];
    patchBrand({
      voice_tone: current.includes(tone)
        ? current.filter((t) => t !== tone)
        : [...current, tone],
    });
  };

  const saveLabel = {
    idle: "",
    saving: "Saving…",
    saved: "Saved",
    error: "Save failed — will retry",
  }[saveState];

  const isLast = step === STEPS.length - 1;

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <div className="flex items-center justify-between text-xs text-neutral-500">
          <span>
            Step {step + 1} of {STEPS.length}: {STEPS[step]}
          </span>
          <span className={saveState === "error" ? "text-red-400" : ""}>{saveLabel}</span>
        </div>
        <div className="mt-2 h-1 rounded bg-neutral-800">
          <div
            className="h-1 rounded bg-brand transition-all"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>
      </div>

      {step === 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Brand identity</h2>
          <p className="text-sm text-neutral-500">
            This is what the AI director uses to keep the ad recognisably yours.
          </p>
          <Input
            placeholder="Project name (optional)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div>
            <FieldLabel hint="Used throughout the script. Write it exactly as it should appear.">
              Brand name
            </FieldLabel>
            <Input
              placeholder="e.g. Cozzipay"
              value={brief.brand?.name ?? ""}
              onChange={(e) => patchBrand({ name: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel hint="One clear sentence. The sharper this is, the sharper the script's hook will be.">
              Elevator pitch
            </FieldLabel>
            <textarea
              className={textareaClass}
              rows={3}
              placeholder="What does your brand do, in one sentence?"
              value={brief.brand?.pitch ?? ""}
              onChange={(e) => patchBrand({ pitch: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel hint="Helps retrieve reference patterns from ads that worked in your sector.">
              Industry
            </FieldLabel>
            <Input
              placeholder="e.g. Fintech"
              value={brief.brand?.industry ?? ""}
              onChange={(e) => patchBrand({ industry: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel hint="Hex codes are translated into lighting and set-dressing language, which video models handle far better than raw hex.">
              Brand colours
            </FieldLabel>
            <Input
              placeholder="#3400D1, #FFD600"
              value={(brief.brand?.colors ?? []).join(", ")}
              onChange={(e) =>
                patchBrand({
                  colors: e.target.value
                    .split(",")
                    .map((c) => c.trim())
                    .filter(Boolean),
                })
              }
            />
          </div>
          <div>
            <p className="mb-2 text-sm text-neutral-400">Brand voice</p>
            <div className="flex flex-wrap gap-2">
              {VOICE_TONES.map((tone) => {
                const active = (brief.brand?.voice_tone ?? []).includes(tone);
                return (
                  <button
                    key={tone}
                    type="button"
                    onClick={() => toggleTone(tone)}
                    className={`rounded-full border px-3 py-1 text-xs transition ${
                      active
                        ? "border-brand bg-brand/20 text-white"
                        : "border-neutral-700 text-neutral-300 hover:bg-neutral-900"
                    }`}
                  >
                    {tone}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Product &amp; audience</h2>
          <div>
            <FieldLabel hint="Be specific. One feature makes a sharper ad than your whole product range.">
              What this ad is selling
            </FieldLabel>
            <Input
              placeholder="e.g. Our 1-click checkout SDK"
              value={brief.product?.name ?? ""}
              onChange={(e) => patchProduct({ name: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel hint="Who should feel this ad was made for them?">
              Target audience
            </FieldLabel>
            <Input
              placeholder="e.g. E-commerce store owners"
              value={brief.product?.target_audience ?? ""}
              onChange={(e) => patchProduct({ target_audience: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel hint="The frustration the ad opens on. This becomes the hook, so make it concrete.">
              Their biggest frustration
            </FieldLabel>
            <textarea
              className={textareaClass}
              rows={2}
              placeholder="e.g. Losing sales to long, fiddly checkout forms"
              value={brief.product?.pain_point ?? ""}
              onChange={(e) => patchProduct({ pain_point: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel hint="The one thing you do that alternatives cannot.">
              What makes you different
            </FieldLabel>
            <textarea
              className={textareaClass}
              rows={2}
              placeholder="e.g. One tap, no forms at all"
              value={brief.product?.differentiator ?? ""}
              onChange={(e) => patchProduct({ differentiator: e.target.value })}
            />
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Competition &amp; market</h2>
          <p className="text-sm text-neutral-500">
            This section does the most work. Real customer complaints produce far
            better hooks than generic positioning.
          </p>
          <div>
            <FieldLabel hint="Naming who you are up against lets the director build contrast rather than a generic pitch.">
              Main competitors
            </FieldLabel>
            <Input
              placeholder="Comma separated"
              value={(brief.competition?.competitors ?? []).join(", ")}
              onChange={(e) =>
                patchCompetition({
                  competitors: e.target.value
                    .split(",")
                    .map((c) => c.trim())
                    .filter(Boolean),
                })
              }
            />
          </div>
          <div>
            <FieldLabel hint="Quote real complaints if you have them: reviews, support tickets, social replies. Specific frustration makes a specific hook.">
              What is the market saying?
            </FieldLabel>
            <textarea
              className={textareaClass}
              rows={3}
              placeholder="e.g. Customers abandon mobile checkouts because typing billing details takes too long."
              value={brief.competition?.market_sentiment ?? ""}
              onChange={(e) => patchCompetition({ market_sentiment: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel hint="How you want to be seen relative to the alternatives.">
              Your positioning
            </FieldLabel>
            <textarea
              className={textareaClass}
              rows={2}
              placeholder="e.g. The modern, frictionless alternative"
              value={brief.competition?.positioning ?? ""}
              onChange={(e) => patchCompetition({ positioning: e.target.value })}
            />
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-5">
          <h2 className="text-xl font-semibold">Campaign setup</h2>

          <div>
            <p className="mb-2 text-sm text-neutral-400">Objective</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {OBJECTIVES.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => patchCampaign({ objective: o.value })}
                  className={`rounded-md border px-3 py-2 text-left text-sm transition ${
                    brief.campaign?.objective === o.value
                      ? "border-brand bg-brand/20 text-white"
                      : "border-neutral-700 text-neutral-300 hover:bg-neutral-900"
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm text-neutral-400">Narrative arc</p>
            <div className="space-y-2">
              {AD_CATEGORIES.map((c) => (
                <button
                  key={c.value}
                  type="button"
                  onClick={() => patchCampaign({ ad_category: c.value })}
                  className={`w-full rounded-md border px-3 py-2 text-left transition ${
                    brief.campaign?.ad_category === c.value
                      ? "border-brand bg-brand/20"
                      : "border-neutral-700 hover:bg-neutral-900"
                  }`}
                >
                  <span className="block text-sm font-medium text-neutral-100">
                    {c.label}
                  </span>
                  <span className="block text-xs text-neutral-400">{c.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm text-neutral-400">Format</p>
            <div className="grid gap-2 sm:grid-cols-3">
              {FORMATS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => patchCampaign({ format: f.value })}
                  className={`rounded-md border px-3 py-2 text-sm transition ${
                    brief.campaign?.format === f.value
                      ? "border-brand bg-brand/20 text-white"
                      : "border-neutral-700 text-neutral-300 hover:bg-neutral-900"
                  }`}
                >
                  <span className="block">{f.label}</span>
                  <span className="block text-xs text-neutral-500">{f.hint}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm text-neutral-400">Length</p>
            <div className="flex gap-2">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => patchCampaign({ duration_seconds: d })}
                  className={`rounded-md border px-4 py-2 text-sm transition ${
                    brief.campaign?.duration_seconds === d
                      ? "border-brand bg-brand/20 text-white"
                      : "border-neutral-700 text-neutral-300 hover:bg-neutral-900"
                  }`}
                >
                  {d}s
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Notes for the director</h2>
          <textarea
            className={textareaClass}
            rows={5}
            placeholder="Anything else the AI director should know? Specific scenes, must-have shots, things to avoid."
            value={brief.director_notes ?? ""}
            onChange={(e) => setBrief((b) => ({ ...b, director_notes: e.target.value }))}
          />
          <p className="text-xs text-neutral-500">
            Your brief is saved automatically. You can come back and edit it any time
            before generating the script.
          </p>
        </div>
      )}

      <div className="mt-8 flex gap-3">
        {step > 0 && (
          <Button variant="outline" onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
        )}
        {!isLast && (
          <Button className="flex-1" onClick={() => setStep((s) => s + 1)}>
            Continue
          </Button>
        )}
        {isLast && (
          <Button className="flex-1" onClick={onComplete}>
            Save & continue to script
          </Button>
        )}
      </div>
    </div>
  );
}
