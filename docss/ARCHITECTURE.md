# Primo AI Platform — Master Architecture & Build Plan

## Platform Vision

Primo is an end-to-end AI-powered commercial production studio. It takes a brand brief from a business user and produces a complete video advertisement — from strategic concept and scriptwriting through directorial guidance, asset generation, multi-model video creation, and final stitched export.

Users who prefer to shoot ads with real teams get the same script/direction intelligence without video generation. Users who want fully AI-generated ads get a multi-model aggregator that lets them choose their preferred video engine.

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 14+ (App Router), TypeScript, Tailwind CSS, Shadcn/UI | SSR for SEO on marketing pages, React for app dashboard, great DX |
| Backend API | Python 3.12+, FastAPI | Async-native, best AI/ML ecosystem, typed with Pydantic |
| Task Queue | Celery + Redis (broker) | Battle-tested for long-running video jobs, retries, rate limiting |
| Database | PostgreSQL 16 | ACID for credit ledger, JSONB for flexible schema fields |
| Cache / Sessions | Redis | Fast session store, rate limiting counters, pub/sub for job progress |
| Object Storage | AWS S3 (or Cloudflare R2 for cost) | Video chunks, final exports, brand assets, training data |
| CDN | CloudFront or Cloudflare | Video delivery, asset serving |
| Auth | NextAuth.js (frontend) + JWT verification (backend) | Social login, magic link, credential-based |
| Payments | Stripe + PayPal + Cozzipay | Three gateways, unified credit wallet |
| Video Processing | FFmpeg (via python-ffmpeg or subprocess) | Normalize, stitch, transcode |
| AI - Script/Direction | Gemini 2.5 Flash/Pro or Claude via API (RAG-backed) | Cost-effective, large context for swipe-file retrieval |
| AI - Image Generation | Flux Pro (via fal.ai) or DALL-E 3 | Asset/character pre-generation for video consistency |
| AI - Video Generation | Multi-model aggregator (see Module 6) | fal.ai as unified gateway to Veo, Kling, Seedance, etc. |
| Deployment | Docker Compose (dev), AWS ECS or Railway (prod) | Containerized, scalable, reproducible |
| Monitoring | Sentry (errors), PostHog (product analytics) | Error tracking + usage insights |

---

## Module Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS FRONTEND                              │
│  Marketing ─ Auth ─ Onboarding ─ Dashboard ─ Brief ─ Script View    │
│  Storyboard ─ Video Timeline ─ Export ─ Admin Panel                  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ REST/WebSocket
┌─────────────────────▼───────────────────────────────────────────────┐
│                      FASTAPI BACKEND                                  │
│  Auth ─ Users ─ Projects ─ Briefs ─ Scripts ─ Assets ─ Generation   │
│  Credits ─ Payments ─ Admin ─ Webhooks ─ Model Registry              │
└───┬─────────────┬──────────────┬────────────────────────────────────┘
    │             │              │
    ▼             ▼              ▼
┌────────┐  ┌─────────┐  ┌──────────────────────┐
│ PostgreSQL │  │  Redis  │  │  Celery Workers       │
│ (Data)     │  │ (Cache) │  │  - script_gen         │
└────────────┘  └─────────┘  │  - asset_gen          │
                             │  - video_gen          │
                             │  - video_stitch       │
                             │  - payment_webhooks   │
                             └──────────┬───────────┘
                                        │
                          ┌─────────────▼─────────────┐
                          │  EXTERNAL SERVICES          │
                          │  - fal.ai (Video Models)    │
                          │  - Gemini/Claude (LLM)      │
                          │  - Flux/DALL-E (Images)     │
                          │  - Stripe/PayPal/Cozzipay   │
                          │  - S3 (Storage)             │
                          └────────────────────────────┘
```

---

## Module 1: User Onboarding & Intelligence Collection

### Data to Collect at Registration

| Field | Type | Purpose |
|-------|------|---------|
| Full Name | text | Identity |
| Email | email | Auth, notifications |
| Password / Social Login | auth | Access |
| Company/Brand Name | text | Pre-fill future briefs |
| Country | select | Localization, currency defaults, compliance |
| Industry | select (multi) | Personalized templates, analytics |
| Company Size | select | Tier recommendations |
| Role | select | Creative Director, Marketing Manager, Founder, Agency |
| Primary Use Case | select | AI video generation, Script-only, Both |
| How did you hear about us | select | Attribution |
| Preferred Ad Platforms | multi-select | TikTok, Instagram, YouTube, TV, LinkedIn |
| Monthly Ad Budget Range | select | Tier suggestions |

### Onboarding Flow (Progressive)
1. Email + Password (or Google/social sign-in)
2. Profile step: Name, Company, Country, Industry
3. Preference step: Role, Use Case, Ad Platforms
4. Optional: Upload brand assets immediately (logo, colors, style guide)
5. Land on dashboard with guided first-project wizard

---

## Module 2: Project & Brief Intake Engine

### Persistence, Auto-Save & Resume (How Nothing Gets Lost)

Everything a user creates is persisted server-side in the database, never only in the browser. This guarantees a user can close the tab, log out, switch devices, and return exactly where they left off.

**What gets saved and when:**
- **Brief (draft)**: Auto-saved to `projects.brief` (JSONB) as the user fills the wizard — debounced save on every step and every field blur. A half-finished brief survives a refresh.
- **Generated script**: Saved to `projects.script` (JSONB) the moment the LLM returns it. Each scene is also written to the `scenes` table.
- **Compiled prompts**: Saved per scene in `scenes.compiled_prompt`, so the exact prompt used is always recoverable and editable.
- **Assets**: Saved in `scene_assets` with their status (generated/approved/rejected/uploaded).
- **Generated videos**: Each clip URL in `scenes.video_url`; final stitched video in `projects.final_video_url`.

**Project state machine** (`projects.status`) drives resume:
```
draft → scripted → assets_ready → generating → completed
                                             → failed
```
When a user opens a project, the frontend reads `status` and routes them to the correct step automatically:
- `draft` → back to the brief wizard with all fields pre-filled
- `scripted` → the storyboard/script view
- `assets_ready` → the asset review step
- `generating` → the timeline with live per-scene progress
- `completed` → the export page with the finished video

**Partial progress is preserved.** Because each scene tracks its own `generation_status`, if 3 of 5 scenes finished before the user left, those 3 clips are already in S3 and shown as done. Only the remaining scenes need to run when they resume. No credits are re-charged for work already completed.

**Project folder view**: `/dashboard/projects` lists every project the user owns with a thumbnail, title, status badge, last-modified date, and credits spent. This is their "project folder." From here they open, duplicate, rename, or delete a project. Deleted projects are soft-deleted (30-day recovery window) before permanent removal.

**Why DB, not browser cache**: Browser cache/localStorage is fragile (cleared on logout, not synced across devices, lost on crashes). Server-side persistence is the correct pattern for anything the user paid credits to create. We may use lightweight client caching (React Query) purely for snappy UI, but the source of truth is always the database.

### Brief Form (Multi-step wizard)

**Step A — Brand Identity**
- Brand name
- Website URL or elevator pitch (textarea)
- Brand assets upload: Logo (PNG), product screenshots, hex color codes
- Brand voice/tone: Professional, Playful, Bold, Minimal, Luxury (multi-select)

**Step B — Product & Audience**
- Product/service being advertised
- Target audience persona (dropdown + custom input)
- Core customer pain point
- Key differentiator / unique selling proposition

**Step C — Competitive Landscape**
- Primary competitor(s)
- Market sentiment / customer complaints about competitors
- What the user wants to say differently

**Step D — Campaign Configuration**
- Campaign objective: Conversion, Brand Awareness, Education, App Install, Event
- Ad category / narrative arc:
  - Problem-Agitation-Solution (PAS)
  - Us vs. Competitor Contrast
  - Social Proof / Transformation
  - High-Energy Disruptor
  - Emotional Storytelling
  - Product Demo / Walkthrough
  - AI Recommended (let the system choose)
- Format: 9:16 Vertical | 16:9 Landscape | 1:1 Square
- Target duration: 15s | 30s | 45s | 60s
- Target platform: TikTok, Instagram Reels, YouTube Shorts, YouTube Pre-roll, TV/Cinema, LinkedIn

**Step E — Assets & Characters (Optional)**
- Upload character references (photos of people/mascots to use)
- Upload product photos for accurate representation
- Upload existing brand footage for style reference
- Notes to the AI director (free text)

### Backend Payload Schema

```json
{
  "project_id": "proj_abc123",
  "brief": {
    "brand": {
      "name": "Cozzipay",
      "pitch": "A wallet-based digital payment gateway enabling 1-click checkouts.",
      "colors": ["#3400D1", "#FF007A", "#FFD600"],
      "voice_tone": ["professional", "bold"],
      "assets": {
        "logo_url": "s3://primo-assets/proj_abc123/logo.png",
        "product_shots": ["s3://..."],
        "style_guide_url": null
      }
    },
    "product": {
      "name": "1-click checkout SDK",
      "target_audience": "E-commerce Store Owners",
      "pain_point": "High cart abandonment due to tedious checkout forms",
      "differentiator": "One-tap wallet payment, no forms needed"
    },
    "competition": {
      "competitors": ["Legacy payment processors"],
      "market_sentiment": "Customers hate typing billing info on mobile",
      "positioning": "Modern, frictionless alternative"
    },
    "campaign": {
      "objective": "conversion",
      "ad_category": "problem-agitation-solution",
      "format": "9:16",
      "duration_seconds": 30,
      "platform": "tiktok",
      "characters_uploaded": ["s3://primo-assets/proj_abc123/char_01.png"]
    }
  }
}
```

---

## Module 3: AI Script & Direction Engine (RAG-backed)

### Why RAG over Fine-Tuning (for v1)

| Factor | RAG | Fine-Tuning |
|--------|-----|-------------|
| Iteration speed | Instant (update DB) | Days (re-train) |
| Cost | $0 upfront | $50-500+ per run |
| Flexibility | Add new categories anytime | Locked to training data |
| Quality ceiling | 90% of fine-tuned | 100% |
| When to switch | Only if RAG quality plateaus | Phase 6 |

### How It Works

1. User submits brief (Module 2 payload)
2. Backend retrieves 3-5 most relevant ad blueprints from the swipe-file DB matching:
   - Same ad category (PAS, Contrast, etc.)
   - Same or similar industry
   - Same format/duration
3. Constructs a prompt:
   - System: "You are an elite commercial director..."
   - Context: Retrieved ad blueprints as examples
   - User: The brand brief JSON
   - Output format: Strict JSON schema (scenes array)
4. Calls Gemini 2.5 Flash (or Claude) with structured output enforcement
5. Returns scene-by-scene master script

### Output Schema (Per Scene)

```json
{
  "campaign_title": "Stop the Checkout Chaos",
  "total_duration_seconds": 30,
  "scenes": [
    {
      "scene_number": 1,
      "scene_label": "The Hook",
      "duration_seconds": 5,
      "script_text": "Tired of losing customers right at the checkout page?",
      "voiceover_direction": "Frustrated male voice, slightly sarcastic tone",
      "visual_description": "Close-up of a thumb hesitating over a cluttered mobile checkout form. Error popups flash red.",
      "camera_movement": "Slow push-in, shallow depth of field",
      "color_grading": "Desaturated blues, high contrast, cold tones",
      "lighting": "Harsh overhead phone screen glow, dark surroundings",
      "audio_sfx": "Subtle tension hum, digital error beeps",
      "graphics_overlay": null,
      "brand_elements": "None in this scene (problem setup)",
      "veo_prompt": "Close-up tracking shot of a frustrated person's thumb hovering over a glowing smartphone screen showing a cluttered checkout form with red error popups. Cinematic soft-box lighting, desaturated cool blue tones. Subtle tense electronic hum. 9:16 vertical.",
      "image_gen_needed": [
        {
          "asset_type": "background_element",
          "description": "Cluttered mobile checkout form UI with multiple input fields and red error badges",
          "style": "photorealistic app screenshot"
        }
      ]
    }
  ],
  "music_direction": "Tense electronic buildup transitioning to uplifting synth at solution reveal",
  "overall_color_palette": "Cold blues → Warm brand purple/gold transition",
  "target_emotion_arc": "frustration → hope → confidence → action"
}
```

### Export Options (Script-Only Users)

Users who want to shoot with real teams can:
- View full script in a formatted storyboard layout
- Export as PDF (director's treatment)
- Export as Google Docs format
- Download individual scene cards
- Get a shot list breakdown for their DP/camera crew

---

## Module 4: Asset Pre-Generation Engine

### Problem This Solves

Video generation models produce inconsistent results when they have to "imagine" brand elements, characters, or products. By pre-generating precise reference images and feeding them as input frames, we dramatically improve accuracy and brand consistency.

### Pipeline

1. Script engine identifies `image_gen_needed` items per scene
2. For each required asset:
   - Construct an image generation prompt incorporating brand colors, style, and uploaded references
   - Call image model (Flux Pro via fal.ai, or DALL-E 3)
   - Store result in S3 linked to the scene
3. User reviews generated assets in the UI
   - Approve / Re-generate / Upload their own replacement
4. Approved assets become reference inputs for video generation

### Character Consistency

- If user uploads character photos: use those as reference images directly
- If AI-generated characters needed: generate a character sheet first (front, 3/4, side) and reuse across all scenes
- Store approved character images in a per-project character library

### Credit Cost
- Image generation: 0.5 credits per image
- User-uploaded replacements: free

---

## Module 5: Ad Intelligence & Swipe File System

### Swipe File Database Schema

```sql
CREATE TABLE ad_blueprints (
  id UUID PRIMARY KEY,
  title VARCHAR(255),
  source_video_url TEXT,          -- Original reference video (internal only)
  industry VARCHAR(100),           -- fintech, ecommerce, saas, fmcg, etc.
  ad_category VARCHAR(100),        -- PAS, contrast, social_proof, disruptor, etc.
  psychological_triggers TEXT[],   -- FOMO, social_proof, pain_relief, etc.
  structural_arc JSONB,            -- Scene-by-scene breakdown
  duration_seconds INTEGER,
  format VARCHAR(10),              -- 9:16, 16:9, 1:1
  platform VARCHAR(50),            -- tiktok, youtube, instagram, tv
  hook_style VARCHAR(100),         -- question, bold_statement, visual_shock, etc.
  pacing VARCHAR(50),              -- fast, moderate, slow_build
  color_palette TEXT[],
  camera_techniques TEXT[],
  effectiveness_score FLOAT,       -- Manual rating 1-10
  embedding VECTOR(1536),          -- For semantic search/RAG retrieval
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### How Blueprints Are Created

1. Upload a winning commercial video to the analysis pipeline
2. Send to Gemini 2.5 Pro with multimodal video understanding:
   - "Deconstruct this ad. Identify the psychological framework, structural arc, pacing, camera techniques, color strategy, and hook mechanism. Output as JSON."
3. Human curator reviews and tags (industry, category, effectiveness score)
4. Generate embedding from the text description for vector similarity search
5. Store in `ad_blueprints` table

### RAG Retrieval at Script Time

When a user submits a brief:
1. Embed the brief text
2. Query `ad_blueprints` with filters (category, industry, format) + vector similarity
3. Return top 3-5 most relevant blueprints
4. Inject as context examples in the LLM prompt

---

## Module 6: Video Generation Model Aggregator

### Core Design Principle: Provider Abstraction

Every video model is registered in a `video_models` table. The platform treats them all through a unified interface. Adding a new model = adding a database row + implementing a thin adapter class. No frontend or pipeline changes needed.

### Supported Models (Launch)

| Model | Provider API | Strengths | Cost/sec (approx) | Credit Multiplier |
|-------|-------------|-----------|-------------------|-------------------|
| Veo 3.1 Lite | fal.ai / Google | Cheapest, decent quality | $0.03-0.05 | x0.5 |
| Veo 3.1 | fal.ai / Google | High quality, 4K capable | $0.20 | x1.5 |
| Kling 3.0 | fal.ai / PiAPI | Native audio, cinematic | $0.08-0.13 | x1.0 |
| Kling 3.0 Turbo | fal.ai | Faster, with audio | $0.11 | x1.0 |
| Seedance 2.0 | fal.ai | Best quality, audio+video in one pass | ~$0.15-0.25 | x2.0 |
| Runway Gen-4.5 | Runway API | Multi-shot character consistency | $0.12 | x1.5 |
| MiniMax Hailuo | fal.ai | Cheapest 4K option | $0.08 | x0.8 |
| Wan 2.5 | fal.ai / self-hosted | Open weights, cheapest at scale | $0.03-0.06 | x0.5 |

### Model Registry Schema

```sql
CREATE TABLE video_models (
  id UUID PRIMARY KEY,
  slug VARCHAR(50) UNIQUE,          -- 'veo-3.1-lite', 'kling-3.0', etc.
  display_name VARCHAR(100),
  provider VARCHAR(50),             -- 'fal', 'runway', 'google', 'replicate'
  api_endpoint TEXT,
  model_id VARCHAR(200),            -- Provider's model identifier
  max_duration_seconds INTEGER,
  supported_resolutions TEXT[],     -- ['720p', '1080p', '4k']
  supported_aspect_ratios TEXT[],   -- ['9:16', '16:9', '1:1']
  supports_audio BOOLEAN,
  supports_image_reference BOOLEAN,
  supports_video_extension BOOLEAN,
  cost_per_second_usd DECIMAL(6,4),
  credit_multiplier DECIMAL(4,2),   -- x0.5, x1.0, x2.0, etc.
  is_enabled BOOLEAN DEFAULT true,
  quality_tier VARCHAR(20),         -- 'budget', 'standard', 'premium'
  avg_generation_time_seconds INTEGER,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Adapter Pattern (Python)

```python
# base class
class VideoModelAdapter(ABC):
    @abstractmethod
    async def generate(self, prompt: str, config: VideoGenConfig) -> VideoGenResult:
        pass

    @abstractmethod
    async def check_status(self, job_id: str) -> JobStatus:
        pass

# Example: fal.ai adapter (covers Veo, Kling, Seedance, Wan, MiniMax)
class FalVideoAdapter(VideoModelAdapter):
    async def generate(self, prompt, config):
        result = await fal_client.submit(
            config.model_id,  # e.g. "fal-ai/veo3"
            arguments={
                "prompt": prompt,
                "aspect_ratio": config.aspect_ratio,
                "duration": config.duration_seconds,
                "resolution": config.resolution,
                "image_url": config.reference_image_url,  # optional
            }
        )
        return VideoGenResult(job_id=result.request_id, provider="fal")

# Example: Runway adapter
class RunwayVideoAdapter(VideoModelAdapter):
    async def generate(self, prompt, config):
        # Runway has its own SDK/API
        ...
```

### User-Facing Model Selection UI

On the video generation step:
- Show model cards with: name, quality tier badge, estimated time, credit cost
- Default recommendation based on their brief (e.g., if they need audio → suggest Seedance/Kling)
- "Let AI choose best model" toggle (platform picks based on brief requirements)
- Cost preview: "This 30s ad (5 scenes) will cost ~25 credits with Kling 3.0"

### Adding New Models (Admin)

Admin dashboard → Model Registry → Add Model:
- Fill in provider, API endpoint, capabilities, pricing
- Toggle enabled/disabled
- Set credit multiplier
- That's it. No code deployment needed for fal.ai models (just a new model_id).

---

## Module 7: Video Generation Pipeline

### Full Pipeline Flow

```
Brief → Script → Asset Pre-gen → User Approval → Video Generation → Stitch → Preview → Export
```

### Step-by-step

1. **Prompt Compilation** (per scene):
   - Take the scene's `veo_prompt` from the script
   - Append brand consistency tags (colors, style)
   - Attach reference image URL (from Module 4 pre-gen or user upload)
   - Format according to the selected model's best practices

2. **Parallel Scene Generation**:
   - Submit all scenes to the chosen video model simultaneously
   - Each scene = independent async Celery task
   - Track progress per-scene in the DB (queued → generating → complete → failed)
   - Push progress updates to frontend via WebSocket/SSE

3. **Per-Scene Result Handling**:
   - On success: download clip to S3, generate thumbnail, update status
   - On failure: retry up to 3x with exponential backoff
   - After 3 failures: mark scene as failed, partial refund for that scene

4. **Stitching** (triggered when all scenes complete):
   - Download all scene clips from S3 to worker's temp storage
   - Normalize: lock frame rate (24fps), resolution, pixel format, audio codec
   - Concatenate with FFmpeg using complex filtergraph
   - Optional: add background music track, fade transitions
   - Upload final MP4 to S3
   - Generate preview thumbnail + low-res preview version

5. **User Preview & Iteration**:
   - Timeline view showing each scene as a block
   - Play full stitched video
   - Per-scene controls: Re-roll (regenerate), Swap Model, Edit Prompt
   - Re-roll triggers only that scene's regeneration + re-stitch

### FFmpeg Normalization Command

```bash
ffmpeg -i scene_01.mp4 -i scene_02.mp4 -i scene_03.mp4 \
  -filter_complex "[0:v]fps=24,scale=1080:1920,setsar=1[v0]; \
                   [1:v]fps=24,scale=1080:1920,setsar=1[v1]; \
                   [2:v]fps=24,scale=1080:1920,setsar=1[v2]; \
                   [v0][0:a][v1][1:a][v2][2:a]concat=n=3:v=1:a=1[outv][outa]" \
  -map "[outv]" -map "[outa]" \
  -c:v libx264 -preset medium -crf 21 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  final_ad.mp4
```

---

## Module 8: Credit & Monetization System

### Everything Is Admin-Configurable (No Hardcoded Prices)

A hard rule for this platform: **no price, credit cost, or ratio is ever hardcoded in the application.** Every chargeable action reads its cost from the database at runtime. Admins change pricing from the dashboard and it takes effect immediately, with no code deployment. This lets you tune margins as API costs shift.

### The Credit-to-Dollar Ratio

A single global setting defines what one credit is worth in USD. This is the anchor for all pricing math.

```sql
CREATE TABLE platform_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(100) UNIQUE NOT NULL,
  value JSONB NOT NULL,
  description TEXT,
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Seeded example
-- key: 'credit_usd_ratio', value: {"usd_per_credit": 0.50}
-- Meaning 1 credit = $0.50 to the end user.
```

**How margin works**: If Kling 3.0 costs you $0.13/sec and a 6-second scene costs you ~$0.78, you charge (say) 5 credits × $0.50 = $2.50 to the user. Your gross margin on that scene is $2.50 − $0.78 = $1.72. The admin dashboard shows this margin live so you never price below cost.

### Action Pricing Table (Admin-Managed)

Instead of hardcoded numbers, each chargeable action is a row admins can edit:

```sql
CREATE TABLE action_pricing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_key VARCHAR(100) UNIQUE NOT NULL, -- 'script_generation', 'asset_image', 'video_scene', 'scene_reroll'
  display_name VARCHAR(150),
  base_credits DECIMAL(10,2) NOT NULL,
  unit VARCHAR(50),                        -- 'per_generation', 'per_image', 'per_scene', 'per_second'
  is_enabled BOOLEAN DEFAULT true,
  notes TEXT,
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

| action_key | display_name | base_credits (default) | unit |
|-----------|-------------|----------------------|------|
| script_generation | Script & Direction | 2 | per_generation |
| asset_image | Asset Image | 0.5 | per_image |
| video_scene | Video Scene | 5 | per_scene (× model multiplier) |
| scene_reroll | Scene Re-roll | 5 | per_scene (× model multiplier) |
| stitching | Video Stitch & Export | 0 | per_generation |
| script_export | Script PDF/DOCX Export | 0 | per_generation |

Final cost of a video scene = `action_pricing.base_credits` × `video_models.credit_multiplier`. Both values are admin-editable, so you can tune per-action pricing AND per-model multipliers independently.

### Cost Preview (Before Charging)

Before any generation, the backend computes the exact credit cost from the current DB values and shows the user a confirmation:
> "This 30s ad (5 scenes) with Kling 3.0 will cost 27 credits (≈ $13.50). You have 200 credits. Proceed?"

The user is only charged after confirming, and the charge uses the same values shown in the preview (locked at confirmation time to avoid mid-flight price changes).

### Subscription Tiers (Admin-Managed)

Tiers are also DB rows, not hardcoded:

```sql
CREATE TABLE subscription_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(50) UNIQUE NOT NULL,       -- 'starter', 'growth', 'agency'
  display_name VARCHAR(100),
  price_usd DECIMAL(10,2),
  credits_per_month INTEGER,
  billing_interval VARCHAR(20),           -- monthly, yearly
  features JSONB,                         -- feature list for pricing page
  stripe_price_id VARCHAR(255),
  paypal_plan_id VARCHAR(255),
  is_enabled BOOLEAN DEFAULT true,
  sort_order INTEGER,
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE credit_packages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(50) UNIQUE NOT NULL,       -- 'topup_small', 'topup_medium'
  display_name VARCHAR(100),
  price_usd DECIMAL(10,2),
  credits INTEGER,
  bonus_credits INTEGER DEFAULT 0,        -- promotional bonus
  is_enabled BOOLEAN DEFAULT true,
  sort_order INTEGER,
  updated_at TIMESTAMP DEFAULT NOW()
);
```

**Default seeded values** (all editable from admin):

| Tier | Price/month | Credits |
|------|------------|---------|
| Starter | $29 | 50 |
| Growth | $79 | 200 |
| Agency | $199 | 600 |
| Enterprise | Custom | Custom |

Pay-as-you-go top-ups: $10 = 20 credits, $49 = 120 credits, $99 = 300 credits. Admins can add bonus credits or change any of these instantly.

### Admin Pricing Controls (Dashboard)

The admin billing panel lets you:
- Set the global **credit-to-USD ratio**
- Edit **base credits** for every action
- Edit **credit multiplier** and **enabled state** for every video model
- Create/edit/disable **subscription plans** and **credit packages**
- See **live margin analysis** per model (your API cost vs. what users pay)
- Add **promotional bonus credits** to packages
- Grant **manual credits** to any user (support, refunds, goodwill)

### Database Schema

```sql
CREATE TABLE wallets (
  id UUID PRIMARY KEY,
  user_id UUID UNIQUE REFERENCES users(id),
  balance_credits DECIMAL(10,2) NOT NULL DEFAULT 0,
  lifetime_purchased DECIMAL(10,2) DEFAULT 0,
  lifetime_spent DECIMAL(10,2) DEFAULT 0,
  updated_at TIMESTAMP
);

CREATE TABLE credit_transactions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  amount DECIMAL(10,2) NOT NULL,       -- positive = addition, negative = deduction
  balance_after DECIMAL(10,2) NOT NULL,
  transaction_type VARCHAR(50),         -- purchase, subscription_grant, script_gen, video_gen, reroll, refund
  reference_type VARCHAR(50),           -- stripe_invoice, paypal_order, cozzipay_session, project, scene
  reference_id VARCHAR(255),
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast balance audits
CREATE INDEX idx_credit_tx_user_created ON credit_transactions(user_id, created_at DESC);
```

### Payment Gateways

**Stripe** — Primary for international cards, subscriptions
- Checkout Session for one-time credit purchases
- Stripe Billing for recurring subscriptions
- Webhook: `checkout.session.completed`, `invoice.paid`, `customer.subscription.*`

**PayPal** — Alternative for users who prefer it
- PayPal Checkout SDK (server-side order creation)
- Webhook: `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`

**Cozzipay** — Wallet-based payments (as documented in their API)
- `POST /v1/checkout/sessions` to create payment
- Redirect to `pay.cozzipay.com/checkout/{session_id}`
- Webhook: `checkout.completed`
- Signature verification: HMAC-SHA256 on raw body
- Supports subscriptions via `line_items[].type = "subscription"`

### Payment Flow (Unified)

1. User clicks "Buy 100 Credits" or "Subscribe to Growth"
2. Frontend calls backend: `POST /api/payments/create-session`
3. Backend creates checkout session with chosen gateway
4. User completes payment on gateway's hosted page
5. Gateway fires webhook to our backend
6. Backend verifies signature, credits wallet, logs transaction
7. Frontend polls or receives WebSocket update showing new balance

---

## Module 9: Admin Dashboard

### Features

- **User Management**: View all users, edit roles, suspend accounts, impersonate
- **Model Registry**: Add/edit/disable video models, set pricing/multipliers
- **Swipe File Manager**: Upload ads for analysis, review/approve blueprints, manage categories
- **Pricing & Fees Control**: Set credit-to-USD ratio, edit per-action credit costs, edit per-model multipliers, manage subscription plans and credit packages, view live margin analysis
- **Credit Operations**: Manual credit grants, view ledger, process refunds
- **Payment Analytics**: Revenue by gateway, MRR, churn, top-up frequency
- **Generation Analytics**: Jobs by model, success rates, avg generation time, failure reasons
- **Content Moderation**: Flag/review generated content, block users
- **Feature Flags**: Enable/disable any module or model globally or per-tier
- **System Health**: Queue depth, worker status, API latency, error rates

### Feature Flag System

```sql
CREATE TABLE feature_flags (
  id UUID PRIMARY KEY,
  key VARCHAR(100) UNIQUE,          -- 'video_generation_enabled', 'model_seedance_enabled'
  description TEXT,
  is_enabled BOOLEAN DEFAULT true,
  applies_to VARCHAR(50),           -- 'all', 'tier:agency', 'user:uuid'
  config JSONB,                     -- Additional configuration
  updated_at TIMESTAMP
);
```

Every module checks feature flags before executing. This allows:
- Gradual rollout of new models
- Disabling a buggy feature without deployment
- Tier-gating premium features
- A/B testing

---

## Module 10: Frontend Architecture (Next.js)

### Route Structure

```
/                           → Marketing landing page
/pricing                    → Pricing page
/login                      → Auth
/register                   → Onboarding wizard
/dashboard                  → User home (projects list, quick stats)
/dashboard/projects/new     → Brief intake wizard (Module 2)
/dashboard/projects/[id]    → Project overview
/dashboard/projects/[id]/script    → Script & storyboard view
/dashboard/projects/[id]/assets    → Asset review & approval
/dashboard/projects/[id]/generate  → Model selection & generation
/dashboard/projects/[id]/timeline  → Video timeline, preview, re-roll
/dashboard/projects/[id]/export    → Download final video + assets
/dashboard/billing          → Credits, subscriptions, payment history
/dashboard/settings         → Profile, brand defaults, API keys
/admin                      → Admin panel (all admin routes)
/admin/users
/admin/models
/admin/swipe-file
/admin/analytics
/admin/features
```

### Key UI Experiences

**Script/Storyboard View** (for all users, especially script-only):
- Vertical card layout: each scene = a card
- Card shows: scene label, duration badge, script text, visual description, camera notes
- Expand card for full directorial details
- Export buttons: PDF, DOCX, Copy All
- "Generate Video" CTA at bottom (transitions to generation flow)

**Video Timeline View**:
- Horizontal timeline strip (like a video editor)
- Each scene block shows: thumbnail, duration, model used, status badge
- Click scene → side panel with details, re-roll button, prompt editor
- Full-width video player above timeline
- Progress indicators during generation (per-scene progress bars)

**Export/Download**:
- Final stitched video (MP4, multiple quality options)
- Individual scene clips (for editing in Premiere/DaVinci)
- Script PDF (formatted director's treatment)
- Storyboard images (the pre-generated assets)
- Veo/model prompts as text file (for users who want to run elsewhere)

---

## Module 11: Scalability & Operations

### Queue Architecture

```
Redis Broker
├── queue:script_generation     (priority: high, concurrency: 10)
├── queue:asset_generation      (priority: medium, concurrency: 20)
├── queue:video_generation      (priority: medium, concurrency: 5 per model)
├── queue:video_stitching       (priority: low, concurrency: 3)
├── queue:payment_webhooks      (priority: critical, concurrency: 5)
└── queue:analytics             (priority: lowest, concurrency: 2)
```

### Job State Machine

```
QUEUED → PROCESSING → COMPLETED
                   → FAILED → RETRYING → COMPLETED
                                       → PERMANENTLY_FAILED → REFUNDED
```

### Storage Lifecycle Rules

| Asset Type | Retention | Location |
|-----------|-----------|----------|
| Brand uploads (logo, photos) | Indefinite | S3 Standard |
| Pre-generated scene assets | 90 days after project completion | S3 Standard → IA |
| Raw video scene clips | 7 days after final export download | S3 Standard → Delete |
| Final stitched video | 30 days | S3 Standard |
| Training data (swipe files) | Indefinite | S3 IA |

### Rate Limiting

- API: 100 req/min per user (general), 10 req/min for generation endpoints
- Video generation: Max 3 concurrent jobs per user
- Credit check before every generation job (fail-fast, no queue waste)

---

## Phased Build Plan

### Phase 0 — Foundations (Week 1-2)
- [ ] Initialize Next.js frontend project (App Router, TypeScript, Tailwind, Shadcn)
- [ ] Initialize FastAPI backend project (project structure, Pydantic models, Alembic migrations)
- [ ] PostgreSQL schema: users, wallets, credit_transactions, projects, scenes
- [ ] Auth system: registration, login, JWT, session management
- [ ] Docker Compose for local dev (postgres, redis, api, frontend, worker)
- [ ] Basic admin user seeding

### Phase 1 — Script MVP (Week 3-5)
- [ ] Onboarding wizard UI
- [ ] Brief intake form (all steps)
- [ ] RAG retrieval system (basic: category + industry filter, later: vector search)
- [ ] Script generation endpoint (Gemini API integration)
- [ ] Script/storyboard display UI (scene cards, expand, formatted view)
- [ ] PDF/DOCX export for script-only users
- [ ] Credit deduction for script generation
- [ ] Basic dashboard (project list, project detail)

### Phase 2 — Ad Intelligence Pipeline (Week 5-7)
- [ ] Admin: swipe file upload & analysis pipeline
- [ ] Multimodal video analysis (send ads to Gemini for deconstruction)
- [ ] Blueprint storage with embeddings (pgvector)
- [ ] RAG upgrade: semantic similarity retrieval
- [ ] Category management UI (admin)
- [ ] User-facing category picker with visual examples

### Phase 3 — Asset Pre-generation (Week 7-9)
- [ ] Image generation integration (Flux Pro via fal.ai)
- [ ] Per-scene asset identification from script
- [ ] Asset review UI (approve/reject/regenerate/upload own)
- [ ] Character consistency system (character sheet generation)
- [ ] Brand asset injection into generation prompts

### Phase 4 — Video Generation & Stitching (Week 9-13)
- [ ] Model registry (DB + admin CRUD)
- [ ] Video model adapter layer (base class + fal.ai adapter)
- [ ] Model selection UI (cards, cost preview, recommendations)
- [ ] Async generation queue (Celery tasks, progress tracking)
- [ ] WebSocket/SSE for real-time progress in frontend
- [ ] FFmpeg stitching worker (normalize + concat)
- [ ] Timeline preview UI
- [ ] Per-scene re-roll functionality
- [ ] Storage lifecycle automation (S3 lifecycle rules)

### Phase 5 — Monetization & Payments (Week 13-15)
- [ ] Credit wallet system (ledger pattern)
- [ ] Stripe integration (checkout, subscriptions, webhooks)
- [ ] PayPal integration (checkout, webhooks)
- [ ] Cozzipay integration (checkout sessions, webhook verification)
- [ ] Billing UI (plans, top-up, transaction history)
- [ ] Subscription management (upgrade/downgrade/cancel)
- [ ] Admin: manual credit operations

### Phase 6 — Admin & Ops Hardening (Week 15-17)
- [ ] Full admin dashboard
- [ ] Feature flag system
- [ ] Rate limiting & abuse prevention
- [ ] Error monitoring (Sentry)
- [ ] Auto-refund on permanent failures
- [ ] Content moderation layer
- [ ] Analytics dashboard (PostHog events)

### Phase 7 — Polish & Launch (Week 17-19)
- [ ] Landing page & marketing site
- [ ] User onboarding optimization (guided wizard, tooltips)
- [ ] Mobile-responsive dashboard
- [ ] Performance optimization (lazy loading, CDN, caching)
- [ ] Security audit (OWASP top 10, API hardening)
- [ ] Load testing
- [ ] Beta user testing & feedback loop

### Phase 8 — Post-Launch (Ongoing)
- [ ] Add new video models as they release (just adapter + DB row)
- [ ] Fine-tuning exploration (if RAG quality plateaus)
- [ ] API access for enterprise users
- [ ] Team/workspace features (agencies managing multiple brands)
- [ ] Voiceover generation integration
- [ ] Background music library / AI music generation
- [ ] A/B test variant generation (same brief → multiple ad versions)

---

## Multi-Client & Mobile Readiness

The platform is API-first by design, which means a mobile app can be added later with **zero backend changes**. The FastAPI backend is the single source of truth; the web app is just one client of it. A mobile app is simply another client hitting the same endpoints.

### What Makes Mobile Easy Later

- **Clean client/server split**: all business logic (credit costs, authorization, pipeline orchestration, pricing) lives in the backend. Clients only render UI and call the API. The security standard enforces this ("frontend checks are UX, not security").
- **Token-based auth**: JWT access + refresh tokens work identically on web and mobile. No cookie-only session coupling that would trip up native apps.
- **Shared packages**: `packages/shared-types`, `packages/api-client`, and `packages/validation` are consumed by both web and mobile, keeping contracts and validation in sync.
- **OpenAPI spec**: FastAPI auto-generates an OpenAPI schema. Mobile (and web) types are generated from it, so the API contract can never silently drift from the clients.

### Recommended Mobile Stack (When You Get There)

- **React Native (Expo)** — maximizes reuse of your existing TypeScript, API client, and Zod validation from the web app.
- **Payments on mobile**: Cozzipay documents a React Native WebView checkout + deep-link return flow; Stripe and PayPal both have native mobile SDKs. All three plug into the same backend webhook/verification logic already built for web.
- **Real-time progress**: the same WebSocket/SSE generation-progress channel used by web works on mobile.

### Rule to Keep It Easy

Do not add platform-specific business logic to any client. If a new rule is needed, it goes in the backend. As long as this holds, adding mobile (or a desktop app, or a public API for enterprise) stays a UI-only effort. Mobile is slotted into the build plan at Phase 8 (post-launch), but the foundation for it is laid from day one.

---

## Key Architecture Decisions Summary

1. **RAG over fine-tuning** for v1. Build the swipe-file pipeline either way.
2. **fal.ai as primary video API gateway** — one SDK, one billing, access to all major models. Add direct API adapters only for models not on fal.
3. **Adapter pattern for models** — new model = new DB row + adapter class (often just a different model_id on the same fal adapter).
4. **Pre-generate assets before video** — dramatically reduces video generation failures and improves brand consistency.
5. **Immutable credit ledger** — never a mutable balance without a transaction log.
6. **Feature flags everywhere** — every module, every model can be toggled without deployment.
7. **Script-first value** — the platform is useful even without video generation. Script-only users are a valid market segment.
8. **Hybrid preview** — auto-stitch in background, show timeline for iteration.

---

## Project Name: **Primo**

Repository structure defined in the next document (PROJECT_STRUCTURE.md).
