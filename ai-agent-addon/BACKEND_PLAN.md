# Backend plan — DB + LangChain agent

Plan only. No code commitments here — this is what we'll build, in what order,
and the load-bearing decisions to make before we start. Two source diagrams:

- `Ai chatbot logic_17-05-26.pdf` — routing & decision tree
- `DB_structure_17-05-26.pdf` — collection-level data model

## 1. How the diagrams map to the system

The logic diagram is a **state machine**, not a chat policy — the four primary
branches (Pre-Sales / Guide / Post-Sales / Other) plus the two binary gates
("happy?" / "easily fixable?") are explicit transitions. We will implement it
as one **LangGraph** graph rather than letting an LLM "decide" the path freely.
Each node in the graph is a small focused LLM call (or a deterministic tool
call) — never a generic "do the right thing" prompt.

The DB diagram is a **content model** — seven entities (the central
`Database` node plus six collections). All except `conversations` /
`messages` are **content** that domain experts seed and curate; the chatbot
reads from them. `conversations` / `messages` are **runtime** data the agent
writes as users interact.

## 2. Database

### 2.1 Technology

**Postgres 15+ with `pgvector`.** Single store for relational data and
embeddings. No second vector DB to operate. LangChain has first-class
support (`PGVector`).

Dev: local Postgres in Docker. Prod: a managed Postgres (Supabase, Neon, or
RDS).

> Considered but rejected:
> - **SQLite + Chroma** — fine for prototyping, two stores to keep in sync in prod.
> - **MongoDB** — the model is relational (use cases → product types → products), not document-shaped.
> - **Pinecone / Weaviate** — buys nothing over pgvector at this scale; adds a vendor.

### 2.2 Schema (content tables)

The names below follow the DB diagram literally so the mapping is obvious.

```sql
-- The four primary entries in the logic diagram. Seeded once, rarely changes.
CREATE TABLE main_conversation_types (
  id            SMALLSERIAL PRIMARY KEY,
  code          TEXT NOT NULL UNIQUE,         -- 'presales' | 'guide' | 'postsales' | 'other'
  label         TEXT NOT NULL,                -- "Pre-Sales", "Guide", ...
  description   TEXT NOT NULL,                -- one-paragraph definition the router LLM sees
  greeting_key  TEXT NOT NULL                 -- i18n key for the opening bot message
);

-- Application contexts. Seeded by content team.
-- e.g. (industry='Robotics', application='Cobot joint actuation')
CREATE TABLE use_cases (
  id            BIGSERIAL PRIMARY KEY,
  industry      TEXT NOT NULL,
  application   TEXT NOT NULL,
  description   TEXT NOT NULL,
  notes         TEXT
);

-- Product families: CaesarPlanetary, Rollsate, Elitewave, Servolux, KGV, SpiralBevel
CREATE TABLE product_types (
  id            BIGSERIAL PRIMARY KEY,
  code          TEXT NOT NULL UNIQUE,         -- 'caesarplanetary'
  name          TEXT NOT NULL,                -- "CaesarPlanetary"
  family        TEXT NOT NULL,                -- "Planetary gearbox" / "Roller screw" / ...
  description   TEXT NOT NULL,
  spec_schema   JSONB NOT NULL                -- which spec keys this family exposes
);

-- Many-to-many: which product types fit which use cases (with a quality score)
CREATE TABLE use_case_product_types (
  use_case_id        BIGINT REFERENCES use_cases(id)     ON DELETE CASCADE,
  product_type_id    BIGINT REFERENCES product_types(id) ON DELETE CASCADE,
  fit_score          SMALLINT NOT NULL,                  -- 1..5; pre-curated
  rationale          TEXT NOT NULL,                      -- "why this fits" — shown to the user
  PRIMARY KEY (use_case_id, product_type_id)
);

-- Concrete SKUs
CREATE TABLE products (
  id                 BIGSERIAL PRIMARY KEY,
  sku                TEXT NOT NULL UNIQUE,    -- 'PG090-10-HP'
  name               TEXT NOT NULL,
  product_type_id    BIGINT REFERENCES product_types(id),
  specs              JSONB NOT NULL,          -- torque, ratio, backlash, mounting, ...
  datasheet_url      TEXT,
  cad_url            TEXT,
  lead_time_days     INTEGER,
  status             TEXT NOT NULL DEFAULT 'active'  -- active | discontinued
);

-- Known issues (post-sales). Per-family.
CREATE TABLE problem_types (
  id                 BIGSERIAL PRIMARY KEY,
  product_type_id    BIGINT REFERENCES product_types(id),
  code               TEXT NOT NULL,           -- 'backlash_exceeds_spec'
  label              TEXT NOT NULL,
  description        TEXT NOT NULL,
  severity           SMALLINT NOT NULL,       -- 1..5
  UNIQUE (product_type_id, code)
);

-- One or more validated fixes per problem type
CREATE TABLE solutions (
  id                 BIGSERIAL PRIMARY KEY,
  problem_type_id    BIGINT REFERENCES problem_types(id) ON DELETE CASCADE,
  summary            TEXT NOT NULL,           -- one-liner the agent surfaces first
  body_markdown      TEXT NOT NULL,           -- full SOP, shown in the card
  confidence         SMALLINT NOT NULL,       -- 1..5; sets the "easily fixable" default
  escalate_if        JSONB,                   -- triggers that force human handoff
  sop_url            TEXT,
  rma_template_url   TEXT
);
```

### 2.3 Schema (runtime tables)

```sql
-- One row per browser session (anon by default; email captured during a flow)
CREATE TABLE conversations (
  id                 BIGSERIAL PRIMARY KEY,
  session_uuid       UUID NOT NULL UNIQUE,    -- generated client-side, stored in localStorage
  user_email         TEXT,
  user_company       TEXT,
  language           CHAR(2) NOT NULL DEFAULT 'EN',
  main_type_code     TEXT REFERENCES main_conversation_types(code),
  current_node       TEXT,                    -- e.g. 'guide.find.results'
  state              JSONB NOT NULL DEFAULT '{}',  -- collected slots: industry, torque, ...
  outcome            TEXT,                    -- 'sell' | 'human_handoff' | 'resolved' | 'abandoned'
  ticket_id          TEXT,                    -- CRM ticket if escalated
  started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_message_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at           TIMESTAMPTZ
);

CREATE INDEX ON conversations (session_uuid);
CREATE INDEX ON conversations (user_email) WHERE user_email IS NOT NULL;
CREATE INDEX ON conversations (started_at);

CREATE TABLE messages (
  id                 BIGSERIAL PRIMARY KEY,
  conversation_id    BIGINT REFERENCES conversations(id) ON DELETE CASCADE,
  role               TEXT NOT NULL,           -- 'user' | 'bot' | 'system'
  content_type       TEXT NOT NULL,           -- 'text' | 'card' | 'form_submit' | 'gate_choice'
  content            JSONB NOT NULL,          -- raw text or structured card payload
  node               TEXT,                    -- which graph node produced/consumed this
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ON messages (conversation_id, created_at);
```

### 2.4 Vector embeddings (for semantic search)

```sql
CREATE EXTENSION vector;

-- Product family + SKU search. One row per product (and one per product_type
-- for category-level matches in the Pre-Sales flow).
CREATE TABLE product_embeddings (
  id                 BIGSERIAL PRIMARY KEY,
  source_type        TEXT NOT NULL,           -- 'product' | 'product_type'
  source_id          BIGINT NOT NULL,
  text               TEXT NOT NULL,           -- the chunk we embedded
  embedding          VECTOR(1536) NOT NULL,   -- text-embedding-3-small dimension
  UNIQUE (source_type, source_id, text)
);

CREATE INDEX ON product_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Same for problems
CREATE TABLE problem_embeddings (
  id                 BIGSERIAL PRIMARY KEY,
  problem_type_id    BIGINT REFERENCES problem_types(id) ON DELETE CASCADE,
  text               TEXT NOT NULL,
  embedding          VECTOR(1536) NOT NULL
);

CREATE INDEX ON problem_embeddings USING ivfflat (embedding vector_cosine_ops);
```

### 2.5 Seeding strategy

- Domain experts maintain content in a flat YAML/CSV directory under
  `backend/seed/` — one file per `product_type`, with nested specs, problems,
  solutions. CI converts to SQL + (re-)generates embeddings.
- Embeddings are regenerated only for rows whose text changed (hash check).
- Migration tool: `alembic`. Idempotent. Never destroy `conversations` / `messages`.

### 2.6 Privacy

- `user_email` only ever captured after explicit consent (datasheet capture / RFQ).
- Don't store raw IPs without consent. If session geo is needed, derive
  `country_code` at write time and discard the IP.
- `messages.content` may include user-entered freeform text — flag and redact
  obvious PII via a Presidio pass before persisting.

## 3. Agent (LangChain + LangGraph)

### 3.1 Why LangGraph, not a plain LangChain agent

The logic diagram is a finite state machine with explicit transitions and gates.
A free-form LLM agent ("pick a tool") gives up that determinism and produces
unpredictable conversation arcs — bad fit for a B2B sales context where the
flow has to be reliable and auditable.

LangGraph models the diagram literally: nodes = boxes, edges = arrows. State
is shared across nodes via the `state` channel. Each node either calls an LLM
(narrow, focused prompt) or a tool (deterministic).

### 3.2 Graph shape

```
                              ┌───────────────┐
                              │  ENTRY        │  ← session opens
                              │  (router)     │
                              └──────┬────────┘
                  ┌──────────┬──────┴──────┬──────────┐
                  ▼          ▼             ▼          ▼
              presales     guide       postsales    other
                  │          │             │          │
                  ▼          ▼             ▼          ▼
            ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐
            │figure_  │  │find /    │  │identify_│  │reclassify_or_│
            │out_need │→ │customize │  │problem  │  │improvise     │
            └─────────┘  └────┬─────┘  └────┬────┘  └──────┬───────┘
                              │             │              │
                              ▼             ▼              │
                         ┌─────────┐  ┌──────────┐         │
                         │happy?   │  │easily    │         │
                         │  gate   │  │fixable?  │         │
                         └──┬───┬──┘  └───┬───┬──┘         │
                       Yes │   │ No   Yes│   │ No          │
                           ▼   ▼         ▼   ▼             ▼
                          SELL HUMAN  RESOLVED HUMAN   FREE_CHAT/HUMAN
```

Terminals all write `outcome` to the `conversations` row.

### 3.3 Nodes

Each node is a small Python module under `backend/agent/nodes/`.

| Node                    | What it does                                                                                              | LLM? |
| ----------------------- | --------------------------------------------------------------------------------------------------------- | ---- |
| `entry_router`          | If user came in via a welcome chip → trivial dispatch. If via free-form composer → LLM classify.          | Yes  |
| `presales.figure_out`   | Multi-turn slot filling: industry → application → constraints. Hands off to `guide.find` with seeded state. | Yes |
| `guide.choose_approach` | Asks Find vs Customize. Deterministic if user picked a chip.                                              | No   |
| `guide.find`            | Calls `search_products` tool. Returns 3 SKUs with rationale.                                              | Yes  |
| `guide.customize`       | Walks a configurator (base type → modules → custom specs). Calls `build_custom_config` tool.              | Yes  |
| `guide.happy_gate`      | Renders the Yes/No card. Pure transition node.                                                            | No   |
| `postsales.identify`    | Collects SKU + symptom. Slot filling.                                                                     | Yes  |
| `postsales.match_kb`    | Calls `find_problems` tool (vector + filter on product_type). Returns top-1 with confidence.              | Yes  |
| `postsales.fix_gate`    | Renders "Did this help?" card. Pure transition.                                                           | No   |
| `other.reclassify`      | LLM tries to map free-form input to one of {presales, guide, postsales}. If confidence < 0.6 → free chat. | Yes  |
| `outcome_sell`          | Writes `outcome='sell'`. Triggers `create_rfq` tool. Renders the Sell terminal card.                      | No   |
| `outcome_human`         | Writes `outcome='human_handoff'`. Triggers `escalate_to_human` tool. Renders the handoff card.            | No   |
| `outcome_resolved`      | Writes `outcome='resolved'`. Optional feedback prompt.                                                    | No   |

### 3.4 Tools

Tools are bog-standard LangChain `@tool` functions. They are the ONLY way the
agent touches the DB or external systems — the LLM never sees raw SQL.

| Tool                    | Signature                                                              | Reads / writes                  |
| ----------------------- | ---------------------------------------------------------------------- | ------------------------------- |
| `search_products`       | `(query: str, filters: dict, limit: int) → list[Product]`              | reads products, product_embeddings |
| `recommend_categories`  | `(industry: str, application: str, limit: int) → list[ProductType]`    | reads use_cases, use_case_product_types, product_embeddings |
| `build_custom_config`   | `(family_code: str, modules: dict) → CustomConfig`                     | reads product_types, products   |
| `find_problems`         | `(sku: str, symptom_text: str, limit: int) → list[(Problem, Confidence)]` | reads problem_types, problem_embeddings |
| `get_solution`          | `(problem_type_id: int) → Solution`                                    | reads solutions                 |
| `create_rfq`            | `(conversation_id: int, sku: str, qty: int, payload: dict) → RFQ`      | writes CRM (HubSpot / Pipedrive / Salesforce) |
| `send_datasheet`        | `(product_id: int, email: str) → bool`                                 | reads products, calls mail service |
| `escalate_to_human`     | `(conversation_id: int, division_code: str, reason: str) → Ticket`     | writes CRM / Slack / Zendesk    |
| `set_outcome`           | `(conversation_id: int, outcome: str) → None`                          | writes conversations            |

Each tool returns structured Pydantic models. The agent's LLM calls use
**JSON mode / structured output**, never freeform tool argument parsing.

### 3.5 LLM choice

- Router and most-of-the-graph: a fast model is plenty (Claude Haiku 4.5,
  GPT-4.1-mini, or Gemini 2.0 Flash). The prompts are narrow, the tools do
  the heavy lifting.
- Pre-sales `figure_out_need` and Post-sales `match_kb` may benefit from a
  larger model when the user's description is vague — call Claude Sonnet 4.6
  or GPT-4.1 on those nodes only.
- Embeddings: `text-embedding-3-small` (1536-dim). Cheap, good enough for
  product / problem text.

Wrap the model behind a config so we can A/B swap. Default to one provider
to minimize prompt tuning churn.

### 3.6 State persistence & resumption

- LangGraph checkpointer writes graph state to Postgres after each node
  (use the `langgraph-checkpoint-postgres` adapter).
- `conversations.state` mirrors a denormalized slim version (industry, sku,
  symptom) for analytics queries — kept in sync via a graph hook.
- Resuming a session: client sends `session_uuid` → backend loads checkpoint
  → graph picks up at `current_node`.

### 3.7 Streaming

- Bot prose streams token-by-token (SSE).
- Cards (forms, product lists, gates, outcomes) are sent as **discrete
  structured events** — not generated by the LLM as prose. They come from
  the node's deterministic output, wrapped in:
  ```json
  { "type": "card", "card_kind": "product_results", "payload": { ... } }
  ```
  The frontend's `addCard` consumes them directly.

### 3.8 Observability

- LangSmith for trace-level inspection of every node call.
- Metrics table (`conversation_outcomes_daily`) populated via a nightly job:
  flow funnels, drop-off node, time-to-resolve, escalation rate per
  `main_type_code`.
- Per-message latency logged to the trace. Tool calls are spans.

### 3.9 Multilingual

- All bot-authored prose is generated in the user's selected language at
  generation time (LLMs do this fine).
- Content tables (`product_types.description`, `solutions.body_markdown`,
  etc.) have an `_i18n` JSONB column with translations curated by the
  content team. The agent picks the right key from `conversations.language`.
- Failsafe: if a translation is missing, fall back to EN and tag the
  message with `translated_at_runtime: true` so we can spot gaps.

## 4. Frontend integration (wiring the widget)

The current widget is a stand-alone visual layer with no API calls. To plug
in the backend, three changes:

### 4.1 Replace `_flows` mock bodies with a single dispatcher

```js
// widget.js — new shape (sketch)
async startFlow(flowName, opts) {
  this.state.flow = flowName;
  this.showScreen("chat");
  this._thread().innerHTML = "";
  this.showTyping();

  const stream = await this.api.startFlow(flowName, {
    session_uuid: this.sessionId,
    language: this.state.language,
    seed: opts || {},
  });

  for await (const event of stream) {
    this.hideTyping();
    if (event.type === "bot_text")  this.addBotMessage(event.text);
    if (event.type === "card")      this.addCard(this._renderCard(event));
    if (event.type === "gate")      this._addGate({ ...event, onYes: ..., onNo: ... });
    if (event.type === "outcome")   this._addOutcome(event);
    if (event.type === "suggest")   this._setSuggestions(event.replies);
  }
}
```

### 4.2 Backend endpoints

| Endpoint                                  | Purpose                                                  |
| ----------------------------------------- | -------------------------------------------------------- |
| `POST /api/sessions`                      | Open or resume a session by `session_uuid`               |
| `POST /api/flows/{flow}/start`            | Start a flow, returns an event stream (SSE)              |
| `POST /api/messages`                      | Send a user message (text, form submit, gate choice)     |
| `POST /api/tools/datasheet`               | Email a datasheet (called by `send_datasheet`)           |
| `POST /api/tools/rfq`                     | Submit an RFQ                                            |
| `POST /api/tools/escalate`                | Trigger human handoff                                    |
| `GET  /api/content/product-types`         | Read-only (cached) — populates configurator dropdowns    |
| `GET  /api/content/use-cases`             | Read-only (cached)                                       |

Everything runs through SSE for streamed responses except plain GETs.

### 4.3 Backend stack

- **FastAPI** + **uvicorn**. Async-first, plays well with LangGraph streaming.
- **Pydantic v2** for all message schemas (shared with frontend via JSON schema export).
- **SQLAlchemy 2.x** (async) for non-vector queries; raw SQL for `pgvector` ANN.
- **Alembic** migrations.
- Auth: simple API key for staging; cookie-bound session UUID for prod
  (anonymous OK; email-bound when captured).
- Container: one Docker image. Deploy on Fly.io / Render / your existing infra.

## 5. Adaptations from the diagrams

A few places where strict fidelity to the diagrams would hurt UX or rigor.
Calling them out so they're conscious decisions, not drift:

- **"Other → Force to improvise" should not be a dead end.** The diagram's
  "Force to improvise" terminal becomes our `other.reclassify` node, which
  loops back into the graph if the user's free-form text clearly maps to one
  of the three primary flows. If it stays ambiguous after 1–2 turns, we drop
  to a free-chat mode with a permanent "talk to a human" CTA. The diagram's
  loop ("No → back to User Input") is preserved as a soft retry, not a hard
  reset.
- **The "easily fixable?" gate is partially deterministic.** We don't let the
  LLM judge alone. The gate uses `solutions.confidence` (curated) + a count of
  prior identical resolutions for the same SKU. The LLM only paraphrases the
  outcome, doesn't decide it.
- **The "Database" node in the logic diagram is the same DB on both sides.**
  In the diagram it's drawn as separate cylinders on the pre-sales and
  post-sales branches; in implementation it's one Postgres instance.
- **Conversations track main_type via `code`, not `id`.** Easier to grep
  logs, doesn't require a join to read. The id is still there for FK
  integrity.
- **Customize-from-parts** isn't fully fleshed out in the diagrams. We treat
  it as a sub-flow of Guide with its own configurator UI (template +
  module slots). Modules come from `products` rows tagged with
  `specs.role = "module"`.

## 6. Phased rollout

Each phase is shippable on its own.

| Phase | Scope                                                                                                | Done when                                                                                          |
| ----- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **0** | Skeleton: FastAPI + Postgres + Alembic + a single `/api/health` route                                | Local stack comes up, migration runs                                                               |
| **1** | Content schema + seed loader + read-only tools (`search_products`, `recommend_categories`, `get_solution`) | A `curl` against `search_products` returns real SKUs                                          |
| **2** | LangGraph router + `presales` + `guide.find` + `outcome_sell` + `outcome_human`                      | The Guide flow end-to-end works from the live widget against the backend                           |
| **3** | `guide.customize` + `postsales.*` + KB embeddings                                                    | A user with a real SKU + symptom gets the right solution card                                      |
| **4** | Human handoff to a real channel (Slack channel or CRM ticket), email-capture flow, RFQ submission     | A handoff lands in a real engineer's queue with full conversation context                          |
| **5** | Streaming polish, multilingual content i18n, LangSmith dashboards, A/B harness                       | Funnel metrics visible; non-EN users get curated translations                                       |

## 7. Open questions

These need a product / business decision before Phase 4:

1. **CRM target.** HubSpot vs Pipedrive vs Salesforce vs in-house. Affects
   `escalate_to_human` and `create_rfq` tools.
2. **Which division gets the handoff by default.** The "About Us" page lists
   six divisions; we need a routing matrix from `(main_type, product_family)`
   → division inbox.
3. **Email service.** SendGrid / Postmark / SES for datasheet delivery and
   handoff notifications.
4. **Auth model for returning users.** Do we ever match a `session_uuid` to a
   known company by email domain? Useful for "Recent from your account" in
   Post-sales — but adds PII handling overhead.
5. **Cost ceiling per conversation.** Sets the LLM-tier choices in §3.5.

## 8. What lands in the widget once functionality is wired

The visuals already in `widget.js` map 1:1 to backend events. The only
client-side changes are:

- Each `_flows[name]` body shrinks to ~5 lines — open an SSE stream, render events.
- `addCard` learns a `_renderCard(event)` dispatcher that picks the right HTML template per `card_kind`.
- A small `api.js` module handles `session_uuid`, SSE parsing, retries.
- The mock typing delay in `_addGate` etc. goes away — real latency from the backend takes over.

No CSS changes. No restructure of `_flows`. The visuals stand as-is.
