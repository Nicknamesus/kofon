# Conversational direction — design note

The agent feels too button-driven right now — like filling out a form rather
than talking to someone. Predefined nodes are fine; the agent just needs more
freedom in *how* it uses them.

## The core distinction

The graph decides **what happens**. The LLM should write **how it sounds**.

Right now those are conflated: each node ships canned Python strings around a
slot-filling LLM call, so the decision tree leaks straight through the writing.
Every postsales turn reads as "ask symptom → ask clarification → present match"
in those exact words.

Predictability of *outcomes* (sales must know when handoff fires; engineering
must trust which fix was recommended) doesn't require predictability of
*phrasing*.

## What to change

1. **Toolbox, not flowchart, on soft surfaces.**
   Hand the LLM the list of capabilities (`identify_symptom`, `search_kb`,
   `present_problem`, `escalate`, `present_products`, `build_custom`) and let
   it pick the next call. LangGraph supports this pattern — mix it with the
   existing flow graph rather than replacing it.
   - Use the agent-loop pattern for: clarification, acknowledgment, off-topic,
     post-outcome chat.
   - Keep the flow graph for the spine: handoffs, outcomes, escalation
     triggers, RFQ generation.

2. **Collapse multi-node sequences on the easy path.**
   `postsales.identify → postsales.match_kb` is two LLM calls and two messages
   when a competent engineer would do both in one breath. A clear symptom like
   "my PG090 is leaking oil" should skip the clarification step entirely.

3. **Let the LLM write the prose.**
   Instead of `AIMessage(content="What's the symptom?")`, pass the LLM the
   conversation and the node's intent ("ask for the symptom in a way that
   acknowledges what the user just said"). Predictable transition, fresh
   wording.

## KB depth is the prerequisite

The vector floor (`MATCH_FLOOR=0.55`, `AMBIGUOUS_FLOOR=0.30`) only helps if
there's real material to match against. Three problems isn't enough.

Two-sided benefit:

- **Grounding** — more problems with richer descriptions cut down on the
  "I'm not 100% sure" ambiguous shortlists.
- **Voice** — `Solution.body_markdown` is currently an SOP. Useful as a fix,
  useless as raw material for natural-sounding paraphrasing. Add a field like
  `customer_facing_description` ("what this usually looks like from the
  customer's side") so the LLM has prose to riff off, not just labels.

## Recommended sequence

If/when this gets picked up, in this order:

1. **KB depth first** — cheap, makes the existing flow work better immediately
   with no architectural change.
2. **Loosen specific nodes** — let the LLM choose phrasing freely inside the
   existing graph.
3. **Agent-loop on soft surfaces only** — clarification, off-topic,
   post-outcome.

Don't go full agent-loop on day one. That's the kind of thing that's fun until
a sales handoff silently doesn't fire because the model decided "engineer
follow-up" sounded more polite.
