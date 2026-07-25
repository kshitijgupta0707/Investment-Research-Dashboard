# Investment Research Dashboard

Multi-tenant SaaS where analysts ask natural-language equity research questions and an
AI agent decides which data tools to call, then returns a structured, source-attributed
report rendered as real UI components.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui |
| Backend | FastAPI (Python 3.13), async |
| Database + Auth | Supabase (Postgres, JWT, Row-Level Security) |
| LLM | Claude (`claude-sonnet-5`) via the Anthropic API |
| Market data | yfinance (primary), Alpha Vantage (fallback) |
| News | NewsAPI, with sentiment classified by Claude |
| Knowledge base | BM25 keyword index over seeded filing excerpts |

## Layout

```
backend/
  app/
    routes/       FastAPI routers (thin)
    services/     business logic
    agent/        tool schemas, planner, synthesizer, executor
    integrations/ market data, news, knowledge-base search
    models/       DB accessors
    schemas/      Pydantic request/response models
    middleware/   auth + tenant context, logging, error handler
    utils/        config, helpers
  scripts/        seeding and ingestion
  tests/
frontend/
  src/app/        Next.js App Router pages
```

## Local setup

Requires Python 3.13+ and Node 20+.

**1. Environment**

```bash
cp .env.example .env                                # backend config
cp frontend/.env.local.example frontend/.env.local  # frontend config
```

Fill both in. `.env` files are gitignored, and no secret is exposed to the browser —
all Claude calls go through the backend.

**2. Backend**

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt                   # Windows
# source .venv/bin/activate && pip install -r backend/requirements.txt  # macOS/Linux

cd backend && uvicorn app.main:app --reload
```

API on http://localhost:8000, interactive docs at http://localhost:8000/docs.

**3. Frontend**

```bash
cd frontend && npm install && npm run dev
```

App on http://localhost:3000.
