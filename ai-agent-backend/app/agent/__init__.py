"""LangGraph agent layer.

The agent is a state machine, not a free-form LLM loop. Nodes are defined
explicitly under `nodes/`; the graph wiring is in `graph.py`. Each node is
either a small focused LLM call or a deterministic transition — see
`BACKEND_PLAN.md` §3.

LLM provider: DeepSeek (Kofon is in China — see
`memory/project-china-llm-constraint.md`).
"""
