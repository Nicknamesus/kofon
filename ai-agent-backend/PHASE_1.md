# Phase 1 — Summary

The first layer of substance on top of the Phase 0 skeleton: a real
**content schema** in Postgres, a **seed loader** that fills it from
human-editable files, and the **three read-only tools** the agent will
use in Phase 2 to answer pre-sales and post-sales questions.

No agent yet. No LLM yet. The point of Phase 1 is that you can ask the
backend questions like "show me planetary gearboxes with backlash under
5 arcmin" and get real SKUs back — over HTTP — without an AI in the
loop. Once that's solid, Phase 2 can focus on agent logic without
simultaneously debugging "is the data even there?".

---

## In plain terms

Phase 0 was wiring. Phase 1 is **data + the first three things the bot
will be able to do with that data**:

1. **Look up products** by free-form text plus structured filters
   (`search_products`).
2. **Recommend product families** for a given industry + application
   (`recommend_categories`).
3. **Fetch validated fixes** for a known problem (`get_solution`).

These are the *primitives*. The Phase 2 agent will combine them into
flows (e.g. Guide-Find calls `search_products`; Pre-sales calls
`recommend_categories` then hands off to Guide-Find).

### What "it works" means

All commands run from inside `ai-agent-backend/`:

```powershell
cd X:\programming\websites\kofon\ai-agent-backend
docker compose up -d                # uses ./docker-compose.yml
.\.venv\Scripts\Activate.ps1        # so alembic / python find the env
alembic upgrade head
python -m app.seed.load
uvicorn app.main:app --port 8000
```

then:

```powershell
$body = '{"query":"planetary","filters":{"max_backlash_arcmin":5},"limit":3}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/tools/search_products `
  -Method Post -Body $body -ContentType 'application/json'
```

returns two real CaesarPlanetary SKUs (the HP variants — the HT ones
exceed the backlash threshold and are correctly filtered out).

---

## What's in the folder

```
ai-agent-backend/
├── alembic/versions/c96b3d3b7fda_phase_1_initial_schema.py  # creates all 9 tables
├── app/
│   ├── main.py                # now mounts the tools router
│   ├── models/                # NEW
│   │   ├── __init__.py        # re-exports + registers metadata
│   │   ├── content.py         # 7 content tables (seeded)
│   │   └── runtime.py         # 2 runtime tables (written by agent in P2)
│   ├── schemas/               # NEW
│   │   └── tools.py           # Pydantic v2 request/response models
│   ├── tools/                 # NEW
│   │   ├── search_products.py
│   │   ├── recommend_categories.py
│   │   └── get_solution.py
│   ├── routers/               # NEW
│   │   └── tools.py           # HTTP wrappers (curl-testable)
│   └── seed/                  # NEW
│       └── load.py            # idempotent loader (python -m app.seed.load)
└── seed/                      # NEW — human-edited content
    ├── main_conversation_types.yaml
    ├── use_cases.yaml
    ├── use_case_fits.csv
    ├── product_types/caesarplanetary.yaml
    ├── products/caesarplanetary.yaml
    └── problems/caesarplanetary.yaml
```

---

## The schema (9 tables)

Names mirror `DB_structure_17-05-26.pdf` so the diagram-to-code mapping
is one-to-one.

### Content (seeded, mostly static)

| Table                       | What it is                                            | Natural key                       |
| --------------------------- | ----------------------------------------------------- | --------------------------------- |
| `main_conversation_types`   | The 4 router branches (presales/guide/postsales/other) | `code`                            |
| `use_cases`                 | (industry, application) contexts                      | `(industry, application)`         |
| `product_types`             | Product families (CaesarPlanetary, Rollsate, ...)     | `code`                            |
| `use_case_product_types`    | M:N fit between use cases and families + `fit_score`  | `(use_case_id, product_type_id)`  |
| `products`                  | Concrete SKUs with JSONB `specs`                      | `sku`                             |
| `problem_types`             | Known issues per family                               | `(product_type_id, code)`         |
| `solutions`                 | Validated fixes with `confidence` + SOPs              | *(rewritten per problem on seed)* |

### Runtime (empty until Phase 2)

| Table           | What it is                                          |
| --------------- | --------------------------------------------------- |
| `conversations` | One row per browser session; `state` JSONB         |
| `messages`      | Turn-by-turn log, JSONB content (text/card/gate)   |

### Embeddings (deferred to Phase 3)

`product_embeddings` and `problem_embeddings` aren't created yet. The
pgvector extension is already in the running image (Phase 0 chose
`pgvector/pgvector:pg16`), so adding them later is just a migration —
no image swap, no reseed of existing rows.

### Constraints worth noting

- `CHECK fit_score BETWEEN 1 AND 5`, `CHECK severity BETWEEN 1 AND 5`,
  `CHECK confidence BETWEEN 1 AND 5` — domain experts can't accidentally
  enter 7s.
- `ON DELETE CASCADE` for `solutions → problem_types` and
  `messages → conversations` — if a problem or conversation is dropped,
  its children go with it.
- Partial index `ix_conversations_user_email_present` — only indexes
  rows where the user actually gave us their email. Smaller, faster.

---

## The seed pipeline

**Files-on-disk, not SQL.** Content lives under `seed/` as YAML and CSV
so domain experts can edit it without writing queries, and changes show
up as readable git diffs.

```
YAML/CSV files  →  python -m app.seed.load  →  Postgres
```

The loader is **idempotent**: re-running it on an already-populated DB
produces zero net changes. Each entity uses `INSERT ... ON CONFLICT DO
UPDATE` keyed on its natural key (see table above).

**Solutions are an exception** — they have no natural key in the schema
(the diagram doesn't give them one). The loader deletes a problem's
solutions and re-inserts them on every run. Cheap, since the row count
per problem is tiny.

### Demo content shipped in Phase 1

Just enough to prove the pipeline end-to-end:

- **4** main conversation types (the four diagram branches).
- **6** use cases — Robotics × 2, Packaging, Machine tool, Solar,
  Aerospace ground support.
- **1** product type (`caesarplanetary`) with a realistic `spec_schema`.
- **4** SKUs — PG060-3-HP, PG090-10-HP, PG090-25-HT, PG140-50-HT.
- **6** curated fits (use-case × product-type rows with 1–5 scores
  and a rationale string the bot can quote).
- **3** problem types and **3** solutions — including one with an
  `escalate_if` JSONB payload, which Phase 3's "easily fixable?" gate
  will consume.

The other five product families (Rollsate, Elitewave, Servolux, KGV,
SpiralBevel) get added in Phase 2+ by the content team. The agent
doesn't need them to be complete to start working — it just needs
*some* family fully seeded so the tools have something to return.

---

## The three tools

All three are **plain async Python functions** in `app/tools/`. The
LangChain `@tool` decoration that Phase 2 needs is a thin adapter over
these — the business logic stays here, framework-agnostic.

Each tool is also exposed as an HTTP endpoint under `/api/tools/` so
we can curl-test it. From Phase 2 onwards the agent calls the Python
function directly (no HTTP hop in-process); the endpoints stick around
as the contract surface for external consumers and debugging.

### `search_products`

```
POST /api/tools/search_products
{
  "query": "...",                  // free-form text (optional)
  "filters": {                     // structured, optional
    "family": "caesarplanetary",
    "frame_size_mm": 90,
    "min_nominal_torque_nm": 80,
    "max_backlash_arcmin": 5,
    "variant": "HP"
  },
  "limit": 3
}
```

**Phase 1 implementation**: ILIKE on product name + family
name/description, plus JSONB `specs->>'key'` comparisons. Inactive
products are excluded.

**Phase 3 implementation**: the text branch is replaced by a pgvector
ANN query over `product_embeddings`. The signature and Pydantic return
type don't change — Phase 2 agent code carries through unchanged.

### `recommend_categories`

```
POST /api/tools/recommend_categories
{ "industry": "Robotics", "application": "Cobot joint actuation" }
```

Joins `use_cases → use_case_product_types → product_types`, ordered by
the curated `fit_score`. If the exact `(industry, application)` pair
isn't seeded, falls back to a fuzzy ILIKE match and flags
`use_case_matched: false` so the agent knows to confirm with the user
rather than charging ahead.

### `get_solution`

```
GET /api/tools/solutions/{problem_type_id}
```

Returns the problem row plus every linked solution, ordered by
`confidence` descending. The Phase 3 "easily fixable?" gate will read
the top solution's `confidence` (combined with prior-resolution counts
for the same SKU) to decide which terminal node fires. Phase 1 just
exposes the data — the gate logic lives in Phase 3.

---

## Smoke test (run end-to-end on 2026-05-18)

```
docker compose up -d              → kofon-chatbot-postgres healthy
alembic upgrade head              → c96b3d3b7fda applied, 9 tables present
python -m app.seed.load           → main_conversation_types=4,
                                    use_cases=6, product_types=1,
                                    products=4, use_case_product_types=6,
                                    problem_types=3, solutions=3
python -m app.seed.load           → same counts (idempotent ✓)
uvicorn app.main:app --port 8000  → starts cleanly

POST /api/tools/search_products
  query="planetary", max_backlash_arcmin=5
  → PG060-3-HP, PG090-10-HP   (HT variants correctly excluded)

POST /api/tools/recommend_categories
  industry=Robotics, application=Cobot joint actuation
  → CaesarPlanetary @ fit_score=5 with rationale

GET /api/tools/solutions/1
  → backlash_exceeds_spec + SOP-CP-001 solution @ confidence=4
```

---

## What is explicitly NOT in Phase 1

- No LangGraph, no LangChain, no LLM. Routing and slot-filling are
  Phase 2.
- No embeddings tables, no vector search. Phase 3.
- No agent-driven writes to `conversations` / `messages`. The tables
  exist; nothing populates them yet.
- No write tools (`create_rfq`, `escalate_to_human`, `send_datasheet`).
  Phase 4.
- No auth. Endpoints are open in dev.
- No frontend wiring. The widget is still pure visuals (Phase 2 swaps
  the mocks for SSE event streams).
- Content is one family only. The other five get seeded by the content
  team as they become relevant.

---

## How Phase 1 sets up Phase 2

| Phase 2 work                    | What Phase 1 already gives it                                                          |
| ------------------------------- | -------------------------------------------------------------------------------------- |
| LangGraph `guide.find` node     | `search_products` already returns the exact `ProductOut` shape the card will render.   |
| LangGraph `presales.figure_out` | `recommend_categories` is the slot-filling endpoint — call it once industry+app are collected. |
| `outcome_sell` / `outcome_human` | `conversations.outcome` column exists; just write `'sell'` / `'human_handoff'`.       |
| Per-conversation state          | `conversations.state` JSONB + `current_node` are sitting empty, waiting for the checkpointer hook. |
| SSE event streaming             | FastAPI + lifespan are async-ready; adding `POST /api/flows/{flow}/start` with SSE is additive. |

The data layer is the load-bearing piece of the agent. Building it
without the agent in the loop means Phase 2 can focus entirely on
state-machine wiring, not "does the right SKU come out of the DB?".
