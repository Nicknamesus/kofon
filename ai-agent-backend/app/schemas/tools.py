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
        description=(
            "`product_types.code` from the catalog. Examples spanning "
            "the families: 'caesarplanetary' / 'kr_series' / 'kpx_s_series' "
            "(planetary), '8_11_series_harmonic' (harmonic), "
            "'kofon_ball_screw' (linear), 'agv_drive_wheel_kfq150' (mobility)."
        ),
    )
    frame_size_mm: int | None = Field(
        default=None,
        description=(
            "Frame size in mm. Values are family-specific — e.g. caesarplanetary "
            "uses 60/90/140; kr_series uses 045/060/070/080/090/110/128."
        ),
    )
    ratio: int | None = Field(
        default=None,
        description=(
            "Reduction ratio (the N in 'N:1'). e.g. a '20:1' gearbox has ratio=20."
        ),
    )
    stages: int | None = Field(
        default=None,
        description="Number of planetary stages (1, 2, or 3).",
    )
    min_nominal_torque_nm: float | None = None
    max_backlash_arcmin: float | None = None
    variant: str | None = Field(
        default=None,
        description=(
            "Family-specific variant tag. Examples: 'HP' (low backlash) / "
            "'HT' (high torque) on caesarplanetary."
        ),
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
    product_page_url: str | None = None
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
    product_page_url: str | None = None
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


# ---------------------- find_problems (Phase 3) ----------------------


class FindProblemsRequest(BaseModel):
    sku: str | None = Field(
        default=None,
        description="Exact SKU. If known, restricts the search to that product's family.",
    )
    symptom_text: str = Field(
        description="Free-form description of what the customer is seeing."
    )
    limit: int = Field(default=3, ge=1, le=10)


class ProblemMatch(BaseModel):
    """One candidate problem and how confident we are it's the right one."""

    problem: ProblemSummary
    similarity: float = Field(
        description="Cosine similarity 0..1 (higher = closer to the symptom)."
    )
    top_solution: SolutionOut | None = Field(
        default=None,
        description="The highest-confidence curated fix; null if no solution rows.",
    )


class FindProblemsResponse(BaseModel):
    sku: str | None
    product_type_code: str | None = Field(
        default=None,
        description="Family resolved from the SKU. Null if SKU was unknown or unresolvable.",
    )
    matches: list[ProblemMatch]


# ---------------------- build_custom_config (Phase 3) ----------------------


class BuildCustomConfigRequest(BaseModel):
    family_code: str = Field(description="`product_types.code` to configure.")
    modules: dict[str, Any] = Field(
        description="User-chosen spec values keyed by `spec_schema` keys."
    )


class BuildCustomConfigResponse(BaseModel):
    family_code: str
    family_name: str
    modules: dict[str, Any]
    closest_stock_sku: str | None = Field(
        default=None,
        description="Stock SKU that gets closest to the chosen config (best-effort).",
    )
    rationale: str = Field(
        description="One sentence summarising the custom build for the user."
    )
