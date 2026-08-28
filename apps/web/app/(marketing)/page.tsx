import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Primo — AI Ad Production Studio",
  description:
    "Turn a brand brief into a scene-by-scene directorial script and a finished video ad. Choose your video engine, keep your brand consistent, and export for your own crew if you prefer to shoot it.",
};

const STEPS = [
  {
    title: "Describe your brand",
    body: "A guided brief captures your product, audience, competitors, and what the market is actually saying.",
  },
  {
    title: "Get a director's script",
    body: "Scene by scene, with camera moves, lighting, colour grading, voiceover direction, and audio notes.",
  },
  {
    title: "Generate or shoot it",
    body: "Produce the video with your chosen AI engine, or export the treatment and shot list for your own crew.",
  },
];

const CAPABILITIES = [
  {
    title: "Multiple video engines",
    body: "Pick the engine that fits the job. Budget options for drafts, premium ones for final cuts, with the credit cost shown before you commit.",
  },
  {
    title: "Brand consistency built in",
    body: "Reference assets are generated first and fed into the video model, so your colours, products, and characters stay recognisable across every scene.",
  },
  {
    title: "Scene-level control",
    body: "Don't like one shot? Re-roll that scene alone. You are not paying to regenerate an entire ad.",
  },
  {
    title: "Useful without AI video",
    body: "If your team shoots with real people, take the script, shot list, and treatment and leave the generation behind.",
  },
];

export default function LandingPage() {
  return (
    <main>
      <section className="px-6 py-24 text-center">
        <span className="text-sm font-medium uppercase tracking-wide text-brand-highlight">
          AI Ad Production Studio
        </span>
        <h1 className="mx-auto mt-4 max-w-3xl text-4xl font-bold sm:text-5xl">
          From brand brief to finished video ad
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-lg text-neutral-400">
          Primo works like a creative director: it interrogates your brief, writes the
          script, plans every shot, and can produce the finished film.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-4">
          <Link
            href="/register"
            className="rounded-lg bg-brand px-6 py-3 font-medium text-white transition hover:opacity-90"
          >
            Start your first ad
          </Link>
          <Link
            href="/pricing"
            className="rounded-lg border border-neutral-700 px-6 py-3 font-medium text-neutral-200 transition hover:bg-neutral-900"
          >
            See pricing
          </Link>
        </div>
        <p className="mt-4 text-xs text-neutral-500">
          Prepaid credits. No subscription required to start.
        </p>
      </section>

      <section className="border-t border-neutral-800 px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-2xl font-semibold">How it works</h2>
          <ol className="mt-10 grid gap-6 sm:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.title} className="rounded-xl border border-neutral-800 p-6">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand/20 text-sm font-medium text-brand-highlight">
                  {index + 1}
                </span>
                <h3 className="mt-4 font-medium text-neutral-100">{step.title}</h3>
                <p className="mt-2 text-sm text-neutral-400">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-neutral-800 px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-2xl font-semibold">
            Built for people who make ads
          </h2>
          <div className="mt-10 grid gap-6 sm:grid-cols-2">
            {CAPABILITIES.map((item) => (
              <div
                key={item.title}
                className="rounded-xl border border-neutral-800 p-6"
              >
                <h3 className="font-medium text-neutral-100">{item.title}</h3>
                <p className="mt-2 text-sm text-neutral-400">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-neutral-800 px-6 py-20 text-center">
        <h2 className="text-2xl font-semibold">Ready to see your ad?</h2>
        <p className="mx-auto mt-3 max-w-md text-neutral-400">
          Write one brief and get a full directorial treatment back.
        </p>
        <Link
          href="/register"
          className="mt-8 inline-block rounded-lg bg-brand px-6 py-3 font-medium text-white transition hover:opacity-90"
        >
          Create an account
        </Link>
      </section>
    </main>
  );
}
