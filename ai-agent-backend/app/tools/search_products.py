"""search_products — Phase 1 implementation.

Text + JSONB filter. Phase 3 replaces the text branch with a pgvector ANN
query over `product_embeddings`; the call signature stays the same so the
agent code in Phase 2 won't need updating.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductType
from app.schemas.tools import ProductOut, SearchProductsFilters


async def search_products(
    session: AsyncSession,
    query: str = "",
    filters: SearchProductsFilters | None = None,
    limit: int = 3,
) -> list[ProductOut]:
    """Return the top-N SKUs matching `query` and `filters`.

    `query`  — free-form. Phase 1 matches with ILIKE on product name,
               product-type name, and product-type description.
    `filters` — small explicit set; see `SearchProductsFilters`.

    Inactive products are excluded.
    """
    filters = filters or SearchProductsFilters()

    stmt = (
        select(Product, ProductType)
        .join(ProductType, Product.product_type_id == ProductType.id, isouter=True)
        .where(Product.status == "active")
    )

    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(pattern),
                ProductType.name.ilike(pattern),
                ProductType.description.ilike(pattern),
                ProductType.family.ilike(pattern),
            )
        )

    if filters.family:
        stmt = stmt.where(ProductType.code == filters.family)

    # JSONB filters on the per-family `specs` map.
    # Postgres comparison works directly on JSONB->>'key' cast to numeric.
    if filters.frame_size_mm is not None:
        stmt = stmt.where(
            Product.specs["frame_size_mm"].as_integer() == filters.frame_size_mm
        )
    if filters.min_nominal_torque_nm is not None:
        stmt = stmt.where(
            Product.specs["nominal_torque_nm"].as_float()
            >= filters.min_nominal_torque_nm
        )
    if filters.max_backlash_arcmin is not None:
        stmt = stmt.where(
            Product.specs["backlash_arcmin"].as_float()
            <= filters.max_backlash_arcmin
        )
    if filters.variant:
        stmt = stmt.where(Product.specs["variant"].as_string() == filters.variant)

    stmt = stmt.order_by(Product.sku).limit(limit)

    rows = (await session.execute(stmt)).all()

    return [
        ProductOut(
            sku=p.sku,
            name=p.name,
            family=pt.family if pt else None,
            product_type_code=pt.code if pt else None,
            specs=p.specs,
            datasheet_url=p.datasheet_url,
            cad_url=p.cad_url,
            lead_time_days=p.lead_time_days,
            status=p.status,
        )
        for p, pt in rows
    ]
