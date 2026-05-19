"""phase 3 embeddings

Adds `product_embeddings` and `problem_embeddings` tables with pgvector
columns. The pgvector extension itself is preinstalled in the dev image
(`pgvector/pgvector:pg16`) — we just `CREATE EXTENSION IF NOT EXISTS`.

Embedding dimension is 1024 so the schema works with both production
providers (BGE-M3 native; DashScope text-embedding-v3 with
`dimension=1024`). See `app/embeddings.py`.

Indexes use HNSW rather than ivfflat. ivfflat needs to be trained on
enough vectors to form meaningful centroids; with the small seed sets
we ship in Phase 3, an ivfflat index produces a degenerate plan that
silently returns zero rows for `ORDER BY embedding <=> ... LIMIT N`.
HNSW has no training prerequisite and degrades gracefully on tiny
tables.

Revision ID: d4e2a9f5c10b
Revises: c96b3d3b7fda
Create Date: 2026-05-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e2a9f5c10b"
down_revision: Union[str, None] = "c96b3d3b7fda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "product_embeddings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type", "source_id", "text_hash",
            name="uq_product_embeddings_source_hash",
        ),
    )
    # ivfflat needs training rows; for tiny seed sets a plain index works
    # too. Cosine ops match the L2-normalised vectors our providers emit.
    op.execute(
        "CREATE INDEX ix_product_embeddings_embedding "
        "ON product_embeddings USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "problem_embeddings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("problem_type_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.ForeignKeyConstraint(
            ["problem_type_id"], ["problem_types.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "problem_type_id", "text_hash",
            name="uq_problem_embeddings_problem_hash",
        ),
    )
    op.create_index(
        op.f("ix_problem_embeddings_problem_type_id"),
        "problem_embeddings",
        ["problem_type_id"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX ix_problem_embeddings_embedding "
        "ON problem_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_problem_embeddings_embedding")
    op.drop_index(
        op.f("ix_problem_embeddings_problem_type_id"),
        table_name="problem_embeddings",
    )
    op.drop_table("problem_embeddings")
    op.execute("DROP INDEX IF EXISTS ix_product_embeddings_embedding")
    op.drop_table("product_embeddings")
    # Leave the vector extension in place — other migrations may use it.
