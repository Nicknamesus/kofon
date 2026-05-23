# Analysis: `main_concerns.md` vs `chatgpt_concerns.md`

## Context

Two parallel risk lists for the Kofon agent sit in `ai-agent-backend/`:
- `main_concerns.md` — the team's own shortlist of what they consider most important (20 items across General / Security / Maintenance / Misc / Testing).
- `chatgpt_concerns.md` — ChatGPT's exhaustive enumeration of risks a chairman/buyer might raise (25 numbered sections).

The point of the analysis: see which of ChatGPT's concerns the team has already internalised, which ChatGPT raised that the team **hasn't** flagged (potential blind spots), and which the team flagged that ChatGPT **missed** (these are usually the things only you can see from inside the product). Then map each cluster against what Phase 4 of the backend already covers vs. what's still open, so we know where the real work is.

---

## 1. Where the two lists agree (validated priorities)

These are the concerns that show up on both sides. They are the safest investments to make next because both an outside critic and the team think they matter.

| Theme | main | chatgpt | Current state |
|---|---|---|---|
| Human handoff / not replacing sales | G1 | §23 | `outcome_human` exists as a routing target; **no live takeover UX**, no account → no identity for the human to "become". |
| Spec-driven questioning before recommending | G3 | §5, §9 | `presales_figure_out` + `guide_customize` ask spec questions; the questioning is short and shallow vs. §5's checklist (wheel diameter, climbing angle, brake, IP rating, etc.). |
| Hallucination control / answer accuracy | G4 ("backlash answer — was that DeepSeek?") | §3 | Postsales path is grounded in pgvector (`MATCH_FLOOR`); **the presales/guide path is mostly LLM voice** — the backlash answer almost certainly was DeepSeek's prior, not retrieval. Confirms G4's suspicion. |
| Latency vs detail tradeoff | G5 | §17 | No token streaming yet (it's in the Phase 5 plan). Message verbosity is currently hardcoded in nodes — no policy. |
| Customer priority classification | G6 | §9, §10 | Not implemented. `conversations` rows exist (basis for scoring) but no scoring node. |
| Structured customisation form | G8 | §6, §9 | `build_custom_config` tool exists in the engine. **Not yet surfaced as a field-by-field widget** — the spec is a free-text LLM extraction today. |
| Sensitive data leakage | S1 | §13 | No public/sales/engineering KB tiering exists. Product KB is one pool. |
| Prompt injection | S2 | §14 | No detection layer; system prompt + node prompts are the only defence. |
| Maintenance burden | M1, M2 | §19 | No manual; no templates; the seed pipeline (`extract_url`, `extract_pdf`) is the closest thing to a "template" but isn't documented for non-builders. |
| Stress / load | Misc | §17 | Not tested. |
| Defensibility / not copiable | Misc | §22 | ChatGPT's answer (moat = Kofon-specific KB + selection logic + workflow) is the better framing of main's question. |
| ROI / conversation analysis | Misc, Testing | §11 | `conversations` + `messages` get written every turn (analytics-ready). No dashboard, no metric definitions yet. |

**Takeaway:** the team's intuitions track ChatGPT's externally-derived list closely. Of the 12 themes above, ~9 are still blockers; 3 (handoff target, ROI substrate, customisation tool) have plumbing but no surface.

---

## 2. In `chatgpt_concerns` but **NOT** in `main_concerns` — likely blind spots

These are the items the team hasn't surfaced as top-priority. Sorted by how much I'd push back on the omission:

### 2a. Should probably move into main_concerns
- **§7 Quotation risk** — main_concerns never mentions pricing. For a B2B reducer site this is the single most common opening question. Without a rule ("don't commit prices, route to sales"), the first leaked discount or wrong MOQ creates a real liability. Cheap to add (one outcome branch + a refusal phrase).
- **§16 Legal liability / disclaimer** — paired with §7 and G4. If a customer buys a reducer the agent recommended and the equipment fails, the conversation transcript becomes evidence. A one-line "preliminary guidance, engineers confirm final selection" disclaimer at outcome time is trivial and substantially de-risks this.
- **§1 Strategic positioning** — not a build concern, but it shifts how the team **sells** this. "Customer-service cost-cut" vs. "overseas inquiry conversion + technical selection assist" is the same product priced very differently. Worth aligning the pitch with whichever framing Kofon's chairman responds to.
- **§8 Multilingual terminology glossary** — `app/i18n.py` is in the tree (untracked) so the team is thinking about it, but main_concerns doesn't flag the **terminology** specifically. Translating "backlash" or "harmonic reducer" wrong is a credibility kill for industrial buyers and is invisible until a German or Spanish customer points it out.
- **§15 Competitor scraping / rate limiting** — there is no abuse detection right now. A competitor running 5k queries to map the product matrix would succeed silently. At minimum needs per-IP rate limiting on `/api/messages`.

### 2b. Worth noting, lower urgency for now
- **§11 ROI metrics design** — the data substrate is there (analytics persistence in Phase 4). Defining the indicators is a conversation with Kofon, not a build task; can wait until real conversations land.
- **§18, §19 Cost & ongoing-maintenance economics** — relevant for the commercial proposal, less so for engineering. Worth pricing into any monthly contract.
- **§20 Internal employee resistance** — change-management; deferred to Kofon's side.
- **§21 Weak initial traffic** — true but external (SEO/promotion is Kofon's problem). Just needs to be in the expectations conversation.
- **§24 Chairman sharp-question prep** — useful as a sales deck, not a backlog item.

### 2c. Already partially or fully handled — main_concerns simply didn't repeat what's done
- **§10 Disconnect from sales process** — largely closed by Phase 4 (pluggable CRM, RFQ payloads, routing matrix). Remaining: real division/inbox config in `routing.yaml`, contact-capture card.
- **§4 Incomplete product data** — actively in progress (`extract_url_batch.py` ran 138 URLs, 84 ok / 54 failed; `extract_pdf.py` is the planned fix). The team knows; it just isn't on a *concerns* list because it's a known workstream.
- **§2 Product understanding depth** — same as §4; ingest pipeline is the lever.

---

## 3. In `main_concerns` but **NOT** in `chatgpt_concerns` — team-only insight

These are concerns ChatGPT didn't surface. They're often the most interesting ones because they come from actually using the product.

- **G2: account system + don't-lose-the-chat-during-signup** — this is a UX continuity concern ChatGPT didn't think of. It's tightly coupled to G1 (handoff): without identity, a human salesperson cannot "take over" a specific session. The constraint that the conversation must survive the signup flow is the hard part. **No backend support today** (no users table, no auth, sessions are checkpointer-keyed by thread_id only).
- **G5 second half: readability vs detail balance (the Neugart comparison)** — ChatGPT's §5 talks about questioning depth; main's G5 is about **output verbosity** — that an answer with all the detail but in a 40-line wall is worse than a partial answer in 5 lines. This is a real difference. Aligns with [[project-kofon-conversational-direction]] — agent feels too form-like; voice and flow need to be separable.
- **G7: customer correctly calibrating agent capabilities** — ChatGPT §12 talks about *trust*; G7 is about the user's *mental model* (under/overestimating what the bot can do). The fix is in onboarding copy and the bot's self-description, not just disclaimers.
- **S3: our own data-usage policy (we analyse conversations)** — ChatGPT only talked about leakage *outward*. Main correctly notes we also need a public policy about how *we* use the captured conversations. Required for GDPR-equivalent and Chinese PIPL.
- **S4: DeepSeek as the egress hole** — ChatGPT's §13 lists leak surfaces but **never names the LLM provider itself** as the most direct egress. Since [[project-china-llm-constraint]] forces DeepSeek + a Chinese embeddings provider, this is the single biggest open question for sensitive-data scope: anything the agent sees, DeepSeek sees. The mitigation isn't technical — it's scope. Don't give the agent capabilities that require sensitive data in the first place. Worth writing this constraint into the system explicitly.
- **"How is our product uncopiable?"** (Misc) — ChatGPT §22 is the close cousin but answers a different question. ChatGPT says: *Kofon's moat is its own KB + selection logic*. Main asks: *what is **our** (the builders') moat?* Those are different commercial questions and the team should be clear which one they care about.

---

## 4. Concrete gaps against current code

Cross-referencing both lists against the Phase 4 backend ([[project-kofon-chatbot]]):

**Plumbing exists, surface missing:**
- Human handoff routing target → no live takeover UX, no account
- `build_custom_config` tool → no structured-fields widget on the addon
- Analytics persistence → no ROI dashboard / metric definitions
- Routing matrix → placeholder division names in `routing.yaml`

**Not yet started:**
- Account / auth model (blocks G1, G2)
- Spec-explainer KB tier ("what is backlash, in 3 lines") — would close G4 properly
- Pricing/quotation refusal rules (chatgpt §7)
- Output-time disclaimer (chatgpt §16, supports G4/G7)
- Prompt-injection detection layer (S2 / §14)
- Public / sales / engineering KB tiering (S1 / §13)
- Rate limiting + abuse detection (§15)
- Capability self-description / onboarding copy (G7)
- Customer priority scoring (G6 / §10)
- Multilingual terminology glossary (§8) — `app/i18n.py` is in flight but glossary scope is unclear
- Stress test / cost ceiling (Misc / §17 / §18)
- Maintenance manual + KB-update templates (M1, M2 / §19)

**Open data/policy questions (need Kofon, not code):**
- What does Kofon classify as sensitive? (S1 — gating decision)
- What is the data-usage policy for analysed conversations? (S3)
- What defines a "high-priority customer"? (G6)
- Which languages are in scope, with what terminology authority? (§8)

---

## 5. Recommendation for what to do with this analysis

Two outputs are useful here:
1. **Updated `main_concerns.md`** — fold in §7 quotation, §16 disclaimer, §1 positioning, §8 glossary, §15 rate limiting, since these aren't currently on the team's radar but are cheap/critical.
2. **A separate "for-Kofon-to-decide" document** — the four open policy questions in §4 above. These block design decisions and they aren't ours to answer.

Implementation order, if/when picking work from the merged list:
- (a) Cheap protective wins first: disclaimer at outcomes, pricing refusal rule, rate limit. A weekend of work; closes three real liability surfaces.
- (b) Then close G1+G2 together (account + handoff) — they're paired and unblock the human-in-the-loop story.
- (c) Then enrich the KB for grounding (resolves G4 and §3 simultaneously, also aligns with [[project-kofon-conversational-direction]] about KB depth being the prerequisite, not an afterthought).
- (d) Only then worry about polish (§11 ROI dashboard, §8 glossary expansion, §15 abuse detection beyond a basic rate limit).

---

## Verification

This is an analysis deliverable, not a code change, so verification is reader-side:
- Spot-check the cross-reference table in §1 by opening both source files side-by-side.
- Sanity-check §4 against `ai-agent-backend/app/agent/nodes/` and the Phase 4 / Phase 5 plan docs.
- Sanity-check the "blind spot" claims in §2 by searching `main_concerns.md` for the keywords (`price`, `quotation`, `disclaimer`, `glossary`, `rate`) — none should appear.
