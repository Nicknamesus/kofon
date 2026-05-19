# Phase 3 — Summary

Phase 3 lights up the **fuzzy** branches of the routing diagram. Phase 2
shipped the deterministic Guide-Find rail; Phase 3 rides those rails
through three new flows that all require semantic / LLM judgment:

- **Post-sales** — a customer with a broken unit gets matched to a known
  problem via vector search, sees the curated fix, and the partially
  deterministic "easily fixable?" gate decides whether to mark resolved
  or escalate.
- **Guide-Customize** — sub-flow under Guide that walks the family's
  `spec_schema` (frame size → ratio → variant → ...), builds a custom
  configuration, and offers the closest stock SKU alongside.
- **Other-Reclassify** — the diagram's "Force to improvise" terminal is
  replaced with one cheap LLM re-routing pass. If the user's free-form
  text clearly maps to a primary flow, control hands off in the same
  turn; otherwise we fall through to a friendly free-chat reply with
  three suggestion chips and a "talk to a human" CTA. Per
  `memory/feedback-llm-before-human-handoff.md`.

Three new tools, two new tables, six new graph nodes (incl.
`outcome_resolved`).

---

## In plain terms

You can now have three more kinds of conversation:

- "**My PG090 is leaking oil**" → identifies the problem, surfaces the
  curated fix card and SOP link, asks "did that help?".
- "**I want a custom planetary, 90mm, 10:1 ratio, low backlash**" →
  walks the configurator, recommends the closest stock SKU, hands off
  to sales for a custom quote if you want one.
- "**Hi there**" → no longer a dead-end. A second-chance router maps
  intent to a real flow, or offers a clear free-chat path.

---

## What was built

### 3a — Embeddings schema + pluggable provider

Two new tables (`product_embeddings`, `problem_embeddings`) with
`vector(1024)` columns. Indexes use **HNSW** rather than ivfflat —
ivfflat needs enough vectors to train meaningful centroids, and with
the small seed sets we ship in Phase 3 it produces a degenerate plan
that silently returns zero rows for `ORDER BY embedding <=> ... LIMIT N`.

Migration: `alembic/versions/d4e2a9f5c10b_phase_3_embeddings.py`.

Provider lives in `app/embeddings.py` with three implementations:

| Provider     | When                                             | Setup                         |
| ------------ | ------------------------------------------------ | ----------------------------- |
| `hash`       | **Default.** CI / dev — zero-config, non-semantic | none                          |
| `bge-m3`     | Production-quality local — `BAAI/bge-m3`         | `pip install sentence-transformers` |
| `dashscope`  | Hosted alternative — Qwen `text-embedding-v3`    | `DASHSCOPE_API_KEY=...`       |

All three emit 1024-dim L2-normalised vectors so the schema and queries
are identical across providers. Provider is process-singleton; the
config var is `EMBEDDING_PROVIDER`.

The `hash` default lets `python -m app.seed.load` and `smoke_3a` run
end-to-end without a 2 GB model download or an API key — useful for
plumbing checks. It is **not** semantic, so the postsales user journey
needs to flip to `bge-m3` or `dashscope` to do anything useful.

### 3b — Embeddings seed loader

`app/seed/embed.py` builds short, focused text chunks per row:

```
product_type → "<name> (<family>) — <description>"
product      → "<sku> — <name>. specs: k=v, k=v, ..."
problem_type → "<label>. <description>"
```

Idempotent: each row stores a `text_hash` and only rebuilds when the
chunk changes. Stale rows for a key are deleted in the same pass. The
seed driver `app/seed/load.py` now calls this automatically after
content upsert, so the existing one-command flow stays one command:

```powershell
python -m app.seed.load
```

### 3c — Tools

- `find_problems(sku?, symptom_text, limit)` — pgvector cosine match
  over `problem_embeddings`. When `sku` is known we resolve the
  family and restrict the search to that family's problems; otherwise
  we search across all. Returns top-N `ProblemMatch` rows with
  similarity and the highest-confidence curated solution attached.
- `build_custom_config(family_code, modules)` — validates the family,
  echoes a normalised payload, and picks the closest stock SKU by
  exact-spec-match scoring. No DB writes — RFQ is Phase 4.

Schemas: `FindProblemsRequest/Response`, `ProblemMatch`,
`BuildCustomConfigRequest/Response` in `app/schemas/tools.py`.

### 3d — Post-sales nodes

Three nodes; same shape as Guide-Find from Phase 2 but riding the new
KB tool.

- `postsales.identify` — slot-fills SKU + symptom. SKU is optional
  (many tickets land with "the label fell off"); we only block on a
  symptom.
- `postsales.match_kb` — calls `find_problems`. Top match crossing
  `MATCH_FLOOR=0.55` → present problem + curated solution + a Yes/No
  gate. Below the floor → present a 3-row shortlist for the user to
  pick from. Zero matches → escalate.
- `postsales.fix_gate` — partially deterministic per BACKEND_PLAN §5.
  Gate-button clicks bypass the LLM entirely. Free-text replies go
  through a narrow yes/no/unclear classifier. Even a "yes" routes to
  human handoff when the surfaced solution's confidence ≤ 2 —
  better a callback than a false-resolve.

`outcome_resolved` (new terminal in `outcomes.py`) writes the
resolved outcome and an optional `feedback` card. Triggers
`create_rfq`/`escalate_to_human` come in Phase 4.

### 3e — Guide.customize

`app/agent/nodes/guide_customize.py`. Sub-flow under Guide, gated on
`slots.customize.active`. Reads the family's `spec_schema`, slot-fills
the keys via one focused LLM extraction + one targeted clarifier per
turn. Once at least `MIN_FILLED=2` keys are set (or the user says
they're done), calls `build_custom_config` and emits a configurator
card + a Yes/No gate that **reuses `guide.happy_gate`** — Yes →
`outcome_sell`, No → `outcome_human`.

The frontend opts in by sending `subflow: "customize"` on the message
payload (handled in `app/routers/agent.py`).

### 3f — Other.reclassify

`app/agent/nodes/other_reclassify.py`. Replaces the Phase-2 dead-end
where `flow=other` routed straight to `outcome_human`. One cheap LLM
re-classification call; if it lands on a primary flow with confidence
≥ 0.6, we set `state.flow` and the graph dispatcher routes the same
turn (proven pattern from Phase 2c `presales → guide` handoff).
Otherwise we emit a short free-chat reply with three suggestion chips
and a "talk to a human" CTA. After `RECLASSIFY_MAX_ATTEMPTS=2`
unhelpful turns we drop through to `outcome_human`.

### 3g — Graph rewiring + smokes

`app/agent/graph.py` adds the new nodes plus two dispatch helpers
(`_guide_dispatch`, `_postsales_dispatch`) so the START / router /
after-reclassify branches can decide which sub-node to enter based on
slot state. The graph shape:

```
START → entry_router ──┬── presales.figure_out ── → guide.find ── …
                       ├── guide.find ──┐
                       ├── guide.customize ─┤→ guide.happy_gate ──┬── outcome_sell
                       │                    │                     └── outcome_human
                       ├── postsales.identify → postsales.match_kb ──┐
                       │                                             ├── (ambiguous → END)
                       │                                             └── postsales.fix_gate ──┬── outcome_resolved
                       │                                                                       ├── outcome_human
                       │                                                                       └── (re-ask → END)
                       └── other.reclassify ──┬── (re-routed → primary flow node)
                                              └── (free-chat → END)
```

## Smoke test trail

| Sub-phase | Script                          | Outcome                                                                       |
| --------- | ------------------------------- | ----------------------------------------------------------------------------- |
| 3a        | `python -m app.agent.smoke_3a`  | 1024-dim embedding; `find_problems` returns 3 matches for a planted symptom.  |
| 3b        | `python -m app.agent.smoke_3b`  | Postsales graph traversed end-to-end. Terminal outcome on a semantic provider; on `hash` the assertion relaxes to "graph reached the postsales subgraph". |
| 3c        | `python -m app.agent.smoke_3c`  | Customize: 3 turns → `outcome_sell` for the custom-build path.                |
| 3d        | `python -m app.agent.smoke_3d`  | Reclassify: greeting → free-chat; intent → flow handoff on the next turn.     |

Run them after `docker compose up -d`, `alembic upgrade head`, and
`python -m app.seed.load`. Smoke 3b/c/d each call the live DeepSeek API
and reset their session_uuid, so they're safe to re-run.

---

## What is explicitly NOT in Phase 3

- **CRM / RFQ / email side effects.** `outcome_sell` / `outcome_resolved`
  / `outcome_human` still only write to graph state. Phase 4 wires the
  real tools (`create_rfq`, `escalate_to_human`, `send_datasheet`).
- **Widget renderers for the new card kinds.** The backend emits
  `problem_match`, `problem_candidates`, `custom_config`, and `suggest`
  cards; the widget's `_renderCard` learned `gate` / `recommendations`
  / `product_results` / `outcome` in Phase 2 and falls back gracefully
  on unknown kinds. Adding bespoke renderers is a small follow-up.
- **Real semantic embeddings by default.** The provider defaults to
  `hash` (deterministic, non-semantic) so dev / CI works zero-config.
  Production needs `EMBEDDING_PROVIDER=bge-m3` (with
  `sentence-transformers`) or `dashscope` (with `DASHSCOPE_API_KEY`).
- **`writes to `conversations` / `messages` tables.** Graph state is
  persisted via the LangGraph checkpointer; the analytics-shaped
  Alembic tables still aren't being written. Small follow-up.

---

## Discovered along the way

A few notes worth flagging so future readers don't repeat them.

- **ivfflat + tiny tables = empty results.** A `vector(1024)` ivfflat
  index trained on 3 rows produces a degenerate plan that silently
  returns zero rows for `ORDER BY embedding <=> $1 LIMIT N`. HNSW has
  no training prerequisite and degrades gracefully. Use HNSW until the
  seed set is large enough to train ivfflat.
- **SQLAlchemy `.order_by("label").limit(N)` is brittle.** Ordering by
  a label string survives a bare `select(...)` but is silently
  dropped when chained with `.limit(...)` — the resulting query is
  unordered and returns wrong rows. Always order by the column
  expression itself (`order_by(dist_expr)`), not the label name.
- **Pre-empt the eager LLM.** `postsales.identify` extracts a "symptom"
  from even very vague openers ("something is wrong"). The match_kb
  ambiguous-shortlist branch is what makes that tolerable — a strict
  block-on-detail policy turned out to feel worse in dogfooding than
  showing two or three candidates and letting the user pick.
