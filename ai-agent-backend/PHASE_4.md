# Phase 4 — Summary

Phase 4 wires the agent's terminal outcomes to real side effects: a
**CRM** (lead / ticket creation), **email** (division notification), and
shaped **analytics rows** in `conversations` / `messages`. Through Phase
3, every outcome was a no-op — `outcome_sell` rendered a card and that
was it. Now it produces an RFQ in the CRM, notifies the right division,
and persists a row sales can query.

The CRM is intentionally **pluggable** behind a small `CrmProvider`
Protocol. Zoho CRM is the default real adapter, but swapping to
Salesforce or a Chinese-native CRM is a single env var (`CRM_PROVIDER`)
and a new file under `app/crm/`. Outcome nodes never see the provider.

---

## In plain terms

- A confirmed sale (`outcome_sell`) now creates a **Deal** in Zoho (or
  whatever CRM is wired), notifies the receiving division by email, and
  stores the internal RFQ for audit.
- A handoff (`outcome_human`) creates a **Case** in the CRM with the
  full transcript + symptom + reason, with priority bumped to `high`
  when a curated fix didn't work.
- A resolved issue (`outcome_resolved`) logs an **activity** so support
  has a record of what the bot resolved without human intervention.
- Every turn now also writes to `conversations` / `messages` so funnel
  / outcome analytics queries actually return data.

---

## What was built

### CRM provider
- `app/crm/__init__.py` — `CrmProvider` Protocol + factory, payload
  dataclasses (`LeadPayload`, `TicketPayload`, `ActivityPayload`,
  `CrmResult`). Three operations: `create_lead`, `create_ticket`,
  `log_activity`.
- `app/crm/log.py` — default. Returns synthetic record ids; the
  orchestrator writes a `crm_calls` audit row alongside, so the
  complete history is visible in the DB even with no real provider.
- `app/crm/zoho.py` — Zoho v6 adapter. OAuth refresh-token grant,
  per-region endpoints (us / eu / in / au / jp / **cn**), Deals / Cases
  / Tasks mapping, in-process token cache, single retry on 401.

### Email provider
- `app/mail/__init__.py` — `EmailProvider` Protocol + factory.
- `app/mail/log.py` — default. Audit-only.
- `app/mail/aliyun.py` — Aliyun DirectMail adapter (signed POP request,
  no SDK dependency).

### Routing + RFQ payload
- `app/sideeffects/routing.yaml` — `(main_type, product_family)` →
  division mapping. Six pre-seeded divisions; edit names + inboxes
  before going live.
- `app/sideeffects/routing.py` — loader + resolver. Falls back to a
  static default if the YAML is absent.
- `app/sideeffects/rfq.py` — builds `LeadPayload` / `TicketPayload`
  from agent state. The only place that knows the shape of
  `state.slots`; CRM adapters take the dataclass and never look at
  state directly.

### Orchestration
- `app/sideeffects/handlers.py` — `handle_sell`, `handle_human_handoff`,
  `handle_resolved`. Each one resolves division → builds payload →
  inserts internal `Rfq` / `Ticket` → calls the CRM → records the
  attempt in `crm_calls` → sends notification email → records in
  `email_calls` → patches the conversations row.
- Errors are swallowed by default (`SIDEEFFECTS_SOFT_FAIL=true`) so a
  provider outage never breaks the user-facing flow. The audit rows
  hold the failure for re-drive later.

### Analytics persistence
- `app/persistence.py` — `upsert_conversation`, `append_user_message`,
  `append_bot_text`, `append_bot_card`, `update_conversation_state`.
  Called by the SSE router on every turn.
- `app/routers/agent.py` — wires persistence in. Upserts the
  conversation, persists the user turn, then streams + persists every
  AI message and card.

### Schema
- `f2a8c91d4e30_phase_4_side_effects.py` — adds `rfqs`, `tickets`,
  `crm_calls`, `email_calls`. Conversations gains `rfq_id` (FK) and
  `division_code`.

### Smoke
- `app/agent/smoke_4.py` — runs sell / handoff / resolved scenarios
  end-to-end with `CRM_PROVIDER=log` and asserts that the audit rows
  + `conversations.rfq_id` / `ticket_id` columns are populated.

---

## Resume command

From `ai-agent-backend/`:

```powershell
docker compose up -d
.\.venv\Scripts\Activate.ps1
alembic upgrade head                          # advances to f2a8c91d4e30
python -m app.agent.setup_checkpointer        # idempotent
python -m app.seed.load                       # idempotent
python -m app.agent.smoke_4                   # Phase 4 smoke
python -m app.serve --port 8001               # NOT `uvicorn ...` on Windows
```

Switch CRM later by setting `CRM_PROVIDER=zoho` and the four `ZOHO_*`
vars (see `.env.example`). No code changes.

---

## Open items

- **Contact capture** (email / company) still isn't part of any Phase 3
  flow — `LeadPayload.contact_email` defaults to `None` and the CRM
  record is created in an "unknown contact" shape. A Phase 4.1 sub-step
  should add a small contact-capture card in `outcome_sell` /
  `outcome_human` before the side effect fires.
- **Datasheet email** (`send_datasheet` tool) isn't wired yet; the
  email provider is in place, but no node currently calls it. Trivial
  follow-up.
- **Routing matrix content** is placeholder — the division names and
  inbox addresses in `routing.yaml` must be confirmed with Kofon's
  internal org chart before go-live.
- **Soft-fail default** is correct for the demo but should be flipped
  off once Phase 5 alerting is in place.
