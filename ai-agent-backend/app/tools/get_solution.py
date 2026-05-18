"""get_solution — list validated fixes for a problem type.

Returns the problem details plus every linked solution, ordered by
curated confidence. The Phase 3 'easily fixable?' gate uses the top
solution's `confidence` (plus prior-resolution counts) to decide which
terminal node fires — but that lives in Phase 3; Phase 1 just exposes
the data.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProblemType, ProductType, Solution
from app.schemas.tools import GetSolutionResponse, ProblemSummary, SolutionOut


class ProblemNotFoundError(LookupError):
    pass


async def get_solution(
    session: AsyncSession, problem_type_id: int
) -> GetSolutionResponse:
    row = (
        await session.execute(
            select(ProblemType, ProductType)
            .join(
                ProductType,
                ProblemType.product_type_id == ProductType.id,
                isouter=True,
            )
            .where(ProblemType.id == problem_type_id)
        )
    ).first()

    if row is None:
        raise ProblemNotFoundError(
            f"No problem_type with id={problem_type_id}"
        )

    problem, ptype = row

    solutions = (
        await session.execute(
            select(Solution)
            .where(Solution.problem_type_id == problem_type_id)
            .order_by(Solution.confidence.desc(), Solution.id)
        )
    ).scalars().all()

    return GetSolutionResponse(
        problem=ProblemSummary(
            id=problem.id,
            code=problem.code,
            label=problem.label,
            description=problem.description,
            severity=problem.severity,
            product_type_code=ptype.code if ptype else None,
        ),
        solutions=[
            SolutionOut(
                id=s.id,
                summary=s.summary,
                body_markdown=s.body_markdown,
                confidence=s.confidence,
                escalate_if=s.escalate_if,
                sop_url=s.sop_url,
                rma_template_url=s.rma_template_url,
            )
            for s in solutions
        ],
    )
