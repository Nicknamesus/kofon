"""Graph nodes. One module per node, each defining `async def run(state) -> dict`.

Naming follows `BACKEND_PLAN.md` §3.3:
    entry_router, presales.figure_out, guide.choose_approach,
    guide.find, guide.happy_gate, postsales.identify, postsales.match_kb,
    postsales.fix_gate, other.reclassify, outcome_*.
"""
