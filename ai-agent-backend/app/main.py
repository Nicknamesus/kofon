"""FastAPI application entrypoint.

Phase 0 exposed /api/health.
Phase 1 adds /api/tools/{search_products,recommend_categories,solutions}.
Phase 2 will add /api/sessions and /api/flows/{flow}/start.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers.tools import router as tools_router


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
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tools_router)


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
