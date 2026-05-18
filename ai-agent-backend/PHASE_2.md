# Phase 2 — Summary

The agent comes alive. Phase 1 built the data layer and read-only
tools; Phase 2 wraps a **LangGraph state machine** around them, streams
events to the frontend over **SSE**, and replaces the widget's mocked
`_flows` with real conversations.

LLM provider is **DeepSeek** (`deepseek-chat`) — the project runs from
China, where Anthropic/OpenAI/Google aren't reachable. See
`memory/project-china-llm-constraint.md`.

---

## In plain terms

You can now have a real conversation with the agent. It will:

- classify your intent into one of four flows (Pre-sales, Guide,
  Post-sales, Other),
- run a multi-turn slot-fill to figure out what you need,
- call into the Phase 1 tools (`recommend_categories`, `search_products`)
  to fetch real SKUs from Postgres,
- present them as cards in the widget,
- ask a Yes/No "happy?" gate,
- and end the conversation by writing an `outcome` (sell or human handoff).

State is persisted in Postgres via a LangGraph checkpointer, so closing
and reopening the browser resumes mid-conversation.

### What "it works" means

```powershell
cd X:\programming\websites\kofon\ai-agent-backend
docker compose up -d
.\.venv\Scripts\Activate.ps1
python -m app.agent.setup_checkpointer       # once
python -m app.serve --port 8001              # FastAPI + agent

# (in another shell)
cd X:\programming\websites\kofon\ai-agent-addon
python -m http.server 8002

# Open http://localhost:8002/demo.html in a browser.
# Click "I know what I need" → describe a planetary gearbox → see SKUs → say yes.
```

---

## What was built, in five sub-phases

### 2a — LangGraph plumbing

Proves the LangGraph + DeepSeek + Postgres checkpointer pipeline works
before any real flow logic exists.

- `app/agent/state.py` — `AgentState` TypedDict (slots, messages,
  cards, flow, current_node, outcome).
- `app/agent/llm.py` — DeepSeek factory. Cheap model (`deepseek-chat`)
  by default; reasoner held in reserve for Phase 3.
- `app/agent/checkpointer.py` — `AsyncPostgresSaver` wrapped in an
  async context manager. Tables created via
  `python -m app.agent.setup_checkpointer`.
- `app/agent/graph.py` — `build_echo_graph` (one node, smoke test).
- `app/agent/smoke_2a.py` — two turns under the same `session_uuid`
  proves the checkpointer restores history.

**Critical Windows fix**: on Python 3.14 + Windows, `asyncio`'s default
`ProactorEventLoop` is incompatible with psycopg's async driver (which
the LangGraph checkpointer uses). Setting the event-loop policy via
`asyncio.set_event_loop_policy(...)` is unreliable here because uvicorn
calls `asyncio.run` after our app loads. The robust fix is in
`app/serve.py`: we build a `SelectorEventLoop` ourselves and run
`uvicorn.Server.serve()` inside it. This is the recommended entrypoint
on Windows.

### 2b — Guide-Find flow

The simplest deterministic branch — chosen first per the user's
mental model ("the rigid stuff first, fuzzy stuff in Phase 3").

Nodes:
- `guide.find` — single LLM call extracts `SearchProductsFilters`,
  decides if there's enough signal to search, and either runs the
  search or asks a targeted clarifying question. Pre-existing filters
  (seeded by Pre-sales) are merged so the family carries through.
- `guide.happy_gate` — partially deterministic per BACKEND_PLAN §5.
  Gate-button clicks set `slots.happy` directly (no LLM). Free-text
  replies go through a narrow classifier (yes/no/unclear) with one
  re-ask before falling through to human handoff.
- `outcome_sell` / `outcome_human` — terminal nodes. Write
  `state.outcome` and emit a structured `outcome` card.

Graph shape:

```
START → guide.find ─┬─ "ask more"     → END
                    ├─ "search"       → END     (await gate reply)
                    └─ (user replied to gate) → guide.happy_gate
                                                  ├─ outcome_sell  → END
                                                  ├─ outcome_human → END
                                                  └─ (re-ask)      → END
```

Smoke test `app/agent/smoke_2b.py` drives three turns:
"I'm looking for a gearbox" → "Planetary, low backlash, 90mm, ~80 Nm"
→ "Yes, PG090-10-HP looks perfect." End state: `outcome='sell'`,
candidates persisted, `current_node='outcome_sell'`.

### 2c — Router + Pre-sales

Adds the first node every conversation hits, plus the first
multi-turn slot-fill flow.

- `entry_router` — DeepSeek classifies one of `presales | guide |
  postsales | other`. Bypassed entirely when the frontend sends `flow`
  in the payload (chip click).
- `presales.figure_out` — two-phase node:
  - Phase 1: extract `industry` + `application`, ask one targeted
    follow-up if either is missing.
  - Phase 2: call `recommend_categories`, present the top family with
    rationale, hand off to `guide.find` with `slots.filters.family`
    seeded.

Graph entry dispatch now looks at `state.flow` (and falls back to
`entry_router` if unset) and at `state.outcome` (END if terminated).

Smoke test `app/agent/smoke_2c.py` drives the full chain:
"I need motion for a cobot joint" → router classifies as `presales`
→ pre-sales recommends CaesarPlanetary → user accepts → guide.find
runs in the same turn → returns SKUs → user picks → outcome_sell.

### 2d — SSE endpoints

Wraps the graph in HTTP. The widget never sees LangGraph; it just
streams events.

- `POST /api/sessions` — convenience: returns a fresh UUID for first-
  time clients. Clients can also generate their own (the widget does,
  via `localStorage`).
- `POST /api/messages` — the single endpoint. Body:
  `{session_uuid, text?, flow?, gate_choice?}`. Streams SSE events:

  ```
  event: bot_text   data: {"text": "..."}
  event: card       data: {"kind": "product_results", "payload": {...}}
  event: card       data: {"kind": "gate", "payload": {...}}
  event: outcome    data: {"outcome": "sell"}
  event: done       data: {}
  ```

  Each card kind corresponds to a structured payload the frontend
  renders deterministically — *not* prose from the LLM.

- `app/routers/agent.py` — uses `graph.astream(stream_mode="updates")`
  to grab per-node state deltas and converts them to SSE events on
  the fly. No "send the full final state and let the client diff"
  pattern.

- CORS: dev-wide `allow_origins=["*"]` so the widget served from
  `http.server` on port 8002 can hit the API on 8001. Replace with an
  explicit allowlist in prod.

Smoke test `app/agent/smoke_2d.py` uses httpx to consume the SSE
stream and verify event ordering: `bot_text` → `card(product_results)`
→ `card(gate)` → `done`, then `gate_choice="yes"` → `bot_text` →
`card(outcome)` → `outcome` → `done`.

### 2e — Widget wiring

Replaces the visuals-only `_flows` with the SSE dispatcher per
BACKEND_PLAN §4.1.

- `ai-agent-addon/api.js` (new) — `AIAgentAPI.streamMessage` opens an
  SSE connection, parses the event stream, calls a per-event handler.
  Persists `session_uuid` in `localStorage`.
- `ai-agent-addon/widget.js` — minimal patch:
  - `startFlow(name, opts)` checks `cfg.apiUrl`. If set, calls
    `_startFlowApi` (real backend). If unset, falls back to the mock
    `_flows` (visuals-only — preserves the pre-2e demo experience).
  - Composer `send` is similarly mode-aware.
  - New methods: `_streamFromApi`, `_handleAgentEvent`, plus four
    card renderers (`_renderProductResultsCard`,
    `_renderRecommendationsCard`, `_renderGateCard`,
    `_renderOutcomeCard`).
- `ai-agent-addon/config.kofon.js` — `apiUrl: "http://127.0.0.1:8001"`.
  Remove this line to revert to mocks.
- `ai-agent-addon/widget.css` — added styles for the product-row card.

The addon stays drop-in for any other site — the apiUrl is the only
config the host needs to set, and `AIAgentAPI` is namespaced on
`window` exactly like `AIAgent`.

---

## Smoke test trail

| Sub-phase | Script                          | Outcome                                                           |
| --------- | ------------------------------- | ----------------------------------------------------------------- |
| 2a        | `python -m app.agent.smoke_2a`  | Two echo turns; checkpointer restores history on turn 2.          |
| 2b        | `python -m app.agent.smoke_2b`  | Three turns; outcome=sell; one candidate emitted.                 |
| 2c        | `python -m app.agent.smoke_2c`  | Four turns; presales → guide handoff in turn 2; outcome=sell.     |
| 2d        | `python -m app.agent.smoke_2d`  | SSE event stream printed; turn 2 closes with `outcome` + `done`.  |
| 2e        | Open `demo.html`                | Click chip → real flow → real SKUs → gate buttons → outcome card. |

---

## What is explicitly NOT in Phase 2

- **Post-sales agent.** Phase 3 — needs the fuzzy KB matching with
  problem embeddings. Currently routes to `outcome_human` so users
  hitting this flow get an immediate handoff.
- **`guide.customize`.** Phase 3 — the configurator sub-flow.
- **`other.reclassify`.** Phase 2 routes `other` to `outcome_human`
  too. Phase 3 adds the "try to map to a primary flow once, else
  free-chat" logic.
- **Token streaming.** `bot_text` events fire once per AIMessage with
  the full content. Token-by-token streaming is Phase 5 polish.
- **Tool calling by the LLM.** The agent calls tools deterministically
  from inside nodes — the LLM never decides to call a tool. Widening
  this is one of the levers discussed in our pre-Phase-2 chat.
- **Real CRM / email / RFQ.** Phase 4. Outcomes write
  `conversations.outcome` (well, the checkpointer state — the
  `conversations` Alembic table itself isn't being written to yet;
  that's a small follow-up).
- **Embeddings.** Phase 3 — needed for `postsales.match_kb` and a
  better-quality `search_products`. Will use a Chinese embeddings
  provider (BGE local or Qwen API), not OpenAI's
  `text-embedding-3-small`.
- **Authentication.** Endpoints are open; CORS is `*`. Lock down for
  prod.

---

## Post-2e polish (in-flight UX fixes)

A few small fixes shipped during initial dogfooding. None changes the
shape of Phase 2, but they're worth flagging so future readers know
they're already in:

- **Session lifecycle on the widget.** Clicking a chip from the welcome
  screen now resets the persisted `session_uuid` (and the back-arrow
  does the same when returning to welcome). Without this, an old
  terminated thread silently no-ops the next chip click. Composer-only
  messages still continue the current conversation. The server also
  short-circuits a "this conversation already wrapped up" message when
  it sees a message arrive on a thread with `outcome` set.
- **Markdown rendering.** The widget runs a minimal markdown pass over
  every `bot_text` event — `**bold**`, `*italic*`, `_italic_`. Runs
  AFTER HTML-escape so it can't smuggle in tags. Anything more elaborate
  is Phase 5 polish.
- **Recommendation gate.** Pre-sales now emits a `gate` card alongside
  the recommendation card ("Yes, show me products" / "No, talk to an
  engineer"). Yes hands off to `guide.find`; No lands cleanly on
  `outcome_human`. Replies typed in the composer are classified by a
  tiny LLM call (with a fast path for literal "yes"/"no" from the gate
  buttons).
- **LLM family-pick fallback in pre-sales.** When `recommend_categories`
  returns no curated match, instead of escalating immediately the node
  asks DeepSeek to pick the closest fit from `product_types` (with
  `no_match=true` as an honest escape hatch). Validated against the DB
  to block hallucinated codes. See
  `memory/feedback-llm-before-human-handoff.md` — this is the template
  for similar fallbacks in `postsales.match_kb` and `guide.customize`
  when Phase 3 lands.

---

## How Phase 2 sets up Phase 3

| Phase 3 work                | What Phase 2 gives it                                                              |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `postsales.identify`        | Slot-fill pattern is already proven in `presales.figure_out`.                       |
| `postsales.match_kb`        | Just needs the embeddings table populated + a new `find_problems` tool.            |
| "easily fixable?" gate      | `guide.happy_gate` is the template (partially deterministic, LLM paraphrases).     |
| `guide.customize`           | Another `guide.find`-style node; the state machine and card patterns are reusable. |
| `other.reclassify`          | LLM-driven flow change is already proven by `presales → guide` handoff in 2c.      |
| Better SKU ranking          | Replace ILIKE in `search_products` with pgvector ANN; signature stays the same.    |
