export interface BrandSection {
  name?: string;
  pitch?: string;
  industry?: string;
  colors?: string[];
  voice_tone?: string[];
  asset_keys?: string[];
}

export interface ProductSection {
  name?: string;
  target_audience?: string;
  pain_point?: string;
  differentiator?: string;
}

export interface CompetitionSection {
  competitors?: string[];
  market_sentiment?: string;
  positioning?: string;
}

export interface CampaignSection {
  objective?: string;
  ad_category?: string;
  format?: "9:16" | "16:9" | "1:1";
  duration_seconds?: number;
  platform?: string;
}

export interface Brief {
  brand?: BrandSection;
  product?: ProductSection;
  competition?: CompetitionSection;
  campaign?: CampaignSection;
  director_notes?: string;
}

export const AD_CATEGORIES = [
  {
    value: "problem-agitation-solution",
    label: "Problem → Agitation → Solution",
    description: "Open on a real frustration, amplify it, then land your product as the fix.",
  },
  {
    value: "us-vs-competitor",
    label: "Us vs. Competitor",
    description: "Contrast the old way against your modern alternative.",
  },
  {
    value: "social-proof",
    label: "Social Proof / Transformation",
    description: "Lead with results and the before-and-after payoff.",
  },
  {
    value: "high-energy-disruptor",
    label: "High-Energy Disruptor",
    description: "Fast cuts and pattern interrupts built for the scroll.",
  },
  {
    value: "emotional-storytelling",
    label: "Emotional Storytelling",
    description: "Build a narrative that earns feeling before the pitch.",
  },
  {
    value: "product-demo",
    label: "Product Demo",
    description: "Show exactly how it works, step by step.",
  },
] as const;

export const OBJECTIVES = [
  { value: "conversion", label: "Conversion / Sales" },
  { value: "awareness", label: "Brand Awareness" },
  { value: "education", label: "Educational / Feature Launch" },
  { value: "app_install", label: "App Installs" },
] as const;

export const FORMATS = [
  { value: "9:16", label: "9:16 Vertical", hint: "TikTok, Reels, Shorts" },
  { value: "16:9", label: "16:9 Landscape", hint: "YouTube, web" },
  { value: "1:1", label: "1:1 Square", hint: "Feed posts" },
] as const;

export const DURATIONS = [15, 30, 45, 60] as const;

export const VOICE_TONES = [
  "Professional",
  "Playful",
  "Bold",
  "Minimal",
  "Luxury",
  "Warm",
] as const;
