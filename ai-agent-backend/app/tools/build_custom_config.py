"""build_custom_config — assemble a custom-spec payload for a family.

The configurator UI sends the family code and the user's chosen spec
values (one entry per `product_types.spec_schema` key). This tool:

  1. validates that the family exists,
  2. echoes a normalised payload back,
  3. picks the closest stock SKU by a tiny scoring heuristic, so the
     agent can offer it as an alternative before committing to a custom.

No DB writes — that's Phase 4 (CRM/RFQ). Phase 3 just produces a
structured object the widget renders as the configurator summary card.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductType
from app.schemas.tools import BuildCustomConfigResponse


class FamilyNotFoundError(LookupError):
    pass


async def build_custom_config(
    session: AsyncSession,
    *,
    family_code: str,
    modules: dict,
) -> BuildCustomConfigResponse:
    family = (
        await session.execute(
            select(ProductType).where(ProductType.code == family_code)
        )
    ).scalar_one_or_none()
    if family is None:
        raise FamilyNotFoundError(f"Unknown family_code={family_code!r}")

    stock = (
        await session.execute(
            select(Product)
            .where(Product.product_type_id == family.id)
            .where(Product.status == "active")
        )
    ).scalars().all()

    closest = _closest_stock_sku(stock, modules)

    bits = ", ".join(f"{k}={v}" for k, v in sorted(modules.items()) if v is not None)
    rationale = (
        f"Custom {family.name} build with {bits}."
        if bits
        else f"Custom {family.name} build (no constraints yet)."
    )

    return BuildCustomConfigResponse(
        family_code=family.code,
        family_name=family.name,
        modules=modules,
        closest_stock_sku=closest,
        rationale=rationale,
    )


def _closest_stock_sku(products: list[Product], modules: dict) -> str | None:
    """Return the SKU whose specs match the most chosen module values.

    Numeric mismatches contribute 0; exact equality contributes 1. Plain
    integer comparison is enough for the seed sizes we ship — we are not
    trying to be a real configurator engine, just to surface a stock
    candidate before recommending custom.
    """
    if not products:
        return None
    best_sku: str | None = None
    best_score = -1.0
    for p in products:
        score = 0.0
        specs = p.specs or {}
        for key, value in modules.items():
            if value is None:
                continue
            other = specs.get(key)
            if other == value:
                score += 1.0
        if score > best_score:
            best_score = score
            best_sku = p.sku
    return best_sku
