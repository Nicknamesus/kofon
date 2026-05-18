"""DeepSeek chat model factory.

All nodes call `get_chat_llm()` to get a ready-to-use chat model. Keeping
the factory in one place means switching models per-node (or globally,
later) is a one-line change.

Why DeepSeek: see `memory/project-china-llm-constraint.md`.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_deepseek import ChatDeepSeek

from app.config import get_settings


def get_chat_llm(
    *, temperature: float = 0.2, model: str | None = None
) -> ChatDeepSeek:
    """Return a `deepseek-chat` model — fast, cheap, supports tool calls.

    Use this for routers, slot-fillers, paraphrasers — most nodes.
    """
    settings = get_settings()
    return ChatDeepSeek(
        model=model or settings.deepseek_chat_model,
        temperature=temperature,
        api_key=settings.deepseek_api_key,
    )


@lru_cache(maxsize=1)
def get_reasoner_llm() -> ChatDeepSeek:
    """Return `deepseek-reasoner` for nodes that need deeper reasoning.

    Slower and more expensive — reserve for Phase 3 fuzzy-matching work.
    """
    settings = get_settings()
    return ChatDeepSeek(
        model=settings.deepseek_reasoner_model,
        api_key=settings.deepseek_api_key,
    )
