# Manual test queries

Structured set of queries that exercise every plumbed branch end-to-end.
Each block is self-contained; reset the chat (refresh page or hit "Back to
menu") between blocks unless the block says "continue".

---

## 1. Post-sales: vague-symptom guard → identify → match → fix gate → resolved

| Step | Action | Expected |
|---|---|---|
| 1 | Click **"I have an issue with a product"** | Bot replies asking for what specifically is happening (NOT the candidate list) |
| 2 | Type: `something is wrong with my gearbox` | Bot acknowledges and asks again — still too vague |
| 3 | Type: `oil leak around the input shaft` | Bot presents a problem_match for **"Input shaft oil weep"** + the Yes/No gate |
| 4 | Click **"Yes, fixed"** | Outcome card "Issue resolved" + closing message |
| 5 | Type: `thanks, one more thing — do you sell mounting flanges?` | Bot answers conversationally (post-outcome chat), does NOT dead-end |

## 2. Post-sales: ambiguous shortlist → deterministic pick

| Step | Action | Expected |
|---|---|---|
| 1 | Click **"I have an issue with a product"** | |
| 2 | Type: `my unit is making a strange noise` | Probably falls below the match floor → "Closest matches" card with 2–3 candidates and a "None of these…" button |
| 3 | Click **"Input shaft oil weep"** | Skips vector search, presents that exact problem + solution + Yes/No gate |
| 4 | Click **"No, still broken"** | Routes to outcome_human handoff card |

## 3. Post-sales: "None of these — describe more" path

| Step | Action | Expected |
|---|---|---|
| 1 | Click **"I have an issue with a product"** | |
| 2 | Type: `something weird is happening` | Bot asks for detail (vague guard) |
| 3 | Type: `random vibrations` | Likely ambiguous shortlist |
| 4 | Click **"None of these — let me describe more"** | Bot asks for more detail |
| 5 | Type: `housing is running really hot under continuous load` | Should match **"Housing temperature alarm under continuous duty"** with confidence + Yes/No |

## 4. Post-sales: total mismatch → human handoff

| Step | Action | Expected |
|---|---|---|
| 1 | Click **"I have an issue with a product"** | |
| 2 | Type: `the LCD screen on the front panel won't turn on` | No KB match → handoff card |
| 3 | Type: `is there anything I can try in the meantime?` | Post-outcome chat keeps responding |

## 5. Pre-sales (no info)

| Step | Action | Expected |
|---|---|---|
| 1 | Click **"Help me figure out what I need"** (or the equivalent presales chip) | Bot asks about industry / application |
| 2 | Type: `robotics, specifically AGV wheel drives` | Bot continues narrowing or hands off to guide.find |
| 3 | Type: `around 100 Nm continuous, frame size 90 mm` | Bot presents matching products card (should include PG090-10-HP) |
| 4 | Click **"Yes"** on the happy gate | Sales handoff outcome |

## 6. Guide (knows roughly what)

| Step | Action | Expected |
|---|---|---|
| 1 | Click **"Show me products / I know what I need"** | Bot greets and asks for specs/filters |
| 2 | Type: `I need a planetary gearbox, frame 140, ratio 50:1` | Product results card with PG140-50-HT |
| 3 | Click **"No"** on happy gate | Human handoff |

## 7. Guide.customize sub-flow

Trigger via the utility chip mapped to `subflow=customize`. Then:

| Step | Action | Expected |
|---|---|---|
| 1 | Click the **Custom build** utility | Customize node runs, asks for spec choices |
| 2 | Provide: `family caesarplanetary, ratio 12, frame 90, low backlash` | Bot offers a custom config + closest stock SKU |

## 8. Other / off-topic reclassification

| Step | Action | Expected |
|---|---|---|
| 1 | Click **"Other"** (or "I have a question") | |
| 2 | Type: `what are your office hours?` | Either reclassified into a friendly answer or routed to human handoff |
| 3 | Type: `actually, I'm looking for a 90 mm gearbox` | Reclassify should reroute into the guide flow same turn |

## 9. Composer-level sanity

| Test | Expected |
|---|---|
| Click the up-arrow send button with the input empty | Button is dimmed grey + shakes briefly, input gets focus, nothing sent |
| Type a single character | Send button turns primary blue |
| Press Enter in the input with text | Sends the message |
| Click the chevron-left button in the header (top-right area) | Returns to the welcome menu |

## 10. Post-outcome continuation regression

Run flow #4 (handoff) to completion, then:

| Step | Action | Expected |
|---|---|---|
| 1 | Type: `also, can you confirm my serial number is on file?` | Friendly LLM reply that says it's noted for the engineer — no "this conversation already wrapped up" message |
| 2 | Type 3–4 more arbitrary follow-ups | Each gets a short, on-topic reply |

---

If anything in flow 1, 2, or 3 still mis-fires, that's KB / embeddings-floor
territory, not plumbing.
