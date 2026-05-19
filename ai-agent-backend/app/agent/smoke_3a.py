"""Phase 3a smoke — embeddings round-trip + find_problems.

Confirms:
  1. The configured embeddings provider returns 1024-dim vectors.
  2. `app.seed.embed` has populated product_embeddings / problem_embeddings.
  3. `find_problems` finds a real KB row for a planted symptom — the
     top match for "backlash is bigger than the datasheet says" is the
     `backlash_exceeds_spec` problem on CaesarPlanetary.

Run after `python -m app.seed.load`.
"""

from __future__ import annotations

import asyncio

from app.db import SessionLocal, engine
from app.embeddings import EMBEDDING_DIM, embed_texts, get_provider
from app.runtime import install_async_event_loop_policy
from app.tools import find_problems


async def main() -> None:
    provider = get_provider()
    print(f"provider={provider.name!r} dim={provider.dim}")
    [vec] = await embed_texts(["smoke test"])
    assert len(vec) == EMBEDDING_DIM, f"expected {EMBEDDING_DIM} dims, got {len(vec)}"
    print(f"OK: single embed returned {len(vec)} dims")

    async with SessionLocal() as session:
        result = await find_problems(
            session,
            sku="PG090-10-HP",
            symptom_text=(
                "The backlash measured at the output shaft is bigger "
                "than the datasheet number after a few hundred hours."
            ),
            limit=3,
        )

    print(f"\nfind_problems sku={result.sku} family={result.product_type_code}")
    for i, m in enumerate(result.matches, 1):
        print(
            f"  {i}. {m.problem.label}  "
            f"similarity={m.similarity:.3f}  "
            f"top_solution_confidence={m.top_solution.confidence if m.top_solution else '-'}"
        )

    assert result.matches, "find_problems returned no matches at all"
    top = result.matches[0]
    if provider.name == "hash":
        # Hash provider is non-semantic — we can't assert content quality,
        # only that the pipeline returned a structured response.
        print("\n(hash provider: skipping semantic correctness assertion)")
    else:
        assert top.problem.code == "backlash_exceeds_spec", (
            f"expected backlash_exceeds_spec at #1, got {top.problem.code}"
        )
        print("\nOK: top match is backlash_exceeds_spec")

    await engine.dispose()


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
