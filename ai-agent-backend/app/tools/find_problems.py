"""find_problems — vector match a symptom description against the KB.

Inputs:
  sku           optional. When present we resolve the product's family
                and filter the search to problems for that family.
  symptom_text  the user's free-form description.

Output: top-N `ProblemMatch` rows (each with its highest-confidence
curated solution attached) ordered by cosine similarity.

The agent never sees the embedding vectors — it only consumes the
structured `FindProblemsResponse`. Same contract pattern as Phase 1
tools.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings import embed_texts
from app.models import (
    ProblemEmbedding,
    ProblemType,
    Product,
    ProductType,
    Solution,
)
from app.schemas.tools import (
    FindProblemsResponse,
    ProblemMatch,
    ProblemSummary,
    SolutionOut,
)


async def find_problems(
    session: AsyncSession,
    *,
    sku: str | None,
    symptom_text: str,
    limit: int = 3,
) -> FindProblemsResponse:
    # Resolve family from SKU when available — a strong prior that cuts
    # cross-family false positives. An unknown SKU is fine; we just don't
    # filter.
    product_type_id: int | None = None
    product_type_code: str | None = None
    if sku:
        row = (
            await session.execute(
                select(Product.product_type_id, ProductType.code)
                .join(ProductType, Product.product_type_id == ProductType.id, isouter=True)
                .where(Product.sku == sku)
            )
        ).first()
        if row is not None:
            product_type_id, product_type_code = row

    [query_vec] = await embed_texts([symptom_text])

    # pgvector's `<=>` is cosine *distance* (0..2). Similarity = 1 - distance.
    # NOTE: ordering by the expression (not the label) because SQLAlchemy's
    # `order_by("dist")` is silently dropped when followed by `.limit(...)`,
    # producing an empty result set.
    dist_expr = ProblemEmbedding.embedding.cosine_distance(query_vec)
    stmt = (
        select(
            ProblemType,
            ProductType,
            dist_expr.label("dist"),
        )
        .join(ProblemEmbedding, ProblemEmbedding.problem_type_id == ProblemType.id)
        .join(
            ProductType, ProblemType.product_type_id == ProductType.id, isouter=True
        )
    )
    if product_type_id is not None:
        stmt = stmt.where(ProblemType.product_type_id == product_type_id)
    stmt = stmt.order_by(dist_expr).limit(limit)

    rows = (await session.execute(stmt)).all()

    matches: list[ProblemMatch] = []
    for prob, ptype, dist in rows:
        # Pull the highest-confidence solution for paraphrasing in the gate.
        top_sol = (
            await session.execute(
                select(Solution)
                .where(Solution.problem_type_id == prob.id)
                .order_by(Solution.confidence.desc(), Solution.id)
                .limit(1)
            )
        ).scalar_one_or_none()

        similarity = max(0.0, min(1.0, 1.0 - float(dist)))
        matches.append(
            ProblemMatch(
                problem=ProblemSummary(
                    id=prob.id,
                    code=prob.code,
                    label=prob.label,
                    description=prob.description,
                    severity=prob.severity,
                    product_type_code=ptype.code if ptype else None,
                ),
                similarity=similarity,
                top_solution=(
                    SolutionOut(
                        id=top_sol.id,
                        summary=top_sol.summary,
                        body_markdown=top_sol.body_markdown,
                        confidence=top_sol.confidence,
                        escalate_if=top_sol.escalate_if,
                        sop_url=top_sol.sop_url,
                        rma_template_url=top_sol.rma_template_url,
                    )
                    if top_sol is not None
                    else None
                ),
            )
        )

    return FindProblemsResponse(
        sku=sku,
        product_type_code=product_type_code,
        matches=matches,
    )
