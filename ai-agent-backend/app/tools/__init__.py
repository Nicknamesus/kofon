"""Read-only tools the agent (and humans, via curl) call.

Phase 1 ships three: `search_products`, `recommend_categories`, `get_solution`.
Each is a plain async function that takes an `AsyncSession`; the LangChain
`@tool` wrappers added in Phase 2 will be thin adapters over these.
"""

from app.tools.build_custom_config import build_custom_config
from app.tools.find_problems import find_problems
from app.tools.get_solution import get_solution
from app.tools.recommend_categories import recommend_categories
from app.tools.search_products import search_products

__all__ = [
    "search_products",
    "recommend_categories",
    "get_solution",
    "find_problems",
    "build_custom_config",
]
