"""Embeddings refresh — content tables → vector tables.

Idempotent. For each product, product_type and problem_type, builds a
text chunk, hashes it, and only computes a new embedding if no row with
that `(source, hash)` already exists. Stale rows for the same source
(text changed) are deleted in the same pass.

Run after `app.seed.load`, or together via the convenience wrapper in
`app/seed/load.py`.

Text shapes (kept small and focused so the embedding stays specific):

  product_type → "<name> (<family>) — <description>"
  product      → "<sku> — <name>. specs: k1=v1, k2=v2, ..."
  problem_type → "<label>. <description>"

These are the chunks future semantic search will match against. Keep
them short, technical and consistent so the embeddings cluster cleanly.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, engine
from app.embeddings import embed_texts, get_provider, text_hash
from app.models import (
    ProblemEmbedding,
    ProblemType,
    Product,
    ProductEmbedding,
    ProductType,
)


def _product_type_text(pt: ProductType) -> str:
    return f"{pt.name} ({pt.family}) — {pt.description}"


def _product_text(p: Product, pt: ProductType | None) -> str:
    spec_bits = ", ".join(
        f"{k}={v}" for k, v in sorted((p.specs or {}).items()) if v is not None
    )
    family = f" — {pt.name} ({pt.family})" if pt else ""
    return f"{p.sku} — {p.name}{family}. specs: {spec_bits}"


def _problem_text(prob: ProblemType) -> str:
    return f"{prob.label}. {prob.description}"


async def refresh_product_embeddings(session: AsyncSession) -> int:
    """Rebuild rows for products + product_types whose text has changed."""
    pt_rows = (await session.execute(select(ProductType))).scalars().all()
    pr_rows = (
        await session.execute(
            select(Product, ProductType).join(
                ProductType, Product.product_type_id == ProductType.id, isouter=True
            )
        )
    ).all()

    targets: list[tuple[str, int, str]] = []  # (source_type, source_id, text)
    for pt in pt_rows:
        targets.append(("product_type", pt.id, _product_type_text(pt)))
    for p, pt in pr_rows:
        targets.append(("product", p.id, _product_text(p, pt)))

    return await _refresh_table(
        session,
        model=ProductEmbedding,
        keyed_by=("source_type", "source_id"),
        rows=[
            {"source_type": st, "source_id": sid, "text": t, "text_hash": text_hash(t)}
            for st, sid, t in targets
        ],
    )


async def refresh_problem_embeddings(session: AsyncSession) -> int:
    rows = (await session.execute(select(ProblemType))).scalars().all()
    return await _refresh_table(
        session,
        model=ProblemEmbedding,
        keyed_by=("problem_type_id",),
        rows=[
            {
                "problem_type_id": prob.id,
                "text": _problem_text(prob),
                "text_hash": text_hash(_problem_text(prob)),
            }
            for prob in rows
        ],
    )


async def _refresh_table(
    session: AsyncSession,
    *,
    model: type,
    keyed_by: tuple[str, ...],
    rows: list[dict],
) -> int:
    """For each row: insert if (key, hash) doesn't exist; drop stale rows
    that share the key but have a different hash.

    Returns the number of new embedding rows actually computed.
    """
    if not rows:
        return 0

    # Build the set of existing (key, hash) pairs for the keys we care
    # about — one query, regardless of row count.
    key_filter = []
    for r in rows:
        clause = None
        for col in keyed_by:
            cond = getattr(model, col) == r[col]
            clause = cond if clause is None else clause & cond
        key_filter.append(clause)

    from sqlalchemy import or_

    existing = (
        await session.execute(
            select(
                *(getattr(model, c) for c in keyed_by),
                model.text_hash,
            ).where(or_(*key_filter))
        )
    ).all()
    existing_set: set[tuple] = {
        tuple(row) for row in existing
    }  # (k1, ..., hash)

    to_embed: list[dict] = []
    for r in rows:
        key = tuple(r[c] for c in keyed_by) + (r["text_hash"],)
        if key not in existing_set:
            to_embed.append(r)

    if not to_embed:
        return 0

    # Drop stale rows for the same key (same source, different hash).
    for r in to_embed:
        clause = None
        for col in keyed_by:
            cond = getattr(model, col) == r[col]
            clause = cond if clause is None else clause & cond
        await session.execute(
            delete(model).where(clause & (model.text_hash != r["text_hash"]))
        )

    vectors = await embed_texts([r["text"] for r in to_embed])
    for r, vec in zip(to_embed, vectors, strict=True):
        session.add(model(embedding=vec, **r))

    return len(to_embed)


async def run() -> None:
    provider = get_provider()
    print(f"Refreshing embeddings via provider={provider.name!r} dim={provider.dim}")
    async with SessionLocal() as session:
        prod = await refresh_product_embeddings(session)
        prob = await refresh_problem_embeddings(session)
        await session.commit()

    await engine.dispose()
    print(f"Done. product_embeddings_new={prod}, problem_embeddings_new={prob}")


def main() -> None:
    try:
        asyncio.run(run())
    except Exception as exc:  # noqa: BLE001
        print(f"Embeddings refresh failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
