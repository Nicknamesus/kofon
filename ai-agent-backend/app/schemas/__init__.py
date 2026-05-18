"""Pydantic v2 schemas for request/response payloads and tool returns.

Tool schemas are deliberately stable: from Phase 2 onwards the LangGraph
agent consumes them via JSON-schema export, so renames are breaking changes.
"""
