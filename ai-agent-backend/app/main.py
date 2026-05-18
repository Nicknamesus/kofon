"""FastAPI application entrypoint.

Phase 0 exposed /api/health.
Phase 1 adds /api/tools/{search_products,recommend_categories,solutions}.
Phase 2 adds /api/sessions and /api/messages (SSE-streamed).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers.agent import router as agent_router
from app.routers.tools import router as tools_router
from app.runtime import install_async_event_loop_policy

# Must happen before uvicorn creates its event loop — psycopg async (used by
# the LangGraph checkpointer) is incompatible with Windows' ProactorEventLoop.
install_async_event_loop_policy()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Startup: probe the DB so we fail fast if it's unreachable.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Kofon Chatbot Backend",
    version="0.2.0",
    lifespan=lifespan,
)

# Dev CORS: the widget will be served via `python -m http.server` on a
# different port than the API, so we need to allow cross-origin XHR. In
# prod, replace this with an explicit allowlist of customer domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools_router)
app.include_router(agent_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Returns ok if the app is alive and Postgres responds to SELECT 1."""
    settings = get_settings()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc.__class__.__name__}"
    return {
        "status": "ok",
        "db": db_status,
        "env": settings.app_env,
    }
