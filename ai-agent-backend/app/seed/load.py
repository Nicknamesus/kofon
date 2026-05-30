"""Seed loader — flat files → Postgres.

Reads everything under `ai-agent-backend/seed/` and upserts into the
content tables. Embedding regeneration (hash-based) is deferred to
Phase 3 along with the embedding tables themselves.

Order of operations is FK-driven:

    main_conversation_types
    use_cases
    product_types         (one file per family)
    products              (resolve product_type_code → id)
    use_case_product_types (resolve both)
    problem_types + solutions  (resolve product_type_code → id;
                                solutions are wiped + reinserted per problem)

Solutions are not natural-keyed in the schema, so the loader treats each
problem's solutions as authoritative: delete-then-insert per problem on
every run. This is cheap (handfuls of rows) and avoids needing a
synthetic key in the YAML.
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal, engine
from app.models import (
    MainConversationType,
    ProblemType,
    Product,
    ProductType,
    Solution,
    UseCase,
    UseCaseProductType,
)

SEED_ROOT = Path(__file__).resolve().parents[2] / "seed"


# ----------------------- low-level helpers -----------------------


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


async def _upsert(
    session: AsyncSession,
    model: type,
    rows: list[dict[str, Any]],
    *,
    conflict_cols: list[str],
    update_cols: list[str],
) -> int:
    """Bulk upsert with ON CONFLICT DO UPDATE. Returns rows touched."""
    if not rows:
        return 0
    # Normalize to a consistent column set. SQLAlchemy compiles a bulk
    # `.values(list_of_dicts)` using the keys of the FIRST dict, silently
    # dropping any column that only later rows carry. Seed files are
    # heterogeneous (e.g. some products have a datasheet_url, others don't),
    # so we fill the union of keys with None to keep every column in the
    # INSERT — otherwise ON CONFLICT's `excluded.<col>` has nothing to write.
    all_keys: set[str] = set()
    for row in rows:
        all_keys.update(row.keys())
    rows = [{key: row.get(key) for key in all_keys} for row in rows]
    stmt = pg_insert(model).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_cols,
        set_={col: getattr(stmt.excluded, col) for col in update_cols},
    )
    await session.execute(stmt)
    return len(rows)


# ----------------------- per-entity loaders -----------------------


async def load_main_conversation_types(session: AsyncSession) -> int:
    rows = _load_yaml(SEED_ROOT / "main_conversation_types.yaml")
    return await _upsert(
        session,
        MainConversationType,
        rows,
        conflict_cols=["code"],
        update_cols=["label", "description", "greeting_key"],
    )


async def load_use_cases(session: AsyncSession) -> int:
    rows = _load_yaml(SEED_ROOT / "use_cases.yaml")
    return await _upsert(
        session,
        UseCase,
        rows,
        conflict_cols=["industry", "application"],
        update_cols=["description", "notes"],
    )


async def load_product_types(session: AsyncSession) -> int:
    folder = SEED_ROOT / "product_types"
    rows = [_load_yaml(p) for p in sorted(folder.glob("*.yaml"))]
    return await _upsert(
        session,
        ProductType,
        rows,
        conflict_cols=["code"],
        update_cols=["name", "family", "description", "product_page_url", "spec_schema"],
    )


async def _product_type_id_by_code(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(select(ProductType.code, ProductType.id))
    return {code: id_ for code, id_ in result.all()}


async def load_products(session: AsyncSession) -> int:
    folder = SEED_ROOT / "products"
    pt_id = await _product_type_id_by_code(session)
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.yaml")):
        doc = _load_yaml(path)
        code = doc["product_type_code"]
        if code not in pt_id:
            raise ValueError(
                f"{path.name}: unknown product_type_code '{code}'. "
                "Add the corresponding file under seed/product_types/."
            )
        for p in doc["products"]:
            rows.append({**p, "product_type_id": pt_id[code]})
    return await _upsert(
        session,
        Product,
        rows,
        conflict_cols=["sku"],
        update_cols=[
            "name",
            "product_type_id",
            "specs",
            "datasheet_url",
            "cad_url",
            "lead_time_days",
            "status",
        ],
    )


async def load_use_case_fits(session: AsyncSession) -> int:
    rows_csv = _load_csv(SEED_ROOT / "use_case_fits.csv")
    pt_id = await _product_type_id_by_code(session)

    # Pull use_case ids by (industry, application).
    uc_rows = await session.execute(
        select(UseCase.id, UseCase.industry, UseCase.application)
    )
    uc_id = {(ind, app): id_ for id_, ind, app in uc_rows.all()}

    rows: list[dict[str, Any]] = []
    for r in rows_csv:
        key = (r["industry"], r["application"])
        if key not in uc_id:
            raise ValueError(
                f"use_case_fits.csv: unknown use case {key}. "
                "Add it to seed/use_cases.yaml first."
            )
        code = r["product_type_code"]
        if code not in pt_id:
            raise ValueError(
                f"use_case_fits.csv: unknown product_type_code '{code}'."
            )
        rows.append(
            {
                "use_case_id": uc_id[key],
                "product_type_id": pt_id[code],
                "fit_score": int(r["fit_score"]),
                "rationale": r["rationale"],
            }
        )
    upserted = await _upsert(
        session,
        UseCaseProductType,
        rows,
        conflict_cols=["use_case_id", "product_type_id"],
        update_cols=["fit_score", "rationale"],
    )
    # Delete fits whose (use_case_id, product_type_id) pair isn't in the CSV
    # anymore. The CSV is the source of truth — without this, regenerating
    # the file leaves stale rows when the LLM picks different fit pairs.
    csv_pairs = {(r["use_case_id"], r["product_type_id"]) for r in rows}
    existing = (
        await session.execute(
            select(
                UseCaseProductType.use_case_id, UseCaseProductType.product_type_id
            )
        )
    ).all()
    stale = [(uc, pt) for uc, pt in existing if (uc, pt) not in csv_pairs]
    for uc, pt in stale:
        await session.execute(
            delete(UseCaseProductType).where(
                UseCaseProductType.use_case_id == uc,
                UseCaseProductType.product_type_id == pt,
            )
        )
    return upserted


async def load_problems_and_solutions(session: AsyncSession) -> tuple[int, int]:
    """Upsert problems by (product_type_id, code); rewrite their solutions."""
    folder = SEED_ROOT / "problems"
    pt_id = await _product_type_id_by_code(session)

    problem_count = 0
    solution_count = 0

    for path in sorted(folder.glob("*.yaml")):
        doc = _load_yaml(path)
        code = doc["product_type_code"]
        if code not in pt_id:
            raise ValueError(
                f"{path.name}: unknown product_type_code '{code}'."
            )
        type_id = pt_id[code]

        for prob in doc["problems"]:
            solutions = prob.pop("solutions", [])
            prob_row = {**prob, "product_type_id": type_id}

            # Upsert the problem and grab its id back.
            stmt = pg_insert(ProblemType).values(prob_row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["product_type_id", "code"],
                set_={
                    "label": stmt.excluded.label,
                    "description": stmt.excluded.description,
                    "severity": stmt.excluded.severity,
                },
            ).returning(ProblemType.id)
            problem_id = (await session.execute(stmt)).scalar_one()
            problem_count += 1

            # Solutions: delete-then-insert. No natural key in the schema and
            # the row count per problem is tiny.
            await session.execute(
                delete(Solution).where(Solution.problem_type_id == problem_id)
            )
            for sol in solutions:
                await session.execute(
                    pg_insert(Solution).values(
                        problem_type_id=problem_id, **sol
                    )
                )
                solution_count += 1

    return problem_count, solution_count


# ----------------------- driver -----------------------


async def run() -> None:
    print(f"Seeding from {SEED_ROOT}")
    async with SessionLocal() as session:
        mct = await load_main_conversation_types(session)
        uc = await load_use_cases(session)
        pt = await load_product_types(session)
        prod = await load_products(session)
        fits = await load_use_case_fits(session)
        probs, sols = await load_problems_and_solutions(session)
        await session.commit()

        # Phase 3: refresh embeddings in the same transaction sequence,
        # so content + vectors stay in sync. Hash-keyed inside; only
        # rows whose text changed get re-embedded.
        from app.seed.embed import (
            refresh_problem_embeddings,
            refresh_product_embeddings,
        )

        prod_emb = await refresh_product_embeddings(session)
        prob_emb = await refresh_problem_embeddings(session)
        await session.commit()

    await engine.dispose()

    print(
        "Done. "
        f"main_conversation_types={mct}, "
        f"use_cases={uc}, "
        f"product_types={pt}, "
        f"products={prod}, "
        f"use_case_product_types={fits}, "
        f"problem_types={probs}, "
        f"solutions={sols}, "
        f"product_embeddings_new={prod_emb}, "
        f"problem_embeddings_new={prob_emb}"
    )


def main() -> None:
    try:
        asyncio.run(run())
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
