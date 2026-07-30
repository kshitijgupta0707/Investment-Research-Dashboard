# Engineering Decisions

**FinLens.ai : Investment Research Dashboard**

Companion to [ARCHITECTURE.md](ARCHITECTURE.md), which describes *what* was built.
This document explains *why*.

---

## 1. Project Summary

**Objective**: A multi-tenant SaaS workspace where equity analysts ask
natural-language research questions and an LLM agent decides, per query, which
data sources to consult before returning a structured, source-attributed report.

**Primary functionality**: A two-turn agent plans which of three tools a question
needs, executes them concurrently, and synthesises the results into a fixed JSON
schema that the frontend renders as typed components - cards, tables, charts,
sentiment badges, each carrying its own confidence rating and sources. Reports
can be saved, tagged, searched, annotated and deleted within an organisation.

**Users**: Analyst teams sharing a workspace, with two roles: Analyst and Admin.

**Architecture**: A layered FastAPI monolith with an agentic AI subsystem, a
Next.js 14 frontend using Server Components, and PostgreSQL via Supabase.

**Major challenges**: Three dominated the work: making tool selection genuinely
model-driven rather than keyword-routed; getting reliable structured output from
an LLM without a brittle schema; and enforcing tenant isolation in a way that
cannot be forgotten.

---

## 2. Which Option and Why

This implements **Option A: Investment Research Dashboard**.

It was chosen because its core requirement, an agent that selects tools per
query  is the hardest thing in the brief to fake. A keyword router would satisfy
a demo but fail the acceptance tests, which deliberately include a question
requiring *zero* tools ("What is a P/E ratio?") and one requiring all three.
Choosing this option meant the graded behaviour had to be real.

The domain also produces naturally structured output. Equity research decomposes
into comparison tables, company cards, price charts and sentiment, which makes
the fixed Turn-2 schema a genuine contract rather than a wrapper around prose.

**Evidence it works.** The `research_queries` table records tool selection per
query. Real rows from the seeded workspace:

| Query | Tools selected |
|---|---|
| What is a P/E ratio? | *(none)* |
| What's NVIDIA's current P/E and market cap? | `get_market_data` |
| What's the latest news on Tesla? | `get_news_sentiment` |
| Analyze NVIDIA's Q3 earnings, compare with AMD and Intel… | `market_data`, `news`, `kb`, `kb` |

The last row shows the model issuing two knowledge-base searches with different
arguments in one plan, behaviour no code path requests.

**Complexity and scale**: The implementation cost sits in orchestration rather
than domain logic: concurrent execution, per-tool failure isolation, and schema
validation. That cost is fixed: adding a fourth tool is a schema, a handler and
a registry entry, not a rewrite.

---

## 3. Technology Stack

### Frontend: Next.js 14 (App Router)

Chosen over plain React (Vite) or Vue for one decisive reason: **Server
Components let the auth check and data fetch happen before any HTML is sent.** A
client-rendered app would ship the protected page, mount React, fire a
`useEffect`, and only then discover the user is unauthenticated : a visible flash
before redirect.

It also keeps the access token off the browser entirely. `src/lib/api/resources.ts`
carries `import "server-only"`, so importing it from a client component is a
**build error**, not a runtime surprise. No `"use client"` file in the codebase
calls the API.

*Trade-off:* the server/client boundary is a genuine source of confusion, and
Server Components cannot write cookies , which is why session refresh must live
in middleware.

### Backend: FastAPI

Chosen over Django or Node/Express. Three reasons:

- **Async-native.** Parallel tool execution via `asyncio.gather` is the core
  feature; Django would have needed threads or Celery.
- **Pydantic validation is the same tool used to validate LLM output.** One
  mental model for request bodies, response contracts and model responses.
- **OpenAPI is generated automatically**, which doubles as the API-design artifact.

Node was rejected because the AI ecosystem, data handling (`yfinance`) and
`rank_bm25` are Python-native.

### Database: PostgreSQL (Supabase)

Postgres was required by the workload, not merely preferred: `jsonb` for stored
reports, `text[]` with GIN indexing for tags, and full-text search over query
text. MongoDB would have handled the JSON but not the relational integrity that
tenant isolation depends on - `org_id uuid not null references organizations(id)`
is what makes an orphan row impossible.

Supabase was chosen over self-hosted Postgres because it supplies JWT auth and
Row-Level Security out of the box, saving roughly a day of work on a compressed
timeline.

### Data access: `asyncpg`, no ORM

**Deliberately no SQLAlchemy, Prisma or Tortoise.** Three reasons:

1. **Tenant safety is more auditable in explicit SQL.** Every accessor takes
   `org_id` as a required argument and every query contains `where org_id = $n`.
   With an ORM the filter hides behind a query-builder call and is easier to omit.
2. Several queries use Postgres-specific features an ORM abstracts poorly —
   `tags @> array[...]::text[]`, `to_tsvector(...) @@ plainto_tsquery(...)`, and
   CTE-returning updates.
3. `asyncpg` is materially faster than SQLAlchemy's async layer, and the schema is
   small enough (9 tables) that an ORM's productivity gain is marginal.

*Trade-off:* no migrations framework and no compile-time query checking. Mitigated
by numbered SQL migrations and integration tests that run against a real database.

### AI:  Google Gemini via `google-genai`, custom orchestration

**No LangChain, no agent framework.** The orchestration is roughly 200 lines
across `planner.py`, `executor.py` and `synthesizer.py`. A framework would have
added a dependency, an abstraction layer and its own failure modes to hide a
control flow that is genuinely simple: one call to plan, `asyncio.gather` to
execute, one call to synthesise.

More importantly, the graded behaviours - per-tool timeouts, partial-result
collection, forced structured output are exactly the things frameworks make
harder to control precisely.

Gemini was chosen for function calling plus forced-call structured output on a
free tier that covers a live demo.

### Deployment: Docker, Railway (backend), Vercel (frontend)

Both services have multi-stage Dockerfiles and a `docker-compose.yml` for
one-command local setup, which the brief lists as preferred. Railway and Vercel
were chosen because they deploy directly from a Dockerfile and a Next.js repo
respectively with no infrastructure code  -  appropriate for a demo, and honestly
not a production posture.

**Not implemented:** CI/CD. There is no `.github/workflows`; tests run locally.

---

## 4. Multi-Tenancy Design

**Pattern: shared database, shared schema, with an `org_id` discriminator column.**

Eight of nine tables carry `org_id`; `kb_documents` is a shared reference corpus
and deliberately does not.

### Why this pattern

| Alternative | Why rejected |
|---|---|
| Database per tenant | Strongest isolation, but migrations, pooling and provisioning cost multiply per tenant. Unjustifiable for a demo with two organisations. |
| Schema per tenant | Still requires per-schema migrations and dynamic search-path switching, for isolation the application layer already provides. |
| **Shared schema** | One migration path, one connection pool, isolation enforced in the query. |

### Request lifecycle

```
JWT → verify signature against Supabase JWKS (locally, cached key)
    → extract sub claim
    → SELECT users WHERE supabase_auth_id = sub
    → CurrentUser(id, org_id, role)
    → every query: WHERE org_id = $n
```

The critical decision is that **`org_id` is never accepted from the client.** No
request schema declares it. There is no parameter through which another tenant
could be requested.

### Two layers, one of them dormant - stated honestly

Row-Level Security exists: 12 policies across 8 tables, backed by three
`security definer` helpers. **It does not fire on the normal request path**,
because the API connects with a privileged role that RLS does not constrain.

The application-level filter is therefore the real defence. RLS is a second
expression of the same rules in the schema, valuable because the rule is written
where the data lives rather than only in application code. Claiming RLS enforces
isolation here would be inaccurate.

### 404, not 403

A report belonging to another organisation returns **404**. This is not politeness
— the filter sits in the `WHERE` clause, so the row genuinely does not come back
and the code cannot distinguish "absent" from "another tenant's". A 403 would
confirm the identifier exists, which is an information leak across the boundary.

Ownership is a separate check: `require_owner_or_admin` runs *after* the row loads
with its `org_id` filter, so cross-tenant access is already a 404 before ownership
is considered.

---

## 5. AI Integration Design

### Orchestration

Three LLM calls per query, plus one conditional retry:

1. **Turn 1 - Planning:** The model receives the question and three tool schemas
   and returns function calls. `automatic_function_calling` is disabled because
   the backend executes tools itself with its own timeouts.
2. **Sentiment** (only if news was selected) , one call per ticker, batched at 25
   articles per request via constrained decoding.
3. **Turn 2 - Synthesis:** The model must call `emit_report` exactly once
   (`FunctionCallingConfigMode.ANY` with a single allowed name), so prose is not a
   possible response.

### Prompt decisions

Both system prompts encode policy the schema cannot express. The planner prompt
instructs the model to call only necessary tools, pass every company in a *single*
call rather than one per company, and answer directly when no company data is
needed. The synthesis prompt supplies a **confidence rubric** - `high` for
directly supported claims, `medium` for inference, `low` when data is thin or a
tool failed ,without which the rating would mean whatever the model felt.

### Structured output 

The `emit_report` schema is **deliberately flat, not a `oneOf` union**, even
though five section types have five different content shapes. Models follow
branching schemas unreliably and every rejection costs a full regeneration.
Strictness lives in Pydantic instead, which coerces `content` to the model
matching the declared `type` or rejects the section.

An empirical constraint shaped this: an `object` with a description but no
`properties` returns from Gemini as `{}` every time. It will not invent a shape
the schema does not name, so all ten possible content fields are declared
explicitly.

### Hallucination mitigation

- The prompt forbids figures from memory: *"never estimate a number that is
  missing  - omit it instead."*
- Every section must carry `sources[]` with a type, label and optional
  `data_as_of`.
- **`partial`, `failed_tools` and `generated_at` are set by the backend, never the
  model.** The executor knows which tools failed; asking the model to self-report
  invites a confident claim about data it never received.

### Error handling

Every tool runs behind `asyncio.wait_for` with a 25-second ceiling and a broad
`except`, returning failures as data rather than raising. One provider outage
degrades the report to `partial: true`; it does not fail the request. Malformed
synthesis output is retried once with the validation error fed back, then
surfaces as a clean 502.

**Retrieval** is BM25 over seeded filing excerpts - lexical, with no embedding
step. The brief permits keyword search, and this avoids an embedding model and
vector store for a 32-chunk corpus.

---

## 6. Engineering Trade-offs

**The timeline was three days, not five.** Scope was compressed deliberately, and
the following were simplified as a result.

| Simplified | Why acceptable | Impact |
|---|---|---|
| **No response caching** | Reports are point-in-time snapshots; caching a query result risks serving stale market data as fresh | Repeated identical queries re-run the full pipeline, including billable LLM calls |
| **No application rate limiting** | Upstream 429s are handled and degraded; the demo has no untrusted traffic | A malicious authenticated user could exhaust the Gemini free tier |
| **No CI/CD** | 453 tests run locally on every change | Nothing prevents a broken commit from being pushed |
| **No monitoring or analytics** | Structured JSON logs carry request id, user, org, latency and tool selection — enough to diagnose from a log search | No dashboards, alerting or aggregation |
| **No streaming responses** | The report is a single structured object; partial JSON has no useful rendering | A three-tool query takes ~40s with no intermediate feedback beyond a skeleton |
| **No background jobs** | Every operation completes within a request | Long queries hold a connection; no scheduled refresh is possible |
| **Single invite code per org** | Sufficient to demonstrate the join flow | No per-email invitations or expiry management beyond a 7-day TTL |
| **BM25 rather than embeddings** | Explicitly permitted; results are explainable | Purely lexical — a query about "chip supply" will not match "wafer capacity" |

One smaller item is honest technical debt: `src/lib/report/` and
`src/lib/reports/` coexist with names one character apart.

---

## 7. Improvements With Two Additional Weeks

**Within the two weeks.**

- **Add more tools.** The agent's value scales with what it can reach: filings via
  an EDGAR client, earnings-call transcripts, analyst estimates. Each addition is a
  schema in `tools.py`, a handler in `executor.py` and a registry entry, so the cost
  is bounded and the planner needs no change to start using it.
- **Application rate limiting** per organisation, protecting the LLM budget.
- **Short-TTL response caching** as a cost measure, with `data_as_of` preserved so
  a cached response never claims to be fresher than it is.
- **An AI evaluation harness** — the acceptance queries as a regression suite
  asserting expected tool selection, so a prompt change that breaks routing fails
  visibly rather than silently.

**Beyond two weeks: product direction.**

These are larger than the window above and are recorded as direction rather than
plan.

- **Document ingestion against the customer's own knowledge base.** Analysts want to
  ask questions over their firm's internal research, not just the seeded filings, and
  the format is usually PDF. The deliberate position is that those documents stay on
  the customer's systems: hosting them would mean carrying their storage cost, their
  retention policy and their compliance surface, and the copy would drift from the
  source. The work is therefore a connector, authenticating against a customer-hosted
  store and querying it behind the existing `search_knowledge_base` contract, rather
  than an upload endpoint that writes PDFs into our database. `_run_knowledge_base` is
  nine lines behind that contract, so the swap touches one module.
- **Multi-turn conversation.** Each query is currently independent. Follow-ups
  ("what about their margins?") would need conversation state, a decision about how
  much history to carry into Turn 1, and a token budget, since prompt size grows with
  every turn. The planner would also need to resolve pronouns against earlier turns,
  which is a meaningful change to how tool selection is prompted.
- **Comments on reports.** The analyst note is deliberately single-author, matching
  the creator-or-admin permission on the report itself. A threaded comment model is a
  different feature: many authors, per-comment ownership, and a read/write rule that
  lets any organisation member contribute without letting them edit a colleague's
  words. That is a new table with its own `org_id` and ownership checks, not an
  extension of the notes column.

---

## 8. Hardest Engineering Challenge

**Getting reliable structured output from the LLM.**

The frontend contract requires that a report never be parsed from prose — the
renderer switches on a section `type` and renders a matching component. That
demands the model produce valid, typed JSON on essentially every call.

**The constraint.** Five section types have five different `content` shapes. A
`text` section carries `{text}`; a `table` carries `{columns, rows}`; a `chart`
carries nested series and points. Expressed correctly, that is a `oneOf` union.

**First iteration: the obvious approach failed.** A branching schema produced
unreliable results: the model would mix fields across types or return content that
did not match its own declared `type`. Each rejection cost a full regeneration,
which at Turn-2 prompt sizes is expensive and slow.

**Second iteration: an unexpected finding.** Simplifying `content` to an untyped
object with a prose description of the five shapes returned `{}` **every time**.
Gemini will not invent a shape the schema does not name. Describing the structure
in the description field is not equivalent to declaring it.

**Final design: invert where strictness lives.** The schema declares the *union
of every field any type could use*, flat, with nothing required, each description
naming the type it belongs to. The prompt says: *"Set only the fields belonging to
this section's type; leave the rest out."* Pydantic then enforces the real contract
with a `model_validator` that coerces `content` to the model matching `type`, or
rejects the section. One retry feeds the validation error back.

**Result.** The frontend boundary gets the same guarantee it would have had from a
strict schema, at a much lower failure rate — and the renderer's `switch` closes
with an `assertNever`, making an unhandled section type a compile error rather
than a blank space in a report.

**Lesson.** Ask the model for something easy to produce and validate it hard.
Schema strictness at the model boundary and schema strictness at the application
boundary are different problems, and conflating them costs generations.

---

## 9. Key Engineering Lessons

**Make the safe path structural, not a rule to remember.** The decisions that held
up best were the ones enforced mechanically: `org_id` as a *required argument* on
every accessor, `import "server-only"` making a client-side API import a build
error, `assertNever` making a missing section type a compile error, and 404
falling out of the query rather than a policy someone applies.

**Never let the model report on its own reliability.** `partial` and
`failed_tools` come from the executor because it observed the failures. This
generalises: the component that observed an event is the one that should report it.

**State-management bugs hide behind plausible explanations.** A blank research
result was initially attributed to a hot-reload artefact. The real cause was
`revalidatePath` re-rendering the route tree and resetting `useFormState`. The
lesson was to stop reasoning from symptoms once a plausible story exists and
verify the mechanism.

**Measure before optimising, and measure the right layer.** Navigation felt slow
and the instinct was to optimise queries. The dominant cost was the database
region — roughly 300 ms per round trip from Tokyo versus 30 ms from Mumbai. An
endpoint doing no database work stayed at 2 ms throughout, which identified the
layer immediately.

**Free-tier constraints are design inputs.** Alpha Vantage's 25 requests/day made
it unusable as a primary provider. Testing the configured fallback revealed that
its two required calls, sent back to back, are refused as too frequent — silently
returning a price with no P/E or market cap. Providers fail in ways their
documentation does not describe, which is an argument for wrapping each one behind
an interface and testing it live.
