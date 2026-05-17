# Kofon Chatbot Backend

Phase 0 skeleton from `BACKEND_PLAN.md`:

- **FastAPI** app exposing `/api/health`
- **Postgres 16 + pgvector** via Docker Compose
- **Async SQLAlchemy 2** engine + session factory
- **Alembic** wired async, ready for Phase 1 migrations

No models, no agent, no flows yet. Just enough so the stack comes up and
migrations run.

## Prerequisites

- Python 3.11 or newer (you have 3.14 — fine, but if any wheel is missing, downgrade to 3.12)
- Docker Desktop with `docker compose` v2

## First-time setup

From this folder:

```powershell
# 1. Configure env
copy .env.example .env       # PowerShell  (or `cp` on bash)

# 2. Start Postgres
docker compose up -d
docker compose ps            # verify "healthy"

# 3. Create + activate a venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1 # PowerShell
# source .venv/bin/activate  # bash

# 4. Install deps (editable)
pip install -e .

# 5. Run Alembic (no migrations yet, but proves wiring)
alembic upgrade head

# 6. Start the API
uvicorn app.main:app --reload --port 8000
```

Then in another shell:

```powershell
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status": "ok", "db": "ok", "env": "development"}
```

## Tearing down

```powershell
docker compose down          # stop, keep data
docker compose down -v       # stop and wipe the volume
```

## Layout

```
ai-agent-backend/
├── .env.example             # template — copy to .env
├── docker-compose.yml       # local Postgres (with pgvector)
├── pyproject.toml           # deps + tooling config
├── alembic.ini              # Alembic config; URL injected from app.config
├── alembic/
│   ├── env.py               # async-aware migration env
│   ├── script.py.mako       # migration template
│   └── versions/            # migrations land here (empty in Phase 0)
└── app/
    ├── __init__.py
    ├── config.py            # pydantic-settings — reads .env
    ├── db.py                # async engine, session factory, Base
    └── main.py              # FastAPI app + /api/health
```

## Adding the first migration (Phase 1 preview)

When Phase 1 lands, models will be added under `app/models/` and imported in
`alembic/env.py`. Then:

```powershell
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## Common issues

- **`asyncpg` install fails on Python 3.14** — downgrade to 3.12 (`pyenv install 3.12 && pyenv local 3.12`) or wait for a wheel release. The rest of the stack is fine on 3.14.
- **`alembic upgrade head` says nothing happens** — that's correct in Phase 0. Alembic prints nothing when there are zero migrations.
- **Health check returns `db: error: ...`** — Postgres isn't reachable. Confirm `docker compose ps` shows `kofon-chatbot-postgres` as `healthy`.
- **Port 5432 already in use** — change `POSTGRES_PORT` in `.env` (and the corresponding side of the `ports:` mapping is already templated).

## What's next

`BACKEND_PLAN.md` (in `ai-agent-addon/`) lays out Phases 1–5:

- **Phase 1** — content tables + seed loader + read-only tools (`search_products`, etc.)
- **Phase 2** — LangGraph router + the `presales` + `guide.find` flows + outcome nodes
- **Phase 3** — `postsales` flow + KB embeddings
- **Phase 4** — human handoff to a real channel + RFQ submission
- **Phase 5** — streaming polish, multilingual content, observability
