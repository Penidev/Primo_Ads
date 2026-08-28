# Primo — Project Structure & Scaffolding Plan

## Monorepo Layout

```
primo/
├── apps/
│   ├── mobile/                       # React Native (Expo) app — ADDED LATER (Phase 8+)
│   │                                 # Consumes the same FastAPI backend + shared packages.
│   │                                 # No backend changes required to add this.
│   ├── web/                          # Next.js frontend
│   │   ├── app/                      # App Router pages
│   │   │   ├── (marketing)/          # Public pages (landing, pricing)
│   │   │   │   ├── page.tsx
│   │   │   │   ├── pricing/page.tsx
│   │   │   │   └── layout.tsx
│   │   │   ├── (auth)/               # Auth pages
│   │   │   │   ├── login/page.tsx
│   │   │   │   ├── register/page.tsx
│   │   │   │   └── layout.tsx
│   │   │   ├── (dashboard)/          # Protected app routes
│   │   │   │   ├── layout.tsx        # Dashboard shell (sidebar, topbar)
│   │   │   │   ├── page.tsx          # Dashboard home
│   │   │   │   ├── projects/
│   │   │   │   │   ├── page.tsx      # Project list
│   │   │   │   │   ├── new/page.tsx  # Brief wizard
│   │   │   │   │   └── [id]/
│   │   │   │   │       ├── page.tsx          # Project overview
│   │   │   │   │       ├── script/page.tsx   # Script & storyboard
│   │   │   │   │       ├── assets/page.tsx   # Asset review
│   │   │   │   │       ├── generate/page.tsx # Model selection
│   │   │   │   │       ├── timeline/page.tsx # Video timeline
│   │   │   │   │       └── export/page.tsx   # Download & export
│   │   │   │   ├── billing/page.tsx
│   │   │   │   └── settings/page.tsx
│   │   │   ├── (admin)/              # Admin panel
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx          # Admin dashboard
│   │   │   │   ├── users/page.tsx
│   │   │   │   ├── models/page.tsx
│   │   │   │   ├── swipe-file/page.tsx
│   │   │   │   ├── analytics/page.tsx
│   │   │   │   └── features/page.tsx
│   │   │   ├── api/                  # Next.js API routes (BFF / proxy)
│   │   │   │   └── auth/[...nextauth]/route.ts
│   │   │   ├── layout.tsx            # Root layout
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/                   # Shadcn/UI primitives
│   │   │   ├── layout/               # Sidebar, Topbar, Footer
│   │   │   ├── brief/                # Brief wizard steps
│   │   │   │   ├── StepBrand.tsx
│   │   │   │   ├── StepProduct.tsx
│   │   │   │   ├── StepCompetition.tsx
│   │   │   │   ├── StepCampaign.tsx
│   │   │   │   └── StepAssets.tsx
│   │   │   ├── script/               # Script display components
│   │   │   │   ├── SceneCard.tsx
│   │   │   │   ├── StoryboardView.tsx
│   │   │   │   └── ScriptExport.tsx
│   │   │   ├── timeline/             # Video timeline components
│   │   │   │   ├── TimelineStrip.tsx
│   │   │   │   ├── SceneBlock.tsx
│   │   │   │   ├── VideoPlayer.tsx
│   │   │   │   └── RerollPanel.tsx
│   │   │   ├── models/               # Model selection UI
│   │   │   │   ├── ModelCard.tsx
│   │   │   │   └── ModelSelector.tsx
│   │   │   ├── billing/              # Payment & credits UI
│   │   │   │   ├── CreditBalance.tsx
│   │   │   │   ├── PricingCards.tsx
│   │   │   │   └── TransactionHistory.tsx
│   │   │   └── admin/                # Admin-specific components
│   │   ├── lib/
│   │   │   ├── api.ts                # Backend API client (fetch wrapper)
│   │   │   ├── auth.ts               # NextAuth config
│   │   │   ├── utils.ts              # Shared utilities
│   │   │   └── constants.ts
│   │   ├── hooks/                    # Custom React hooks
│   │   │   ├── useProject.ts
│   │   │   ├── useCredits.ts
│   │   │   └── useWebSocket.ts
│   │   ├── types/                    # TypeScript types
│   │   │   ├── project.ts
│   │   │   ├── script.ts
│   │   │   ├── models.ts
│   │   │   └── billing.ts
│   │   ├── public/
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   └── package.json
│   │
│   └── api/                          # FastAPI backend
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py               # FastAPI app entry point
│       │   ├── config.py             # Settings (env vars, pydantic-settings)
│       │   ├── deps.py               # Dependency injection (db session, current_user)
│       │   │
│       │   ├── models/               # SQLAlchemy ORM models
│       │   │   ├── __init__.py
│       │   │   ├── user.py
│       │   │   ├── project.py
│       │   │   ├── scene.py
│       │   │   ├── asset.py
│       │   │   ├── wallet.py
│       │   │   ├── credit_transaction.py
│       │   │   ├── video_model.py
│       │   │   ├── ad_blueprint.py
│       │   │   ├── generation_job.py
│       │   │   └── feature_flag.py
│       │   │
│       │   ├── schemas/              # Pydantic request/response schemas
│       │   │   ├── __init__.py
│       │   │   ├── auth.py
│       │   │   ├── user.py
│       │   │   ├── project.py
│       │   │   ├── brief.py
│       │   │   ├── script.py
│       │   │   ├── scene.py
│       │   │   ├── asset.py
│       │   │   ├── billing.py
│       │   │   ├── video_model.py
│       │   │   └── admin.py
│       │   │
│       │   ├── api/                  # Route handlers
│       │   │   ├── __init__.py
│       │   │   ├── v1/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── router.py     # Aggregate all v1 routes
│       │   │   │   ├── auth.py
│       │   │   │   ├── users.py
│       │   │   │   ├── projects.py
│       │   │   │   ├── briefs.py
│       │   │   │   ├── scripts.py
│       │   │   │   ├── assets.py
│       │   │   │   ├── generation.py
│       │   │   │   ├── billing.py
│       │   │   │   ├── models.py     # Video model listing
│       │   │   │   ├── webhooks.py   # Stripe/PayPal/Cozzipay webhooks
│       │   │   │   └── admin.py
│       │   │   └── health.py
│       │   │
│       │   ├── services/             # Business logic layer
│       │   │   ├── __init__.py
│       │   │   ├── auth_service.py
│       │   │   ├── project_service.py
│       │   │   ├── script_service.py       # LLM orchestration, RAG
│       │   │   ├── asset_service.py        # Image generation
│       │   │   ├── video_service.py        # Model dispatch, job management
│       │   │   ├── stitch_service.py       # FFmpeg operations
│       │   │   ├── credit_service.py       # Wallet operations
│       │   │   ├── payment_service.py      # Multi-gateway abstraction
│       │   │   ├── swipe_file_service.py   # Blueprint analysis
│       │   │   ├── rag_service.py          # Retrieval logic
│       │   │   └── feature_flag_service.py
│       │   │
│       │   ├── adapters/             # External service adapters
│       │   │   ├── __init__.py
│       │   │   ├── llm/
│       │   │   │   ├── base.py       # Abstract LLM adapter
│       │   │   │   ├── gemini.py
│       │   │   │   └── claude.py
│       │   │   ├── video/
│       │   │   │   ├── base.py       # Abstract video model adapter
│       │   │   │   ├── fal_adapter.py
│       │   │   │   └── runway_adapter.py
│       │   │   ├── image/
│       │   │   │   ├── base.py       # Abstract image gen adapter
│       │   │   │   ├── flux_adapter.py
│       │   │   │   └── dalle_adapter.py
│       │   │   ├── payments/
│       │   │   │   ├── base.py       # Abstract payment adapter
│       │   │   │   ├── stripe_adapter.py
│       │   │   │   ├── paypal_adapter.py
│       │   │   │   └── cozzipay_adapter.py
│       │   │   └── storage/
│       │   │       ├── base.py
│       │   │       └── s3_adapter.py
│       │   │
│       │   ├── workers/              # Celery task definitions
│       │   │   ├── __init__.py
│       │   │   ├── celery_app.py     # Celery configuration
│       │   │   ├── script_tasks.py
│       │   │   ├── asset_tasks.py
│       │   │   ├── video_tasks.py
│       │   │   ├── stitch_tasks.py
│       │   │   └── payment_tasks.py
│       │   │
│       │   ├── db/
│       │   │   ├── __init__.py
│       │   │   ├── session.py        # SQLAlchemy async session
│       │   │   └── migrations/       # Alembic
│       │   │       ├── env.py
│       │   │       ├── alembic.ini
│       │   │       └── versions/
│       │   │
│       │   └── utils/
│       │       ├── __init__.py
│       │       ├── security.py       # Password hashing, JWT
│       │       ├── ffmpeg.py         # FFmpeg command builders
│       │       ├── prompt_compiler.py # Build video gen prompts
│       │       └── validators.py
│       │
│       ├── tests/
│       │   ├── conftest.py
│       │   ├── test_auth.py
│       │   ├── test_projects.py
│       │   ├── test_credits.py
│       │   ├── test_video_pipeline.py
│       │   └── test_payments.py
│       │
│       ├── pyproject.toml            # Poetry / pip dependencies
│       ├── Dockerfile
│       └── .env.example
│
├── packages/                         # Shared code across web + mobile
│   ├── shared-types/                 # TS types generated from backend OpenAPI spec
│   ├── api-client/                   # Typed API client + auth/token logic (reused by web & mobile)
│   └── validation/                   # Zod schemas shared between web & mobile forms
│
├── infrastructure/
│   ├── docker-compose.yml            # Local dev stack
│   ├── docker-compose.prod.yml       # Production overrides
│   ├── nginx/                        # Reverse proxy config
│   └── scripts/
│       ├── seed_models.py            # Seed video_models table
│       ├── seed_admin.py             # Create admin user
│       └── analyze_ad.py            # CLI tool to analyze a video ad
│
├── docs/
│   ├── ARCHITECTURE.md               # This document (moved here in prod)
│   ├── API_REFERENCE.md
│   ├── DEPLOYMENT.md
│   └── CONTRIBUTING.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint + test on PR
│       └── deploy.yml                # Deploy on merge to main
│
├── .gitignore
├── README.md
└── Makefile                          # Common commands (make dev, make test, etc.)
```

---

## Docker Compose (Local Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: primo
      POSTGRES_USER: primo
      POSTGRES_PASSWORD: primo_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: ./apps/api
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://primo:primo_dev@postgres:5432/primo
      - REDIS_URL=redis://redis:6379/0
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - FAL_KEY=${FAL_KEY}
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - COZZIPAY_SECRET_KEY=${COZZIPAY_SECRET_KEY}
    volumes:
      - ./apps/api:/app
    depends_on:
      - postgres
      - redis

  worker:
    build: ./apps/api
    command: celery -A app.workers.celery_app worker --loglevel=info --queues=script,asset,video,stitch,payment
    environment:
      - DATABASE_URL=postgresql+asyncpg://primo:primo_dev@postgres:5432/primo
      - REDIS_URL=redis://redis:6379/0
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - FAL_KEY=${FAL_KEY}
    volumes:
      - ./apps/api:/app
    depends_on:
      - postgres
      - redis

  web:
    build: ./apps/web
    command: npm run dev
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
    volumes:
      - ./apps/web:/app
      - /app/node_modules
    depends_on:
      - api

volumes:
  postgres_data:
```

---

## Key Dependencies

### Backend (Python)
```toml
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.115"
uvicorn = "^0.32"
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
asyncpg = "^0.30"
alembic = "^1.14"
pydantic = "^2.9"
pydantic-settings = "^2.6"
celery = {extras = ["redis"], version = "^5.4"}
redis = "^5.2"
httpx = "^0.28"                    # Async HTTP client for API calls
python-jose = {extras = ["cryptography"], version = "^3.3"}  # JWT
passlib = {extras = ["bcrypt"], version = "^1.7"}
boto3 = "^1.35"                    # S3
google-genai = "^1.0"             # Gemini API
fal-client = "^0.5"              # fal.ai (video + image models)
stripe = "^11.0"
pgvector = "^0.3"                  # Vector similarity for RAG
python-multipart = "^0.0.12"      # File uploads
pillow = "^11.0"                  # Image processing
```

### Frontend (Node.js)
```json
{
  "dependencies": {
    "next": "^14.2",
    "react": "^18.3",
    "typescript": "^5.5",
    "tailwindcss": "^3.4",
    "@radix-ui/react-*": "latest",
    "next-auth": "^4.24",
    "zustand": "^4.5",
    "react-query": "^5.0",
    "react-hook-form": "^7.53",
    "zod": "^3.23",
    "framer-motion": "^11.0",
    "lucide-react": "latest",
    "@stripe/stripe-js": "^4.0",
    "socket.io-client": "^4.7"
  }
}
```

---

## Database Initialization (Core Tables)

```sql
-- Users & Auth
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255),
  full_name VARCHAR(255),
  company_name VARCHAR(255),
  country VARCHAR(3),              -- ISO 3166-1 alpha-3
  industry VARCHAR(100),
  company_size VARCHAR(50),
  role VARCHAR(50),                -- creative_director, marketing_manager, founder, agency
  use_case VARCHAR(50),            -- video_gen, script_only, both
  ad_platforms TEXT[],             -- tiktok, instagram, youtube, etc.
  avatar_url TEXT,
  is_active BOOLEAN DEFAULT true,
  is_admin BOOLEAN DEFAULT false,
  onboarding_completed BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Projects
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(255),
  status VARCHAR(50) DEFAULT 'draft', -- draft, scripted, assets_ready, generating, completed, failed
  brief JSONB NOT NULL,               -- Full Module 2 payload
  script JSONB,                       -- Generated script (scenes array)
  selected_model_slug VARCHAR(50),
  total_credits_spent DECIMAL(10,2) DEFAULT 0,
  final_video_url TEXT,
  deleted_at TIMESTAMP,               -- soft delete (30-day recovery window)
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Individual scenes within a project
CREATE TABLE scenes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  scene_number INTEGER NOT NULL,
  duration_seconds INTEGER,
  script_data JSONB,                  -- Full scene JSON from script engine
  compiled_prompt TEXT,               -- Final prompt sent to video model
  reference_image_urls TEXT[],        -- Pre-generated or uploaded assets
  video_url TEXT,                     -- Generated video clip URL
  thumbnail_url TEXT,
  generation_status VARCHAR(50) DEFAULT 'pending', -- pending, generating, completed, failed
  generation_job_id VARCHAR(255),
  model_slug VARCHAR(50),
  generation_attempts INTEGER DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(project_id, scene_number)
);

-- Pre-generated assets for scenes
CREATE TABLE scene_assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scene_id UUID REFERENCES scenes(id) ON DELETE CASCADE,
  asset_type VARCHAR(50),             -- character, background, product, graphic, logo_placement
  description TEXT,
  prompt_used TEXT,
  image_url TEXT,
  status VARCHAR(50) DEFAULT 'pending', -- pending, generated, approved, rejected, user_uploaded
  created_at TIMESTAMP DEFAULT NOW()
);

-- Video model registry
CREATE TABLE video_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(50) UNIQUE NOT NULL,
  display_name VARCHAR(100),
  provider VARCHAR(50),
  api_endpoint TEXT,
  model_id VARCHAR(200),
  max_duration_seconds INTEGER,
  supported_resolutions TEXT[],
  supported_aspect_ratios TEXT[],
  supports_audio BOOLEAN DEFAULT false,
  supports_image_reference BOOLEAN DEFAULT false,
  supports_video_extension BOOLEAN DEFAULT false,
  cost_per_second_usd DECIMAL(6,4),
  credit_multiplier DECIMAL(4,2) DEFAULT 1.0,
  is_enabled BOOLEAN DEFAULT true,
  quality_tier VARCHAR(20),
  avg_generation_time_seconds INTEGER,
  config JSONB,                       -- Model-specific config options
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Ad intelligence blueprints (swipe file)
CREATE TABLE ad_blueprints (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255),
  source_video_url TEXT,
  industry VARCHAR(100),
  ad_category VARCHAR(100),
  psychological_triggers TEXT[],
  structural_arc JSONB,
  duration_seconds INTEGER,
  format VARCHAR(10),
  platform VARCHAR(50),
  hook_style VARCHAR(100),
  pacing VARCHAR(50),
  color_palette TEXT[],
  camera_techniques TEXT[],
  effectiveness_score FLOAT,
  full_analysis TEXT,                 -- Full text for embedding
  embedding VECTOR(1536),
  is_approved BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Wallets & Credits (from Architecture doc)
CREATE TABLE wallets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  balance_credits DECIMAL(10,2) NOT NULL DEFAULT 0,
  lifetime_purchased DECIMAL(10,2) DEFAULT 0,
  lifetime_spent DECIMAL(10,2) DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE credit_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  amount DECIMAL(10,2) NOT NULL,
  balance_after DECIMAL(10,2) NOT NULL,
  transaction_type VARCHAR(50),
  reference_type VARCHAR(50),
  reference_id VARCHAR(255),
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Subscriptions
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  tier VARCHAR(50),                   -- starter, growth, agency, enterprise
  status VARCHAR(50),                 -- active, cancelled, past_due, paused
  gateway VARCHAR(50),                -- stripe, paypal, cozzipay
  gateway_subscription_id VARCHAR(255),
  credits_per_month INTEGER,
  current_period_start TIMESTAMP,
  current_period_end TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Platform-wide settings (credit-to-USD ratio, etc.)
CREATE TABLE platform_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(100) UNIQUE NOT NULL,
  value JSONB NOT NULL,
  description TEXT,
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Admin-editable pricing per chargeable action
CREATE TABLE action_pricing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_key VARCHAR(100) UNIQUE NOT NULL,
  display_name VARCHAR(150),
  base_credits DECIMAL(10,2) NOT NULL,
  unit VARCHAR(50),
  is_enabled BOOLEAN DEFAULT true,
  notes TEXT,
  updated_by UUID REFERENCES users(id),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Subscription plans (admin-managed)
CREATE TABLE subscription_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(50) UNIQUE NOT NULL,
  display_name VARCHAR(100),
  price_usd DECIMAL(10,2),
  credits_per_month INTEGER,
  billing_interval VARCHAR(20),
  features JSONB,
  stripe_price_id VARCHAR(255),
  paypal_plan_id VARCHAR(255),
  is_enabled BOOLEAN DEFAULT true,
  sort_order INTEGER,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- One-time credit packages (admin-managed)
CREATE TABLE credit_packages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(50) UNIQUE NOT NULL,
  display_name VARCHAR(100),
  price_usd DECIMAL(10,2),
  credits INTEGER,
  bonus_credits INTEGER DEFAULT 0,
  is_enabled BOOLEAN DEFAULT true,
  sort_order INTEGER,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Credit purchases (created BEFORE checkout; fulfilment reads credits from here,
-- never from the webhook body)
CREATE TABLE credit_purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  reference VARCHAR(100) UNIQUE NOT NULL,   -- our id, echoed by the gateway
  gateway VARCHAR(50) NOT NULL,             -- stripe | paypal | cozzipay
  gateway_session_id VARCHAR(255),
  package_slug VARCHAR(50),
  plan_slug VARCHAR(50),
  amount_usd DECIMAL(10,2) NOT NULL,
  credits INTEGER NOT NULL,
  status VARCHAR(50) DEFAULT 'pending',     -- pending | completed | failed | expired
  fulfilled_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Webhook idempotency: a repeated delivery is ignored, never credited twice
CREATE TABLE processed_webhooks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  gateway VARCHAR(50) NOT NULL,
  event_id VARCHAR(255) NOT NULL,
  event_type VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(gateway, event_id)
);

-- Feature flags
CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  is_enabled BOOLEAN DEFAULT true,
  applies_to VARCHAR(100) DEFAULT 'all',
  config JSONB,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Generation jobs (tracks async work)
CREATE TABLE generation_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id),
  scene_id UUID REFERENCES scenes(id),
  job_type VARCHAR(50),               -- script, asset, video, stitch
  status VARCHAR(50) DEFAULT 'queued', -- queued, processing, completed, failed, refunded
  provider VARCHAR(50),
  provider_job_id VARCHAR(255),
  credits_charged DECIMAL(10,2),
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_projects_user ON projects(user_id, created_at DESC);
CREATE INDEX idx_scenes_project ON scenes(project_id, scene_number);
CREATE INDEX idx_credit_tx_user ON credit_transactions(user_id, created_at DESC);
CREATE INDEX idx_blueprints_category ON ad_blueprints(ad_category, industry, is_approved);
CREATE INDEX idx_gen_jobs_status ON generation_jobs(status, created_at);
CREATE INDEX idx_feature_flags_key ON feature_flags(key);
```

---

## Make Commands (Developer Experience)

```makefile
# Makefile
.PHONY: dev test lint migrate seed

dev:
	docker-compose up -d

dev-logs:
	docker-compose logs -f api worker

stop:
	docker-compose down

migrate:
	docker-compose exec api alembic upgrade head

migrate-create:
	docker-compose exec api alembic revision --autogenerate -m "$(msg)"

seed:
	docker-compose exec api python -m infrastructure.scripts.seed_models
	docker-compose exec api python -m infrastructure.scripts.seed_admin

test-api:
	docker-compose exec api pytest -v

lint-api:
	docker-compose exec api ruff check .

lint-web:
	cd apps/web && npm run lint

format:
	docker-compose exec api ruff format .
	cd apps/web && npm run format
```

---

## Environment Variables (.env.example)

```env
# Database
DATABASE_URL=postgresql+asyncpg://primo:primo_dev@localhost:5432/primo

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET=your-jwt-secret-change-in-prod
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000

# AI Models
GEMINI_API_KEY=
FAL_KEY=
OPENAI_API_KEY=              # Optional, for DALL-E fallback

# Payments
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=

COZZIPAY_PUBLIC_KEY=czp_test_pk_...
COZZIPAY_SECRET_KEY=czp_test_sk_...
COZZIPAY_WEBHOOK_SECRET=

# Storage
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=primo-assets
AWS_REGION=us-east-1

# App
FRONTEND_URL=http://localhost:3000
API_URL=http://localhost:8000
ENVIRONMENT=development
```

---

## Next Steps

With these two documents (ARCHITECTURE.md + PROJECT_STRUCTURE.md), you have:
1. Complete technical architecture with all decisions made
2. Full folder structure ready to scaffold
3. Database schema ready to migrate
4. Docker setup for local development
5. Dependency lists for both frontend and backend
6. Phased build plan with week estimates

**Ready to start coding Phase 0 (Foundations) when you give the go-ahead.**
