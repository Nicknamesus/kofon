# LLM Freedom Ladder

A roadmap for giving the agent's LLM progressively more degrees of freedom —
without losing the safety guarantees that make its responses trustworthy.

The agent today is deliberately rigid: we are *sure* of its responses, but the
rigidity sometimes makes them stiff. This document maps how to loosen that,
level by level, and which guardrails must never loosen with it.

## Where the constraints actually live

The LLM is boxed in by **four independent mechanisms**. Each can be relaxed on
its own, and — critically — each can be relaxed *per node*.

| Mechanism | Where | What it controls |
|---|---|---|
| **Deterministic graph** | `app/agent/graph.py` — `_*_dispatch` / `_after_*` | *Routing* — which node runs, every transition, every outcome. The LLM never picks the next step. |
| **Structured output** | `_Extraction`, `_Route`, `_ProceedVerdict` Pydantic models | *Schema* — the LLM may only emit fixed fields/enums. `with_structured_output` forbids prose. |
| **Templated copy** | `t()` / `app/i18n.py` | *Voice* — nearly all user-facing text is pre-written. The LLM fills only narrow fields (`follow_up_question`, `rationale`). |
| **Curated tools** | `search_products`, `recommend_categories` (`app/tools.py`) | *Grounding* — product facts come from SQL, never the model. |

The **rigid feeling** comes mostly from #3 (templated voice) and partly #2
(one-shot extract → canned follow-up). The **safety** comes mostly from #1
(deterministic routing) and #4 (grounded facts).

**Key insight:** freedom is not one knob — it's four, and they're dial-able per
node. You can relax voice and local conversation (kills rigidity) without
touching routing and grounding (keeps safety).

---

## The freedom ladder

Each level is a superset of the previous one.

### L0 — Current
Deterministic everything. Safe, reproducible, rigid.

### L1 — Voice freedom *(recommended first step, near-zero risk)*
Keep graph, schema, and tools exactly as-is. Add a **voice pass**: after a node
assembles its structured payload (product list, recommendation, gate question),
an LLM rewrites the templated `t()` string into natural prose *given that
payload as data*.

- **Change:** one `render_voice(payload, lang)` helper in `app/agent/llm.py`;
  nodes pass their structured result through it instead of (or alongside) `t()`.
- **Gain:** kills ~80% of the rigidity complaint. This is exactly the
  `memory/project-kofon-conversational-direction.md` memo — separate flow (what
  happens) from voice (how it sounds).
- **Guardrail:** the voice LLM gets the payload as fenced data and may
  *rephrase only* — a validator confirms no SKU/number appears that isn't in the
  payload. Falls back to `t()` on validation failure or timeout.
- **Risk:** cosmetic only. Wrong facts are blocked by the grounding validator;
  worst case is a clumsy sentence.

### L2 — Local conversational freedom *(per rigid node)*
Within a single node, replace one-shot "extract → canned follow-up" with a short
bounded **conversation to fill the slots**. The LLM picks its own clarifying
questions, acknowledges tangents, varies phrasing — but still must emit the same
structured slots, and **the graph still owns every transition**.

- **Change:** in nodes like `presales.figure_out` (phase 1) and `guide.find`
  clarification, let the LLM both converse *and* return `_Extraction`. The node
  still gates on `ready` / `ready_to_search`.
- **Gain:** the back-and-forth feels human; no more "don't ask for both at once"
  stiffness.
- **Guardrail:** turn cap per node (e.g. 3 clarifications then escalate — the
  `memory/feedback-llm-before-human-handoff.md` pattern); slots still validated;
  outcome still graph-decided.
- **Apply surgically:** turn this on for the nodes that feel robotic; leave gates
  (`happy_gate`, `fix_gate`) deterministic, since a misread yes/no there
  corrupts routing.

### L3 — Tool-mediated freedom within a flow
Dissolve the hand-coded phase machine *inside one flow*. Replace e.g. the
`_guide_dispatch` / `find_phase` state logic with an LLM that has tools —
`search_products`, `recommend_categories`, `present_card`, `ask_user`,
`escalate` — and decides which to call. The graph keeps only flow **boundaries**
(entry router in, outcomes out).

- **Change:** collapse `guide.find` + `guide.customize` + `guide.happy_gate` into
  one tool-calling agent node; keep `entry_router` and `outcome_*` deterministic.
- **Gain:** handles edge cases the phase machine can't (user changes mind
  mid-search, asks to compare two families, mixes customize + search).
- **Guardrail:** tools are the *only* source of product facts (grounding
  survives); a wrapper validates every tool call and still emits the `cards`
  contract; outcomes can only be set via the `escalate` / `sell` tools, which the
  harness checks.
- **Risk:** real. Non-deterministic routing. Needs the eval harness (below)
  before shipping.

### L4 — Single-flow agent loop
Collapse the *whole* graph into one ReAct-style agent: full toolset + a policy
system prompt, looping until it calls a terminal tool. The "algorithm" survives
**only as a guardrail shell** — grounding validator, injection armor, language
pin, outcome integrity, card contract, cost/turn caps — not as a flow
controller.

- **Gain:** maximum naturalness; one prompt to maintain instead of 12 nodes.
- **Loss:** reproducibility, the analytics slots (`conversations.state`
  denormalization), predictable cost. Two identical users can get different
  journeys.

### L5 — Full freedom *(thought experiment — NOT a target)*
No graph, no slots, no templates, no validators. One system prompt + tools + raw
conversation. What you give up, stated explicitly:

- **Grounding** — without the validator, the model can state a torque rating or
  backlash figure that isn't in the catalog. In B2B motion components that's a
  spec-liability problem, not a tone problem.
- **Compliance** — no guarantee a human handoff fires when it must.
- **Reproducibility & analytics** — the slot mirror that powers reporting
  disappears.
- **Cost/latency** — unbounded tool loops on `deepseek-reasoner`.

This is why L5 is the wrong target even in principle. The right destination is
**L4's freedom with L0's guarantees** — achieved by keeping the guardrail shell
while removing the flow controller.

---

## Guardrails that must survive at every level

Orthogonal to freedom — these should *never* be relaxed, regardless of level:

1. **Grounding validator** — product facts (SKU, specs, prices, links) come only
   from tool output; strip/block any the model invents. The single most
   important guardrail for B2B.
2. **Prompt-injection armor** — `PROMPT_ARMOR` + `fence()` +
   `sanitize_user_input`. More LLM freedom = bigger attack surface, so this
   matters *more* as you climb.
3. **Language pin** — `language_instruction(lang)` must wrap every generative
   call.
4. **Outcome integrity** — `outcome` / human-handoff can only be set through
   validated paths, never inferred from free prose.
5. **Cost & turn caps** — bounded loops; cheap `deepseek-chat` for
   routing/extraction, `deepseek-reasoner` only where it pays.

---

## Recommended path

1. **Build an eval harness first.** Promote the existing `smoke_3*` / `smoke_4`
   scripts into a scenario suite (20–40 conversations with asserted outcomes:
   right family recommended, handoff fired, no hallucinated SKU). **You cannot
   safely climb past L2 without this** — it's the instrument that tells you
   whether more freedom helped or regressed.
2. **Ship L1 (voice pass) globally.** Highest rigidity-reduction per unit risk.
   Directly executes the existing conversational-direction memo.
3. **Ship L2 on the 2–3 nodes that feel most robotic** (`presales.figure_out`,
   `guide.find` clarification). Leave gates and the entry router deterministic.
4. **Pilot L3 on the `guide` flow only**, behind a config flag, measured against
   the eval harness. Keep `postsales` deterministic (problem-matching has
   correctness/safety stakes).
5. **Treat L4 as a destination, not a near-term step** — only after L3 proves out
   on guide and the eval suite is trusted.

**Dial per node, never globally.** The architecture already supports this — each
node is an independent `run()` with its own LLM call, so you can run L3 on guide
while postsales stays L0.
