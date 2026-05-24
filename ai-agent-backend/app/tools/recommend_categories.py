"""recommend_categories — map an (industry, application) pair to product families.

Exact match on the natural key first; if that misses, fuzzy ILIKE on
industry and application separately. Ranks by curated `fit_score`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProductType, UseCase, UseCaseProductType, has_active_products
from app.schemas.tools import (
    ProductTypeRecommendation,
    RecommendCategoriesResponse,
)


async def recommend_categories(
    session: AsyncSession,
    industry: str,
    application: str,
    limit: int = 3,
) -> RecommendCategoriesResponse:
    use_case_id, matched = await _resolve_use_case(session, industry, application)

    if use_case_id is None:
        return RecommendCategoriesResponse(
            industry=industry,
            application=application,
            use_case_matched=False,
            recommendations=[],
        )

    stmt = (
        select(
            ProductType.code,
            ProductType.name,
            ProductType.family,
            ProductType.description,
            ProductType.product_page_url,
            UseCaseProductType.fit_score,
            UseCaseProductType.rationale,
        )
        .join(
            UseCaseProductType,
            UseCaseProductType.product_type_id == ProductType.id,
        )
        .where(UseCaseProductType.use_case_id == use_case_id)
        .where(ProductType.id.in_(has_active_products()))
        .order_by(UseCaseProductType.fit_score.desc(), ProductType.name)
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()
    recs = [
        ProductTypeRecommendation(
            product_type_code=code,
            name=name,
            family=family,
            description=desc,
            product_page_url=page_url,
            fit_score=fit,
            rationale=rationale,
        )
        for code, name, family, desc, page_url, fit, rationale in rows
    ]
    return RecommendCategoriesResponse(
        industry=industry,
        application=application,
        use_case_matched=matched,
        recommendations=recs,
    )


async def _resolve_use_case(
    session: AsyncSession, industry: str, application: str
) -> tuple[int | None, bool]:
    """Returns (use_case_id, was_exact_match)."""
    exact = await session.execute(
        select(UseCase.id).where(
            UseCase.industry == industry, UseCase.application == application
        )
    )
    hit = exact.scalar_one_or_none()
    if hit is not None:
        return hit, True

    # Fuzzy fallback — useful when the LLM paraphrases the user's input.
    fuzzy = await session.execute(
        select(UseCase.id)
        .where(
            UseCase.industry.ilike(f"%{industry}%"),
            UseCase.application.ilike(f"%{application}%"),
        )
        .limit(1)
    )
    return fuzzy.scalar_one_or_none(), False
