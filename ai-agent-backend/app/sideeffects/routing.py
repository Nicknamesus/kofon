"""Lead-routing matrix loader.

Reads `routing.yaml` once, returns a `Division` for any
`(main_type, product_family_code)` pair. The YAML structure is documented
in the file itself; resolution precedence:

  1. exact route match on (main_type, family)
  2. route with family='*' and `division_by_family: true` — uses the
     `families` map to pick the division for the given family
  3. route with family='*' and explicit `division` — that division
  4. fallback division

If the routing file is missing the loader returns a static default so
the chatbot still works in dev with no setup.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Division:
    code: str
    name: str
    inbox: str


_DEFAULT_DIVISION = Division(
    code="applications",
    name="Applications Engineering",
    inbox="apps-engineering@example.invalid",
)


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    from app.config import get_settings

    path = Path(get_settings().routing_matrix_path)
    if not path.is_absolute():
        # Resolve relative to the project root (cwd when uvicorn boots).
        path = Path.cwd() / path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def reset_cache() -> None:
    """Tests / hot-reload — drop the cached YAML."""
    _load.cache_clear()


def resolve_division(
    main_type: str | None,
    product_family_code: str | None,
) -> Division:
    cfg = _load()
    if not cfg:
        return _DEFAULT_DIVISION

    divisions: dict[str, dict] = cfg.get("divisions", {})
    families: dict[str, str] = cfg.get("families", {})
    routes: list[dict] = cfg.get("routes", [])

    def _as_division(key: str | None) -> Division | None:
        if not key:
            return None
        d = divisions.get(key)
        if not d:
            return None
        return Division(
            code=d.get("code", key),
            name=d.get("name", key),
            inbox=d.get("inbox", ""),
        )

    for route in routes:
        if route.get("main_type") != main_type:
            continue
        family = route.get("family")
        if family not in ("*", product_family_code):
            continue
        if family == product_family_code:
            div = _as_division(route.get("division"))
            if div:
                return div
        # family == '*'
        if route.get("division_by_family"):
            div_key = families.get(product_family_code or "")
            div = _as_division(div_key)
            if div:
                return div
        div = _as_division(route.get("division"))
        if div:
            return div

    fallback_key = (cfg.get("fallback") or {}).get("division")
    div = _as_division(fallback_key)
    return div or _DEFAULT_DIVISION
