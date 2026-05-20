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

## 11. Phase 4 — Side effects (CRM + email + RFQ)

Phase 4 wired the outcome nodes to a pluggable CRM (`CRM_PROVIDER`,
defaults to `log`), a pluggable email provider (`MAIL_PROVIDER`,
defaults to `log`), and a routing matrix. The user-visible behaviour
hasn't changed — the same outcome cards render — but the back-end now
writes audit rows. Verification is SQL-side.

Run the **automated check** first; the flows below verify the same
things end-to-end through the widget.

### 11.0 Automated smoke

From `ai-agent-backend/`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.agent.smoke_4
```

Expected: three scenarios print (`sell`, `handoff`, `resolved`) and
the script exits 0. Failures will assert with the row counts that
were missing.

### 11.1 outcome_sell → Rfq + audit + division email

Run flow **#6** (Guide-Find with happy gate "Yes"). Then in psql:

```sql
-- The newest conversation should have an outcome=sell + a linked Rfq
SELECT id, outcome, division_code, rfq_id, ticket_id
FROM conversations
ORDER BY started_at DESC LIMIT 1;

-- The Rfq row carries the CRM-agnostic payload
SELECT id, sku, product_family, division_code, crm_provider, crm_record_id, status
FROM rfqs
ORDER BY created_at DESC LIMIT 1;

-- An audit row was written for the CRM call (create_lead)
SELECT provider, operation, status, error
FROM crm_calls
WHERE conversation_id = (SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1);

-- And one for the division-notify email
SELECT provider, to_address, subject, kind, status
FROM email_calls
WHERE conversation_id = (SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1);
```

Expected:
| Check | Expected value |
|---|---|
| `conversations.outcome` | `sell` |
| `conversations.division_code` | `planetary` (caesarplanetary family) |
| `conversations.rfq_id` | matches `rfqs.id` of the new row |
| `rfqs.crm_provider` | `log` (or whatever `CRM_PROVIDER` is set to) |
| `rfqs.crm_record_id` | non-null synthetic id (`lead-…` from `log`) |
| `crm_calls` | one row, `operation='create_lead'`, `status='ok'` |
| `email_calls` | one row, `kind='rfq_notify'`, `to_address='planetary-sales@…'`, `status='ok'` |

### 11.2 outcome_human (low-confidence fallback) → Ticket

Run flow **#4** (total-mismatch handoff). In psql:

```sql
SELECT id, outcome, division_code, ticket_id
FROM conversations
ORDER BY started_at DESC LIMIT 1;

SELECT id, reason, division_code, crm_provider, crm_record_id, status
FROM tickets
ORDER BY created_at DESC LIMIT 1;

SELECT provider, operation, status
FROM crm_calls
WHERE conversation_id = (SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1);

SELECT to_address, kind, status
FROM email_calls
WHERE conversation_id = (SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1);
```

Expected:
| Check | Expected value |
|---|---|
| `conversations.outcome` | `human_handoff` |
| `conversations.ticket_id` | matches `tickets.id` as a string |
| `tickets.reason` | `low_confidence_kb_match` (postsales miss) or `user_requested` |
| `crm_calls.operation` | `create_ticket` |
| `email_calls.kind` | `handoff_notify` |

### 11.3 outcome_human (fix didn't work) → priority bumps to high

Run flow **#2** through to "**No, still broken**". In the `tickets`
row, `payload->>'priority'` should be `'high'` (vs `'normal'` for
other handoff reasons), and `reason` should be `fix_didnt_work`.

```sql
SELECT reason, payload->>'priority' AS priority
FROM tickets
ORDER BY created_at DESC LIMIT 1;
```

### 11.4 outcome_resolved → log_activity only (no CRM record creation)

Run flow **#1** through to "**Yes, fixed**". In psql:

```sql
SELECT outcome FROM conversations ORDER BY started_at DESC LIMIT 1;
-- → 'resolved'

SELECT operation, status FROM crm_calls
WHERE conversation_id = (SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1);
-- → one row, operation='log_activity', status='ok'

SELECT COUNT(*) FROM rfqs WHERE conversation_id = (
  SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1
);
-- → 0 (no Rfq for resolved outcomes)

SELECT COUNT(*) FROM tickets WHERE conversation_id = (
  SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1
);
-- → 0 (no ticket either)
```

### 11.5 Analytics persistence — `conversations` + `messages`

After any flow finishes (try flow #6), every user turn and every bot
event should have a row in `messages`.

```sql
WITH last_conv AS (
  SELECT id FROM conversations ORDER BY started_at DESC LIMIT 1
)
SELECT role, content_type, node, content->>'text' AS text_preview
FROM messages
WHERE conversation_id = (SELECT id FROM last_conv)
ORDER BY created_at;
```

Expected:
- Alternating `user` / `bot` rows in order.
- `user.content_type`: `text` for typed input, `gate_choice` for the
  Yes/No, `chip` for the welcome chip click.
- `bot.content_type`: `text` for prose, `card` for product results,
  gates, outcome cards.
- `bot.node` ∈ {`entry_router`, `guide.find`, `guide.happy_gate`,
  `outcome_sell`, …} so funnel queries work.

Also check the slim state snapshot:

```sql
SELECT current_node, language, state->'flow' AS flow, state->'outcome' AS outcome
FROM conversations ORDER BY started_at DESC LIMIT 1;
```

`state` should be a slim mirror of the final agent state with
`messages` stripped.

### 11.6 Routing matrix sanity

Quick lookup that `(main_type, family)` → division resolves correctly
without going through the chat:

```powershell
.\.venv\Scripts\Activate.ps1
python -c "from app.sideeffects.routing import resolve_division; print(resolve_division('guide','caesarplanetary')); print(resolve_division('postsales','rollsate')); print(resolve_division('other','unknown'))"
```

Expected:
- `guide`+`caesarplanetary` → `planetary`
- `postsales`+`rollsate` → `roller_screw`
- `other`+`unknown` → `applications` (fallback)

### 11.7 Provider swap — log → Zoho (manual / staging only)

Don't run against production Zoho. With sandbox creds:

```powershell
# .env
CRM_PROVIDER=zoho
ZOHO_CLIENT_ID=…
ZOHO_CLIENT_SECRET=…
ZOHO_REFRESH_TOKEN=…
ZOHO_REGION=cn          # or us / eu / in / au / jp
```

Restart the API. Run flow #6 (sell). Expected:
- `rfqs.crm_provider` = `'zoho'`
- `rfqs.crm_record_id` = a real Zoho Deal id (numeric string)
- `crm_calls.response` contains Zoho's `{data:[{details:{id:…}}]}`
- Deal appears in Zoho CRM under the configured user's Deals module
  with Stage = Qualification

If the call fails (bad creds / wrong region), `crm_calls.status` is
`'error'`, `error` column has the exception trace, **and the user
still sees the outcome card** (soft-fail per
`SIDEEFFECTS_SOFT_FAIL=true`).

### 11.8 Soft-fail behaviour

Temporarily break the provider (e.g. point `ZOHO_API_URL` to
`https://invalid.example`). Run flow #6:

| Check | Expected |
|---|---|
| Widget UI | Same "Connecting you with sales" card |
| `rfqs` row | Still inserted (internal source of truth) |
| `crm_calls.status` | `error` with non-null `error` column |
| `email_calls.status` | `ok` (email send is independent of CRM) |
| `conversations.outcome` | `sell` (set regardless of provider failure) |

Set `SIDEEFFECTS_SOFT_FAIL=false` to flip to hard-fail — the SSE
stream will surface the error. Don't ship that to demo.

---

If anything in flow 1, 2, or 3 still mis-fires, that's KB / embeddings-floor
territory, not plumbing.
