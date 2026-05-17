"""FastAPI application entrypoint.

Phase 0 only exposes /api/health. Future phases add /api/sessions,
/api/flows/{flow}/start, etc.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import get_settings
from app.db import engine


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
    version="0.0.0",
    lifespan=lifespan,
)


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
