# Phase 0 — Summary

The foundation. Nothing user-facing yet. The point of Phase 0 is to prove the
plumbing works before we add anything complex.

---

## In plain terms

We need a backend service that will eventually power the chatbot. That service
needs three moving parts to talk to each other reliably:

1. **A web server** (the thing the chatbot widget will talk to over HTTP)
2. **A database** (where conversations, products, and knowledge will live)
3. **A migration tool** (so we can change the database structure safely over
   time without losing data)

In Phase 0 we set up all three, wire them together, and add **one tiny endpoint
called `/api/health`** whose only job is to answer "yes, everything is working."

There are no features yet. No chatbot logic, no products in the database, no
conversation storage. Phase 0 is the equivalent of laying the foundation of a
house — boring on its own, but everything else needs it.

### Why bother with a "boring" first phase?

Because most projects break in the seams between systems, not inside them.
Setting up the connections first, with nothing else in the way, means later
phases get to focus on *features* without simultaneously debugging
"can the web server reach the database at all?" The health endpoint becomes
our smoke test forever after — every future change can be checked against it
in one line.

### What "it works" means

```powershell
docker compose up -d     # start the database
uvicorn app.main:app     # start the web server
curl http://127.0.0.1:8000/api/health
```

returns:

```json
{"status": "ok", "db": "ok", "env": "development"}
```

If you see that, the foundation is sound. If not, we know exactly which piece
is broken before we add complexity on top.

---

## What's in the folder

```
ai-agent-backend/
├── .env.example             # template for environment variables
├── .gitignore
├── docker-compose.yml       # spins up Postgres (with pgvector) locally
├── pyproject.toml           # Python dependencies
├── alembic.ini              # migration tool config
├── alembic/
│   ├── env.py               # how migrations connect to the DB
│   ├── script.py.mako       # template for new migrations
│   └── versions/            # actual migration files (empty for now)
└── app/
    ├── __init__.py          # marks app/ as a Python package
    ├── config.py            # reads .env into a typed Settings object
    ├── db.py                # database connection + session machinery
    └── main.py              # the FastAPI app + /api/health
```

---

## How to run it

From inside `ai-agent-backend/`:

```powershell
# 1. Copy environment template
copy .env.example .env

# 2. Start the database (first time pulls ~80 MB image)
docker compose up -d

# 3. Set up Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

# 4. Apply migrations (none yet, but proves wiring)
alembic upgrade head

# 5. Start the API
uvicorn app.main:app --reload --port 8000
```

Then in another shell:

```powershell
curl http://127.0.0.1:8000/api/health
```

To stop:

```powershell
docker compose down          # stops Postgres, keeps your data
docker compose down -v       # also wipes the database
```

---

# Technical deep-dive

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Developer machine                       │
│                                                              │
│   ┌────────────────────┐         ┌───────────────────────┐   │
│   │   FastAPI process  │         │  Docker container     │   │
│   │   (uvicorn)        │         │                       │   │
│   │                    │         │  Postgres 16 +        │   │
│   │   app.main:app     │ ◀─────▶ │  pgvector             │   │
│   │   ├─ /api/health   │  TCP    │  (port 5432)          │   │
│   │   └─ lifespan probe│  asyncpg│                       │   │
│   │                    │         │  Volume:              │   │
│   │   reads .env via   │         │  kofon_pg_data        │   │
│   │   app.config       │         │                       │   │
│   └────────────────────┘         └───────────────────────┘   │
│                                                              │
│   ┌────────────────────┐                                     │
│   │ Alembic CLI        │                                     │
│   │ alembic upgrade    │ ──────────────────────▶ same DB     │
│   │ head               │                                     │
│   │                    │                                     │
│   │ uses app.db.Base   │                                     │
│   │ metadata to detect │                                     │
│   │ schema drift       │                                     │
│   └────────────────────┘                                     │
└──────────────────────────────────────────────────────────────┘
```

## Stack and version pins

| Component         | Version         | Why                                                                 |
| ----------------- | --------------- | ------------------------------------------------------------------- |
| Python            | ≥ 3.11 (3.14 verified) | Async syntax + modern typing. 3.14 has working asyncpg wheels.    |
| FastAPI           | 0.136           | Async-native HTTP framework. Pydantic v2 first-class.               |
| uvicorn[standard] | 0.47            | ASGI server with watchfiles for `--reload`, httptools for speed.    |
| SQLAlchemy[asyncio] | 2.0.49        | The ORM, in its 2.x style with native async sessions.               |
| asyncpg           | 0.31            | The fastest Postgres driver for Python — used by both app and Alembic. |
| Alembic           | 1.18            | DB migration tool that reads SQLAlchemy metadata.                   |
| Pydantic          | 2.13            | Validation + serialization. Used by FastAPI for requests/responses. |
| pydantic-settings | 2.14            | Loads `.env` files into typed Settings objects.                     |
| Postgres          | 16              | Latest stable. The `pgvector/pgvector:pg16` image has the extension preinstalled. |
| pgvector extension | preinstalled   | Will hold semantic embeddings for product/problem search in Phase 4. Not used yet but ready. |

## File-by-file walkthrough

### `docker-compose.yml`

One service: a Postgres 16 container with pgvector preinstalled.

- **Image**: `pgvector/pgvector:pg16`. Plain Postgres + the pgvector extension already compiled in. We won't use vectors until Phase 4, but choosing this image now means we don't have to swap and reseed later.
- **Healthcheck**: `pg_isready` every 5s. Lets `docker compose` know when the
  DB is actually ready to accept connections (the container starts faster than
  Postgres itself does).
- **Named volume** `kofon_pg_data` mounted at `/var/lib/postgresql/data`.
  Data survives container restarts; only `docker compose down -v` wipes it.
- **Env interpolation**: `${POSTGRES_USER:-kofon}` reads from the shell's
  environment (or `.env`), with a default. Lets a single compose file work
  for local / CI / staging without edits.

### `.env.example` and `app/config.py`

`.env.example` is a checked-in template; the real `.env` is gitignored.

`app/config.py` defines a `Settings` class via `pydantic-settings`. It reads
`.env`, validates types, and gives the app a single typed object to consume:

```python
class Settings(BaseSettings):
    postgres_user: str = "kofon"
    postgres_password: str = "kofon_dev_password"
    ...
    database_url: str | None = None

    @computed_field
    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
```

Two notable details:

1. **Composed URL with override**. The DB URL is built from parts (`postgres_user`,
   `postgres_host`, etc.) by default, but a single `DATABASE_URL` env var
   overrides everything. This matters because cloud providers (Render, Neon,
   Supabase) hand you a full URL — letting that override the parts is a
   one-variable production config.
2. **The `postgresql+asyncpg://` scheme** tells SQLAlchemy to use the asyncpg
   driver. Without `+asyncpg`, SQLAlchemy would try the synchronous psycopg2
   driver and fail because we asked for an async engine.

`get_settings()` is `@lru_cache`-d so the env is read once, not on every request.

### `app/db.py`

The database connection layer. Three things live here:

```python
class Base(DeclarativeBase): ...

engine = create_async_engine(_settings.effective_database_url, ..., pool_pre_ping=True)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- **`Base`** is the shared declarative class that Phase 1 models will inherit
  from. By keeping it in `app/db.py`, both the app and Alembic's `env.py`
  import the same metadata, and migrations stay in sync with the ORM.
- **`engine`** is created once per process. `pool_pre_ping=True` issues a
  cheap `SELECT 1` before handing out a pooled connection — catches stale
  connections (after Postgres restart, network blip, etc.) and reconnects
  silently instead of failing the first request after a hiccup.
- **`SessionLocal`** is an `async_sessionmaker` (the 2.x replacement for the
  old `sessionmaker`). `expire_on_commit=False` is the convention for async
  code so attributes can be safely read after commit without triggering an
  implicit reload (which would otherwise need a running session).
- **`get_session`** is the FastAPI dependency we'll use from Phase 1
  onwards: `async def my_route(session: AsyncSession = Depends(get_session))`.
  The `async with` block ensures the session is closed even if an exception
  propagates out of the route.

### `app/main.py`

The FastAPI app itself:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))   # fail fast on a bad DB config
    yield
    await engine.dispose()                     # release pool on shutdown

app = FastAPI(title="Kofon Chatbot Backend", version="0.0.0", lifespan=lifespan)

@app.get("/api/health")
async def health() -> dict[str, str]:
    ...
```

- **Lifespan context manager**: FastAPI runs this once at startup, once at
  shutdown. The startup probe forces a real connection at boot. If the DB is
  misconfigured, the server crashes immediately with a clear error rather than
  letting routes return 500s indefinitely. The shutdown half disposes of the
  connection pool cleanly so we don't leak connections during reloads.
- **`/api/health`**: opens a connection, runs `SELECT 1`, and reports the
  outcome. Crucially, this *runs the query* — it doesn't trust the engine
  cache. A passing health check means a live, working DB roundtrip happened.
- **Exception handling**: a bare `try/except` returns a structured error
  description in the response body. This is intentional for a health check —
  monitoring systems can read the JSON and tell which part is broken
  (`db: error: ConnectionRefusedError`) without parsing logs.

### `alembic.ini` and `alembic/env.py`

`alembic.ini` is Alembic's main config. Most of it is logging boilerplate.
The notable bits:

- `script_location = alembic` — where migration files live (next to this ini).
- `sqlalchemy.url =` is **empty**. The DB URL is set at runtime by `env.py`
  reading from our app config. This means migrations and the app are
  guaranteed to talk to the same DB without two-place duplication.

`alembic/env.py` is where the async magic happens. The standard Alembic
template assumes a sync driver; ours overrides it for async:

```python
async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

- **`async_engine_from_config`** builds an async engine from the same config
  section the sync version would use, but binds asyncpg under the hood.
- **`run_sync(do_run_migrations)`** is the bridge. Alembic's migration runner
  is fundamentally synchronous — it doesn't know about `await`. The
  `connection.run_sync()` call hands the underlying connection back as if it
  were sync, so Alembic's machinery operates as it normally does, while the
  outer code stays in an event loop.
- **`NullPool`** is used for migrations because they're short-lived
  processes — no point keeping a connection pool around for a one-shot
  `alembic upgrade head` run.

The `from app.db import Base  # noqa: F401` line is the load-bearing piece for
Phase 1: once models are added, importing `Base` here makes `Base.metadata`
visible to Alembic, which is what `--autogenerate` reads to detect schema drift.

## The `/api/health` request, traced

What happens when you `curl http://127.0.0.1:8000/api/health`:

1. **Uvicorn** receives the TCP connection, parses the HTTP request, hands it
   to FastAPI via the ASGI protocol.
2. **FastAPI** matches the path `/api/health` to the `health()` coroutine.
3. **`health()`** runs on the event loop. It calls `engine.connect()`, which
   asks the connection pool for a connection.
4. The pool **issues a `SELECT 1`** to verify the connection is alive
   (`pool_pre_ping`). If the connection is dead, it transparently reconnects.
5. The route's **own `SELECT 1`** runs via asyncpg → over TCP → to Postgres,
   which returns `1`.
6. The connection returns to the pool. The route returns
   `{"status": "ok", "db": "ok", "env": "development"}`.
7. FastAPI serializes the dict to JSON, sets `Content-Type: application/json`,
   and Uvicorn writes it back to the socket.

Total latency on a warm pool with local Postgres: typically 1–3 ms.

## Key technical decisions

### Async everywhere, with a single driver

We use `asyncpg` for both the app and migrations. The alternative pattern —
asyncpg in the app, psycopg2 in Alembic — is common but creates two driver
versions to keep in sync, two sets of edge cases, two install paths.
Going single-driver-async simplifies setup at the cost of slightly more
involved `env.py` config.

### `pool_pre_ping` over reconnect-on-error

`pool_pre_ping=True` pays a tiny latency cost per request in exchange for
not having to write reconnect logic anywhere else. Without it, a Postgres
restart or network hiccup leaves stale connections in the pool that fail
the next request that picks them up.

### Lifespan probe at startup

Crashing at boot on a bad DB config is preferable to crashing on first
request — it makes the failure mode visible to whatever launches the
process (systemd, Kubernetes, your terminal) instead of being hidden in
500 responses.

### `expire_on_commit=False` in the session factory

The async-SQLAlchemy idiom. With the default `expire_on_commit=True`, reading
an attribute on an ORM object after commit triggers a refresh — which in
async code requires re-entering the session context. Disabling expiration
sidesteps a class of subtle bugs.

### pgvector image now, even though Phase 0 doesn't use it

Cost: zero (same Postgres, just an extension preinstalled). Benefit: when
Phase 4 (embeddings) lands, we don't have to migrate the existing data to a
new image. We just `CREATE EXTENSION vector;` in a future migration and use it.

### `app/__init__.py` is empty on purpose

Phase 0 doesn't need to re-export anything from the `app` package, so the
init file stays empty. Future phases may add public re-exports (e.g.,
`from app.config import get_settings`) once enough modules are referenced
from multiple call sites for that to be useful.

## What we verified at the end of Phase 0

Concretely, the smoke test we ran:

1. **Image pulls correctly** — `docker compose up -d` succeeds.
2. **Container becomes healthy** — `docker compose ps` shows
   `Up (healthy)`. This means `pg_isready` succeeds, which means Postgres
   is accepting connections.
3. **Dependencies install on Python 3.14** — `pip install -e .` succeeds
   with no missing wheels (asyncpg 0.31 has 3.14 wheels; the others are
   pure Python or have very broad wheel matrices).
4. **Alembic can connect** — `alembic upgrade head` logs
   "Context impl PostgresqlImpl. Will assume transactional DDL." That output
   is Alembic confirming it talked to Postgres and identified the dialect.
5. **The API starts** — `uvicorn app.main:app` runs without raising during
   the lifespan probe. (If the DB were unreachable, the lifespan probe's
   `SELECT 1` would have thrown.)
6. **The health endpoint returns 200 with the expected body** — both
   `status` and `db` are `"ok"`, confirming the full request → query →
   response chain is working.

## What is explicitly NOT in Phase 0

So expectations are clear:

- **No data model.** No tables, no ORM models. `Base.metadata` is empty.
- **No real migrations.** `alembic/versions/` is empty. Phase 1 adds the
  first migration via `alembic revision --autogenerate -m "initial schema"`.
- **No domain logic.** No products, no problem types, no conversations, no
  agent.
- **No LLM integration.** Nothing in this phase calls any model.
- **No authentication.** `/api/health` is open. Production auth lands when
  we have endpoints worth protecting.
- **No tests.** A pytest test for `/api/health` is a natural Phase 1
  addition — the dev extras already include `pytest`, `pytest-asyncio`,
  and `httpx` so it's a single file away.

## How Phase 0 sets up the next 5 phases

| Future phase | What Phase 0 already enables                                                                          |
| ------------ | ----------------------------------------------------------------------------------------------------- |
| Phase 1 — content schema + seed loader + read-only tools | `Base` is imported by `env.py`, so models added to `app/models/` get autogenerated migrations for free. |
| Phase 2 — LangGraph router + first flows | FastAPI is already async-ready. Adding a `POST /api/flows/{flow}/start` endpoint that streams SSE is a few-line addition. |
| Phase 3 — postsales + KB embeddings | The pgvector extension is in the running container; we just enable it via migration. |
| Phase 4 — human handoff + RFQ | The async DB session can write to `conversations` and call external CRMs in parallel with no rework. |
| Phase 5 — streaming, multilingual, observability | Lifespan hooks already exist for adding LangSmith init, metrics collectors, etc. |

The foundation is intentionally minimal and intentionally complete — every
piece a future phase needs is wired, but no piece is built ahead of its phase.
