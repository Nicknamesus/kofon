"""postsales.match_kb — vector match symptom → known problems.

Calls `find_problems` with `(sku?, symptom_text)`. If the top match is
strong enough (similarity ≥ MATCH_FLOOR), we present the problem + its
top curated solution and ask "Did this help?". If no match crosses the
floor, we surface the closest two as candidates so the user can pick or
correct us — better UX than a hard "I don't know".

Slot keys (under slots.postsales):
  candidate_problem_id        the problem_type_id we surfaced
  candidate_solution          dict mirror of the solution we showed
  candidate_similarity        float — feeds the fix_gate alongside
                              solution.confidence
  match_phase                 'presented' | 'no_match'
"""

from __future__ import annotations

from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.agent.state import AgentState
from app.db import SessionLocal
from app.i18n import t
from app.models import ProblemType, ProductType, Solution
from app.schemas.tools import ProblemSummary, SolutionOut
from app.tools import find_problems

# Below this similarity, we don't trust the top match enough to confidently
# present a single answer. Tuned to be lenient — `find_problems` already
# narrows to the family when the SKU is known.
MATCH_FLOOR = 0.55

# `find_problems` always returns top-N rows, even when none are relevant
# (e.g. "LCD won't turn on" against a planetary-gearbox KB). Below this
# floor we treat the result as no match at all and escalate, rather than
# offering an irrelevant shortlist.
AMBIGUOUS_FLOOR = 0.30


async def _present_by_id(
    problem_id: int, postsales: dict, lang: str | None = None
) -> dict | None:
    """Look up a problem + its top solution by id and build a presented
    response. Returns None if the id doesn't resolve."""
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(ProblemType, ProductType)
                .join(
                    ProductType,
                    ProblemType.product_type_id == ProductType.id,
                    isouter=True,
                )
                .where(ProblemType.id == problem_id)
            )
        ).first()
        if row is None:
            return None
        prob, ptype = row
        top_sol = (
            await session.execute(
                select(Solution)
                .where(Solution.problem_type_id == prob.id)
                .order_by(Solution.confidence.desc(), Solution.id)
                .limit(1)
            )
        ).scalar_one_or_none()

    problem_summary = ProblemSummary(
        id=prob.id,
        code=prob.code,
        label=prob.label,
        description=prob.description,
        severity=prob.severity,
        product_type_code=ptype.code if ptype else None,
    )

    if top_sol is None:
        return {
            "messages": [
                AIMessage(content=t("pmk_no_solution", lang, label=prob.label))
            ],
            "outcome": "human_handoff",
            "cards": [
                {
                    "kind": "outcome",
                    "payload": {
                        "outcome": "human_handoff",
                        "title": t("title_connecting_service", lang),
                        "next_step": "human",
                    },
                }
            ],
            "slots": {
                "postsales": {
                    **postsales,
                    "candidate_problem_id": prob.id,
                    "match_phase": "no_solution",
                },
                "picked_problem_id": None,
            },
            "current_node": "postsales.match_kb.no_solution",
        }

    sol_out = SolutionOut(
        id=top_sol.id,
        summary=top_sol.summary,
        body_markdown=top_sol.body_markdown,
        confidence=top_sol.confidence,
        escalate_if=top_sol.escalate_if,
        sop_url=top_sol.sop_url,
        rma_template_url=top_sol.rma_template_url,
    )
    summary_text = t(
        "pmk_match_summary", lang, label=prob.label, summary=sol_out.summary
    )
    return {
        "messages": [AIMessage(content=summary_text)],
        "cards": [
            {
                "kind": "problem_match",
                "payload": {
                    "problem": problem_summary.model_dump(),
                    "solution": sol_out.model_dump(),
                    "similarity": 1.0,
                },
            },
            {
                "kind": "gate",
                "payload": {
                    "question": t("pmk_did_that_fix", lang),
                    "yes_label": t("gate_yes_fixed", lang),
                    "no_label": t("gate_no_still_broken", lang),
                },
            },
        ],
        "slots": {
            "postsales": {
                **postsales,
                "candidate_problem_id": prob.id,
                "candidate_solution": sol_out.model_dump(),
                "candidate_similarity": 1.0,
                "symptom": postsales.get("symptom") or prob.label,
                "phase": "ready",
                "match_phase": "presented",
                "ambiguous_candidates": None,
            },
            "picked_problem_id": None,
        },
        "current_node": "postsales.match_kb.presented",
    }


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    postsales = dict(slots.get("postsales") or {})
    lang = state.get("language")

    # Deterministic pick from the UI's candidate shortlist — skip the
    # vector search entirely and present the chosen problem by id.
    picked_id = slots.get("picked_problem_id")
    if picked_id:
        result = await _present_by_id(int(picked_id), postsales, lang)
        if result is not None:
            return result
        # Fell through — id didn't resolve. Fall back to vector path.

    sku = postsales.get("sku")
    symptom = postsales.get("symptom") or ""

    if not symptom:
        # Shouldn't reach here — identify gates on symptom — but be safe.
        return {
            "messages": [AIMessage(content=t("pi_what_symptom", lang))],
            "current_node": "postsales.match_kb",
        }

    async with SessionLocal() as session:
        result = await find_problems(
            session, sku=sku, symptom_text=symptom, limit=3
        )

    top_sim = result.matches[0].similarity if result.matches else 0.0
    if not result.matches or top_sim < AMBIGUOUS_FLOOR:
        # Either no rows at all, or the closest row is far enough away
        # that even offering it as a candidate would be misleading
        # (e.g. unrelated symptom against a gearbox-only KB).
        msg = t("pmk_no_match", lang)
        return {
            "messages": [AIMessage(content=msg)],
            "outcome": "human_handoff",
            "cards": [
                {
                    "kind": "outcome",
                    "payload": {
                        "outcome": "human_handoff",
                        "title": t("title_connecting_service", lang),
                        "next_step": "human",
                    },
                }
            ],
            "slots": {
                "postsales": {**postsales, "match_phase": "no_match"},
            },
            "current_node": "postsales.match_kb.no_match",
        }

    top = result.matches[0]

    if top.similarity < MATCH_FLOOR:
        # Weak match — present a short shortlist instead of one wrong
        # answer. The widget renders this as a pickable list; the user's
        # reply re-enters the graph and identify treats the chosen label
        # as the refined symptom.
        candidates_payload = [
            {
                "problem_type_id": m.problem.id,
                "label": m.problem.label,
                "description": m.problem.description,
                "similarity": round(m.similarity, 3),
            }
            for m in result.matches
        ]
        return {
            "messages": [
                AIMessage(content=t("pmk_ambiguous_intro", lang))
            ],
            "cards": [
                {
                    "kind": "problem_candidates",
                    "payload": {
                        "candidates": candidates_payload,
                        "title": t("pmk_closest_matches", lang),
                    },
                }
            ],
            "slots": {
                "postsales": {
                    **postsales,
                    "match_phase": "ambiguous",
                    "ambiguous_candidates": candidates_payload,
                }
            },
            "current_node": "postsales.match_kb.ambiguous",
        }

    sol = top.top_solution
    if sol is None:
        # We matched a problem with no curated solution — escalate gracefully.
        return {
            "messages": [
                AIMessage(content=t("pmk_no_solution", lang, label=top.problem.label))
            ],
            "outcome": "human_handoff",
            "cards": [
                {
                    "kind": "outcome",
                    "payload": {
                        "outcome": "human_handoff",
                        "title": t("title_connecting_service", lang),
                        "next_step": "human",
                    },
                }
            ],
            "slots": {
                "postsales": {
                    **postsales,
                    "candidate_problem_id": top.problem.id,
                    "match_phase": "no_solution",
                }
            },
            "current_node": "postsales.match_kb.no_solution",
        }

    summary = t(
        "pmk_match_summary", lang, label=top.problem.label, summary=sol.summary
    )

    return {
        "messages": [AIMessage(content=summary)],
        "cards": [
            {
                "kind": "problem_match",
                "payload": {
                    "problem": top.problem.model_dump(),
                    "solution": sol.model_dump(),
                    "similarity": round(top.similarity, 3),
                },
            },
            {
                "kind": "gate",
                "payload": {
                    "question": t("pmk_did_that_fix", lang),
                    "yes_label": t("gate_yes_fixed", lang),
                    "no_label": t("gate_no_still_broken", lang),
                },
            },
        ],
        "slots": {
            "postsales": {
                **postsales,
                "candidate_problem_id": top.problem.id,
                "candidate_solution": sol.model_dump(),
                "candidate_similarity": top.similarity,
                "match_phase": "presented",
            }
        },
        "current_node": "postsales.match_kb.presented",
    }
