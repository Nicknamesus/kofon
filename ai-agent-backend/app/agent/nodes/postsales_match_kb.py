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

from app.agent.state import AgentState
from app.db import SessionLocal
from app.tools import find_problems

# Below this similarity, we don't trust the top match enough to confidently
# present a single answer. Tuned to be lenient — `find_problems` already
# narrows to the family when the SKU is known.
MATCH_FLOOR = 0.55


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    postsales = dict(slots.get("postsales") or {})

    sku = postsales.get("sku")
    symptom = postsales.get("symptom") or ""

    if not symptom:
        # Shouldn't reach here — identify gates on symptom — but be safe.
        return {
            "messages": [AIMessage(content="What's the symptom you're seeing?")],
            "current_node": "postsales.match_kb",
        }

    async with SessionLocal() as session:
        result = await find_problems(
            session, sku=sku, symptom_text=symptom, limit=3
        )

    if not result.matches:
        msg = (
            "I don't have any known issues that look like this in my "
            "catalog. Let me connect you with a service engineer."
        )
        return {
            "messages": [AIMessage(content=msg)],
            "outcome": "human_handoff",
            "cards": [
                {
                    "kind": "outcome",
                    "payload": {
                        "outcome": "human_handoff",
                        "title": "Connecting you with service",
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
                AIMessage(
                    content=(
                        "I'm not 100% sure which issue this is — does any of "
                        "the following look closest to what you're seeing?"
                    )
                )
            ],
            "cards": [
                {
                    "kind": "problem_candidates",
                    "payload": {"candidates": candidates_payload},
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
                AIMessage(
                    content=(
                        f"This looks like **{top.problem.label}**, but I don't "
                        "have a self-serve fix for it on file. Let me hand you "
                        "off to a service engineer."
                    )
                )
            ],
            "outcome": "human_handoff",
            "cards": [
                {
                    "kind": "outcome",
                    "payload": {
                        "outcome": "human_handoff",
                        "title": "Connecting you with service",
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

    summary = (
        f"This looks like **{top.problem.label}**.\n\n"
        f"_{sol.summary}_\n\n"
        "Did that fix it?"
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
                    "question": "Did that fix the issue?",
                    "yes_label": "Yes, fixed",
                    "no_label": "No, still broken",
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
