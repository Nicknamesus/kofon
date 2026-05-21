"""Generate use cases + (use_case, product_type) fits from the catalog.

Why this exists: the demo seed shipped 6 hand-picked use cases all pointing
at `caesarplanetary`. We now have 30 product types across planetary,
harmonic, bevel, linear, AGV-wheel, ball-screw, tightening-machine
families etc., and the fits table is mostly empty. Hand-writing one row
per (use_case × product_type) pair across that grid is tedious and
error-prone; the catalog itself is the source of truth for what the
products can do, so we hand DeepSeek the catalog + existing use cases
and ask it to propose:

    1. Any *additional* use cases the catalog supports that the current
       seed doesn't cover (linear motion, in-wheel AGV, harmonic-driven
       cobot joints, tightening, etc.).
    2. A `fit_score` 1–5 + one-sentence rationale for every
       (use_case, product_type) pair worth listing. Pairs with score < 2
       are dropped — they're noise.

Output:
    seed/use_cases.yaml          (existing + new, deduped on industry/application)
    seed/use_case_fits.csv       (rewritten from scratch from the LLM table)

After running, re-run `python -m app.seed.load` to push the new rows
into Postgres.

CLI::

    python -m app.seed.generate_use_cases                  # dry run, prints summary
    python -m app.seed.generate_use_cases --apply          # writes files

Why DeepSeek: see `memory/project-china-llm-constraint.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import sys
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm

SEED_ROOT = Path(__file__).resolve().parents[2] / "seed"
USE_CASES_PATH = SEED_ROOT / "use_cases.yaml"
FITS_PATH = SEED_ROOT / "use_case_fits.csv"
TYPES_DIR = SEED_ROOT / "product_types"


# ---------------- Pydantic extraction schema ----------------


class UseCase(BaseModel):
    industry: str = Field(
        description="Industry label, e.g. 'Robotics', 'Packaging', 'Machine tool'."
    )
    application: str = Field(
        description="Concrete application within that industry, e.g. "
        "'Cobot joint actuation'. Industry+application is the natural key."
    )
    description: str = Field(
        description="Two-sentence engineer-readable description of the "
        "motion-control problem this use case represents."
    )
    notes: str | None = Field(
        default=None,
        description="Optional: extra environment / constraint context "
        "(e.g. 'outdoor, corrosion resistance helpful').",
    )


class Fit(BaseModel):
    industry: str
    application: str
    product_type_code: str = Field(
        description="MUST be one of the codes from the catalog supplied "
        "in the prompt. Do not invent new codes."
    )
    fit_score: int = Field(
        ge=1, le=5,
        description="1 = bad fit, 3 = workable, 5 = excellent native fit. "
        "Reserve 5 for products explicitly designed for this application.",
    )
    rationale: str = Field(
        description="One sentence — why this product family fits this "
        "use case, citing the spec or feature that drives the score."
    )


class CatalogMapping(BaseModel):
    use_cases: list[UseCase] = Field(
        description="Final use_cases list to write to seed/use_cases.yaml. "
        "Include the existing use cases verbatim and append new ones. "
        "Use industry+application as the dedup key."
    )
    fits: list[Fit] = Field(
        description="(industry, application, product_type_code) rows with "
        "fit_score and rationale. Skip pairs with score < 2."
    )


SYSTEM = """You map Kofon's motion-control catalog to customer applications.

Inputs:
  - A list of existing use cases the chatbot already knows about.
  - The full product-type catalog (code, family, name, description).

Tasks:
  1. EXTEND the use cases. Keep all existing entries verbatim. Add new
     applications the catalog clearly supports but the existing list
     misses — for example, the catalog has ball-screws and electric
     cylinders (linear motion), AGV drive wheels (in-wheel mobility),
     tightening machines (assembly torque control), harmonic drives
     (cobot joints with very low backlash), bevel gearmotors (right-
     angle drives in tight spaces). Aim for 10–18 use cases total —
     enough variety that most plausible Kofon customers can find one,
     but no padding.

  2. SCORE fits. For every plausible (use_case × product_type) pair,
     emit a fit_score 1–5 and a one-sentence rationale citing a
     concrete spec or feature. Drop pairs with score < 2. A "good" 4–5
     fit should point at a product whose description / name explicitly
     mentions the application. A 3 means "engineer could make it work,
     but it's not what the product was designed for."

Rules:
  - Use ONLY product_type_codes that appear in the catalog input. Do
    NOT invent new codes.
  - Rationales must be specific. "Low backlash makes it suitable" is
    weak; "Backlash <3 arcmin on the HP variant matches cobot joint
    repeatability budgets" is good. Mention spec values when relevant.
  - Industry+application is the unique key. If you want to refine an
    existing use case, keep its (industry, application) pair exactly
    and edit the description/notes only.
  - Output JSON matching the CatalogMapping schema.
"""


# ---------------- generator ----------------


def _load_existing_use_cases() -> list[dict[str, Any]]:
    raw = USE_CASES_PATH.read_text(encoding="utf-8")
    return yaml.safe_load(raw) or []


def _load_catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(TYPES_DIR.glob("*.yaml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out.append({
            "code": doc.get("code", p.stem),
            "family": doc.get("family", ""),
            "name": doc.get("name", ""),
            "description": (doc.get("description") or "").strip(),
        })
    return out


async def _generate(existing: list[dict], catalog: list[dict]) -> CatalogMapping:
    llm = get_chat_llm(temperature=0.0).with_structured_output(CatalogMapping)

    existing_yaml = yaml.safe_dump(
        existing, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    catalog_yaml = yaml.safe_dump(
        catalog, sort_keys=False, allow_unicode=True, default_flow_style=False
    )

    user = (
        "EXISTING use cases (carry over verbatim):\n\n"
        + existing_yaml
        + "\n\nPRODUCT CATALOG (use the `code` field as `product_type_code`):\n\n"
        + catalog_yaml
        + "\n\nProduce the CatalogMapping now."
    )
    result = await llm.ainvoke(
        [SystemMessage(content=SYSTEM), HumanMessage(content=user)]
    )
    if result is None:
        raise RuntimeError("DeepSeek returned no structured output.")
    return result


def _write_use_cases(use_cases: list[UseCase]) -> None:
    # Header matches the existing file's style.
    header = (
        "# Application contexts the chatbot can match a user's free-form\n"
        "# description to.\n"
        "#\n"
        "# Generated by `python -m app.seed.generate_use_cases --apply` against\n"
        "# the current catalog. Edit by hand if rationale/notes need refining;\n"
        "# re-run to regenerate fits when product_types change.\n\n"
    )
    rows = [uc.model_dump(exclude_none=True) for uc in use_cases]
    body = yaml.safe_dump(
        rows, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    USE_CASES_PATH.write_text(header + body, encoding="utf-8")


def _write_fits(fits: list[Fit], valid_codes: set[str]) -> int:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["industry", "application", "product_type_code", "fit_score", "rationale"])
    written = 0
    for f in sorted(fits, key=lambda r: (r.industry, r.application, -r.fit_score)):
        if f.product_type_code not in valid_codes:
            # Silently drop — the LLM hallucinated a code.
            continue
        writer.writerow([f.industry, f.application, f.product_type_code, f.fit_score, f.rationale])
        written += 1
    FITS_PATH.write_text(buf.getvalue(), encoding="utf-8")
    return written


# ---------------- CLI ----------------


def _safe_print(*args: Any) -> None:
    import builtins
    try:
        builtins.print(*args)
    except UnicodeEncodeError:
        msg = " ".join(str(a) for a in args)
        sys.stdout.buffer.write(msg.encode("utf-8", errors="replace") + b"\n")


async def _amain() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write files (default: dry run).")
    args = ap.parse_args()

    existing = _load_existing_use_cases()
    catalog = _load_catalog()
    _safe_print(
        f"Existing use cases: {len(existing)}  •  catalog product types: {len(catalog)}"
    )

    result = await _generate(existing, catalog)
    valid_codes = {c["code"] for c in catalog}

    _safe_print(
        f"\nLLM produced: {len(result.use_cases)} use cases, {len(result.fits)} fit rows"
    )
    # Quick sanity report
    by_uc: dict[tuple[str, str], int] = {}
    for f in result.fits:
        key = (f.industry, f.application)
        by_uc[key] = by_uc.get(key, 0) + 1
    _safe_print("\nFits per use case (top 20 by count):")
    for (ind, app), n in sorted(by_uc.items(), key=lambda kv: -kv[1])[:20]:
        _safe_print(f"  {n:3d}  {ind} :: {app}")
    bad_codes = {f.product_type_code for f in result.fits} - valid_codes
    if bad_codes:
        _safe_print(f"\n!! Hallucinated codes (will be dropped): {sorted(bad_codes)}")

    if not args.apply:
        _safe_print("\n(dry run — pass --apply to write files)")
        return 0

    _write_use_cases(result.use_cases)
    written = _write_fits(result.fits, valid_codes)
    _safe_print(
        f"\nWrote {USE_CASES_PATH.name} ({len(result.use_cases)} use cases) "
        f"and {FITS_PATH.name} ({written} fit rows)."
    )
    return 0


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
