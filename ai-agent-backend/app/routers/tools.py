"""HTTP wrappers around the read-only Phase 1 tools.

The endpoints exist so we can curl-test the tools without an agent in
the loop. Phase 2 onwards the agent calls the underlying functions
directly (no HTTP hop), so these routes stay thin — pure adapters.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.tools import (
    GetSolutionResponse,
    RecommendCategoriesRequest,
    RecommendCategoriesResponse,
    SearchProductsRequest,
    SearchProductsResponse,
)
from app.tools import get_solution, recommend_categories, search_products
from app.tools.get_solution import ProblemNotFoundError

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.post("/search_products", response_model=SearchProductsResponse)
async def search_products_route(
    payload: SearchProductsRequest,
    session: AsyncSession = Depends(get_session),
) -> SearchProductsResponse:
    results = await search_products(
        session, query=payload.query, filters=payload.filters, limit=payload.limit
    )
    return SearchProductsResponse(results=results)


@router.post(
    "/recommend_categories", response_model=RecommendCategoriesResponse
)
async def recommend_categories_route(
    payload: RecommendCategoriesRequest,
    session: AsyncSession = Depends(get_session),
) -> RecommendCategoriesResponse:
    return await recommend_categories(
        session,
        industry=payload.industry,
        application=payload.application,
        limit=payload.limit,
    )


@router.get(
    "/solutions/{problem_type_id}", response_model=GetSolutionResponse
)
async def get_solution_route(
    problem_type_id: int,
    session: AsyncSession = Depends(get_session),
) -> GetSolutionResponse:
    try:
        return await get_solution(session, problem_type_id)
    except ProblemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
