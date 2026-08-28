"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { userApi, type OnboardingUpdate } from "@/lib/user-api";

const INDUSTRIES = [
  "Fintech",
  "E-commerce",
  "SaaS",
  "FMCG / Consumer Goods",
  "Health & Wellness",
  "Education",
  "Real Estate",
  "Other",
];
const ROLES = ["Founder", "Marketing Manager", "Creative Director", "Agency", "Other"];
const USE_CASES = [
  { value: "video_gen", label: "AI video generation" },
  { value: "script_only", label: "Scripts & direction only" },
  { value: "both", label: "Both" },
];
const PLATFORMS = ["TikTok", "Instagram Reels", "YouTube", "LinkedIn", "TV / Cinema"];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<OnboardingUpdate>({ ad_platforms: [] });

  const set = (patch: Partial<OnboardingUpdate>) => setData((d) => ({ ...d, ...patch }));

  const togglePlatform = (p: string) => {
    const current = data.ad_platforms ?? [];
    set({
      ad_platforms: current.includes(p)
        ? current.filter((x) => x !== p)
        : [...current, p],
    });
  };

  // Persist progress on each step so nothing is lost (server-side save).
  const saveStep = async (extra?: Partial<OnboardingUpdate>) => {
    setSaving(true);
    try {
      await userApi.updateOnboarding({ ...data, ...extra });
    } finally {
      setSaving(false);
    }
  };

  const next = async () => {
    await saveStep();
    setStep((s) => s + 1);
  };

  const finish = async () => {
    await saveStep({ complete: true });
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-between text-xs text-neutral-500">
          <span>Step {step} of 3</span>
          <span>{saving ? "Saving…" : "Saved"}</span>
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <h1 className="text-2xl font-semibold">Tell us about you</h1>
            <Input
              placeholder="Company / brand name"
              value={data.company_name ?? ""}
              onChange={(e) => set({ company_name: e.target.value })}
            />
            <Input
              placeholder="Country (ISO code, e.g. USA)"
              value={data.country ?? ""}
              onChange={(e) => set({ country: e.target.value.toUpperCase() })}
              maxLength={3}
            />
            <select
              className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
              value={data.industry ?? ""}
              onChange={(e) => set({ industry: e.target.value })}
            >
              <option value="">Select industry</option>
              {INDUSTRIES.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
            <Button className="w-full" onClick={next} disabled={saving}>
              Continue
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h1 className="text-2xl font-semibold">Your role & goals</h1>
            <select
              className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
              value={data.role ?? ""}
              onChange={(e) => set({ role: e.target.value })}
            >
              <option value="">Select your role</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <div className="space-y-2">
              <p className="text-sm text-neutral-400">Primary use case</p>
              {USE_CASES.map((u) => (
                <label key={u.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="use_case"
                    checked={data.use_case === u.value}
                    onChange={() => set({ use_case: u.value })}
                  />
                  {u.label}
                </label>
              ))}
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button className="flex-1" onClick={next} disabled={saving}>
                Continue
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h1 className="text-2xl font-semibold">Where do you advertise?</h1>
            <div className="grid grid-cols-2 gap-2">
              {PLATFORMS.map((p) => {
                const active = (data.ad_platforms ?? []).includes(p);
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => togglePlatform(p)}
                    className={`rounded-md border px-3 py-2 text-sm transition ${
                      active
                        ? "border-brand bg-brand/20 text-white"
                        : "border-neutral-700 text-neutral-300 hover:bg-neutral-900"
                    }`}
                  >
                    {p}
                  </button>
                );
              })}
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button className="flex-1" onClick={finish} disabled={saving}>
                Finish
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
