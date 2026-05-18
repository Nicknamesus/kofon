"""Seed loader package.

Reads YAML/CSV under `ai-agent-backend/seed/` and upserts into Postgres
by natural key. Idempotent — safe to re-run on every deploy.

Entry point:

    python -m app.seed.load
"""
