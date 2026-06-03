"""Prompt-injection defenses: input sanitization and content fencing."""

from __future__ import annotations

import re

MAX_USER_MESSAGE_LENGTH = 2000

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Tokens an LLM emits *as a string* for a field that should have been JSON
# null. DeepSeek's structured output does this routinely; left unchecked, a
# truthy "null" slips past `value or fallback` guards and surfaces to the
# user (a literal "null" chat bubble) or poisons a downstream match.
_NULLISH_LLM_TOKENS = frozenset(
    {"", "null", "none", "nil", "n/a", "na", "undefined", "nan"}
)


def clean_llm_text(value: str | None) -> str | None:
    """Normalize an optional string an LLM produced.

    Returns ``None`` when *value* is missing, whitespace-only, or one of the
    literal null-ish tokens an LLM emits in place of a real JSON null. Use at
    every site that does ``extraction.field or fallback`` so the fallback
    actually fires instead of rendering the string "null".
    """
    if value is None:
        return None
    stripped = value.strip()
    if stripped.lower() in _NULLISH_LLM_TOKENS:
        return None
    return stripped


def sanitize_user_input(
    text: str | None, *, max_length: int = MAX_USER_MESSAGE_LENGTH
) -> str | None:
    """Clean user-supplied text before it enters the agent graph.

    Strips control characters, trims whitespace, and truncates to
    *max_length*.  Returns ``None`` for empty / whitespace-only input.
    """
    if not text:
        return None
    text = _CONTROL_CHARS_RE.sub("", text)
    text = text.strip()
    if not text:
        return None
    if len(text) > max_length:
        text = text[:max_length]
    return text


def fence(value: str, label: str = "data") -> str:
    """Wrap *value* in XML fences so the LLM treats it as data, not instructions.

    Use when interpolating any externally-sourced content (LLM-extracted
    values, database fields, JSON context) into a system prompt.
    """
    return f"<{label}>\n{value}\n</{label}>"
