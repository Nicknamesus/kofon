# Phase 5+ plan — Conversation logging, analysis, and feedback loop

> Status: **planning only**, not implementation. Captures the design
> direction for "log every conversation, analyse it, use it to better
> the agent" so the work can be picked up cleanly in a future phase.

Phase 4 already gave us most of the raw substrate — full transcripts,
outcomes, side-effect audit. The work ahead is **instrumentation +
analysis + a review surface + a path back into the agent**.

---

## What's already in place

- `messages` table — full transcript per session, role + content_type
  + content + which graph node produced it.
- `conversations` — outcome, division, language, current_node at end,
  slim state snapshot.
- `crm_calls` / `email_calls` — side-effect audit (provider-agnostic).
- LangGraph checkpoints — internal slots / extraction results per node
  (richer than `messages`, but blob-shaped).

So "logging" is essentially done. What's missing is the four layers
below.

---

## Layer 1 — Per-node instrumentation (traces)

LangSmith was already on the Phase 5 roadmap and this is its job. Wrap
every node + tool call so we capture:

- token counts
- latency
- prompt / response text
- structured-output validation hits
- retries / fallbacks

Without it we can compute **what** went wrong from `messages` but not
**why** — e.g. "router picked `other` because the slot-fill LLM
returned malformed JSON and we fell through". That `why` is the load-
bearing piece for prompt improvements.

Cost-side decision: 100% sampling in dev, sub-100% in prod, or
self-hosted? LangSmith has an OSS option.

---

## Layer 2 — Ground-truth backfill from the CRM

`outcome='sell'` doesn't tell us if the deal closed. Phase 4 stores
the internal `rfqs` / `tickets` records — extend them with backfill
columns and a sync job:

- Zoho webhook (or nightly pull) updates `rfqs.status` →
  `closed_won` / `closed_lost` / `disqualified`.
- Same for `tickets` → `resolved_by_human_in_N_minutes`.
- Conversations row gets a denormalised mirror so analytics queries
  don't have to join across.

Now we can compute **conversion by flow / by division / by SKU** —
the only metric that actually answers "is the agent helping."

Webhook vs poll: webhook is real-time but needs a public endpoint +
signature verification; nightly poll is simpler and probably fine
since deals don't close in seconds.

---

## Layer 3 — Aggregation views (analysis)

A handful of materialized views or scheduled jobs, nothing exotic:

| View | What it shows | What it tells us |
| ---- | ------------- | ---------------- |
| `funnel_by_node` | count of conversations ending at each `current_node`, grouped by outcome | where do conversations die? |
| `postsales_match_quality` | histogram of vector similarity scores on first match | if the mass is left of `MATCH_FLOOR`, KB needs more rows, not a better model |
| `router_accuracy` | pairs where `entry_router` picked X but `other.reclassify` later re-routed to Y | each X→Y is a router error worth a few-shot example |
| `slot_extraction_misses` | `guide.find` turns where the extractor returned no filters | bad prompt vs. genuinely ambiguous input |
| `language_vs_outcome` | outcome rate broken down by `conversations.language` | are non-EN users falling out at a higher rate? |
| `turn_count_distribution` | turns per conversation, grouped by outcome | long conversations without a terminal usually mean derailed rails |

---

## Layer 4 — Qualitative review surface

Aggregates only get you so far — someone (probably the content team)
has to actually **read** conversations every week. Cheapest version is
a SQL view + CSV export, sorted by "worst signals first":

- All `human_handoff` where `reason='low_confidence_kb_match'`
  (KB gap)
- All conversations that hit `other.reclassify` more than once
  (router confusion)
- All `sell` outcomes whose CRM backfill came back `closed_lost`
  (false-positive sell)
- Conversations with > 8 user turns and no terminal outcome
  (rail derailed)

A web UI is nicer but not required — start with the CSV.

---

## What the analysis drives back into the agent

Five levers, roughly priority order:

1. **KB depth** — missed postsales matches → new `problem_types` rows
   + the `customer_facing_description` field flagged in
   `memory/project-kofon-conversational-direction.md`. Cheapest,
   highest-leverage. Bad matches almost always mean missing content,
   not a worse model.
2. **Eval fixture set** — every reviewed conversation becomes a
   regression test: input messages → expected node path → expected
   card kinds. Once we have ~100 of these, any prompt change can be
   run against the suite to see what broke. Foundation for everything
   else.
3. **Router + slot-extractor prompts** — backed by mislabel pairs from
   layer 3. Adding 2–3 few-shot examples from real misses is usually
   worth more than rewriting the prompt.
4. **Voice loosening** — also from
   `memory/project-kofon-conversational-direction.md`. Once we can A/B
   at the node level against the eval set, canned strings can be
   replaced with LLM phrasing without worrying about silent flow
   breakage.
5. **Tool gaps** — conversations where no current tool would have
   helped (e.g. "what's the lead time for 50 units of PG090?" and we
   have no `get_lead_time` tool). File as new-tool tickets.

---

## Decisions to make before building

These are the load-bearing choices that affect the shape of the
implementation — worth deciding before the first line of code.

- **PII boundary.** `messages.content` may contain user-typed text.
  Pick one:
  - redact at write time via something like Presidio (recommended for
    production)
  - keep raw with restricted query access
  - keep raw with a TTL (e.g. 90 days, then hash the content column)

  Affects table shape — easier to decide now than retrofit.

- **Retention vs eval set.** Eval fixtures need to outlive the
  conversation TTL. Plan a separate `eval_fixtures` table that copies
  the conversation at review time, so deleting the source doesn't
  break the regression suite.

- **Trace cost / sampling.** LangSmith bills per trace; chatty demos
  add up. Decide on a sampling rate per environment, or self-host.

- **Who owns the review loop.** Engineering, content, or both?
  Affects whether the surface is a CSV (engineering self-serves) or a
  UI (content team self-serves).

- **Backfill plumbing.** Zoho webhook vs nightly poll. Mentioned in
  layer 2 — easier to decide once we know how often deals actually
  close in Kofon's pipeline.

---

## Suggested rollout order

If/when this becomes a real phase, ship in this order:

1. **LangSmith wired in** (~1 day, basically a config flag). Gives
   traces immediately, no schema changes.
2. **`eval_fixtures` table + "promote this conversation to fixture"
   path** — even before review tools, just so anything interesting
   noticed during demos gets captured.
3. **CRM-backfill columns on `rfqs`/`tickets`** + a Zoho webhook (or
   poll job).
4. **The aggregation views above + a CSV export endpoint.**
5. **KB-depth pass** driven by the postsales-similarity histogram.
   Should ship before any voice / agent-loop work, per
   `memory/project-kofon-conversational-direction.md`.
6. **Voice / agent-loop experiments** on soft surfaces, gated on
   eval-set regressions.

---

## Related memory / documents

- `memory/project-kofon-chatbot.md` — current state of the project.
- `memory/project-kofon-conversational-direction.md` — direction for
  making the agent feel less button-driven; the voice/loop work in
  step 6 is gated on the eval set + KB depth from earlier steps.
- `memory/project-china-llm-constraint.md` — LangSmith + tracing
  vendor choice is constrained by this; pick a region or self-host.
- `PHASE_4.md` — open items from Phase 4 that overlap (contact
  capture, real division inboxes).
