"""Request/response schemas for the read-only Phase 1 tools.

The schemas are shared by the FastAPI endpoints (curl-testable in Phase 1)
and the LangGraph tools (consumed by the agent in Phase 2). Keeping them
in one place means the JSON contract is identical in both call paths.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------- search_products ----------------------


class SearchProductsFilters(BaseModel):
    """Optional structured filters for `search_products`.

    Phase 1 supports a small explicit set rather than a generic JSONB query
    — keeps the LLM's tool-call surface small and predictable.
    """

    family: str | None = Field(
        default=None,
        description="`product_types.code` (e.g. 'caesarplanetary').",
    )
    frame_size_mm: int | None = None
    min_nominal_torque_nm: float | None = None
    max_backlash_arcmin: float | None = None
    variant: str | None = Field(
        default=None, description="Family-specific variant tag (e.g. 'HP', 'HT')."
    )


class SearchProductsRequest(BaseModel):
    query: str = Field(
        default="",
        description="Free-form text — matched against product name / family description.",
    )
    filters: SearchProductsFilters = Field(default_factory=SearchProductsFilters)
    limit: int = Field(default=3, ge=1, le=20)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str
    family: str | None
    product_type_code: str | None
    specs: dict[str, Any]
    datasheet_url: str | None
    cad_url: str | None
    lead_time_days: int | None
    status: str


class SearchProductsResponse(BaseModel):
    results: list[ProductOut]


# ---------------------- recommend_categories ----------------------


class RecommendCategoriesRequest(BaseModel):
    industry: str
    application: str
    limit: int = Field(default=3, ge=1, le=10)


class ProductTypeRecommendation(BaseModel):
    product_type_code: str
    name: str
    family: str
    description: str
    fit_score: int
    rationale: str


class RecommendCategoriesResponse(BaseModel):
    industry: str
    application: str
    use_case_matched: bool = Field(
        description="False if the (industry, application) pair wasn't an exact match — "
        "the response then falls back to a fuzzy lookup."
    )
    recommendations: list[ProductTypeRecommendation]


# ---------------------- get_solution ----------------------


class ProblemSummary(BaseModel):
    id: int
    code: str
    label: str
    description: str
    severity: int
    product_type_code: str | None


class SolutionOut(BaseModel):
    id: int
    summary: str
    body_markdown: str
    confidence: int
    escalate_if: dict[str, Any] | None
    sop_url: str | None
    rma_template_url: str | None


class GetSolutionResponse(BaseModel):
    problem: ProblemSummary
    solutions: list[SolutionOut]
