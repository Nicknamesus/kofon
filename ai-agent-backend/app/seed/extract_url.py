"""Catalog ingest — fetch a Kofon product page and emit draft seed YAML.

Usage::

    python -m app.seed.extract_url https://www.kofon.com.cn/products_detail/120.html
    python -m app.seed.extract_url <URL> --code r_series      # force the type code
    python -m app.seed.extract_url <URL> --out seed/drafts    # alt output dir

Pipeline:
    1. httpx GET → raw HTML
    2. BeautifulSoup strips `<script>` / `<style>` and flattens to text
    3. DeepSeek (`get_chat_llm()`) with Pydantic structured output produces
       a `ProductTypeDraft` matching the schema used by `app/seed/load.py`
    4. Two YAML files written under `seed/drafts/`:
         <code>.product_type.yaml  — goes to seed/product_types/<code>.yaml
         <code>.products.yaml      — goes to seed/products/<code>.yaml
       Drafts live in `seed/drafts/` so the seed loader (which only scans
       seed/product_types, seed/products, seed/problems) doesn't pick them
       up. After human review, move them into the active folders.

Reusable: pointed at any product detail URL, the script tries to extract
a consistent schema. Variations in page layout are absorbed by the LLM
extraction step — the prompt is written to handle Chinese or English
text, missing fields, and tables with band ranges (e.g. "62–90 Nm").

Why DeepSeek, not Claude PDF input: Kofon operates from China — see
`memory/project-china-llm-constraint.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.agent.llm import get_chat_llm

# ---------------- Pydantic extraction schema ----------------


class SpecSchemaField(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str = Field(description="'integer' | 'number' | 'string'")
    label: str = Field(description="Human label rendered in the configurator UI.")


class ProductDraft(BaseModel):
    """One concrete SKU in the family."""

    sku: str = Field(description="SKU code, e.g. 'RF080-1-3' (model-stage-ratio).")
    name: str = Field(description="Human name with units, e.g. 'RF080 — 1-stage, 3:1'.")
    specs: dict[str, Any] = Field(
        description=(
            "Numeric / enum spec values keyed by spec_schema. Only include "
            "keys you have evidence for; never invent values."
        )
    )
    datasheet_url: str | None = None
    cad_url: str | None = None
    lead_time_days: int | None = None
    status: str = "active"


class ProductTypeDraft(BaseModel):
    """Top-level extraction result matching the seed/<...> file shapes."""

    product_type_code: str = Field(
        description=(
            "Lowercase snake_case slug for the product family. Examples: "
            "'r_series', 'caesarplanetary'. Stable across SKUs in the same family."
        )
    )
    product_type_name: str = Field(description="Display name, e.g. 'R Series'.")
    family: str = Field(
        description=(
            "High-level category. One of: 'Planetary gearbox', "
            "'Roller screw', 'Harmonic drive / strain wave', 'Linear actuator', "
            "'Bevel gear', or a new family if none fits."
        )
    )
    description: str = Field(
        description="One-paragraph engineer-readable summary of the family."
    )
    spec_schema: dict[str, SpecSchemaField] = Field(
        description=(
            "Declared spec keys used by products in this family. Mirror the "
            "vocabulary in existing seed (frame_size_mm, ratio, "
            "nominal_torque_nm, peak_torque_nm, backlash_arcmin, "
            "input_speed_rpm_max, efficiency_pct, weight_kg, variant)."
        )
    )
    products: list[ProductDraft] = Field(
        description=(
            "Concrete SKUs. If the page lists ratio bands (e.g. ratios "
            "3/4/5/8/10 sharing one torque row), expand each ratio into "
            "its own SKU, using the band's bounds for the torque range."
        )
    )
    source_url: str | None = None
    notes_for_reviewer: str | None = Field(
        default=None,
        description=(
            "Free-form notes about ambiguities, units that needed conversion, "
            "values copied from a band rather than a per-ratio entry, etc. "
            "Helps the human reviewer focus their attention."
        ),
    )


# ---------------- prompt ----------------


SYSTEM = """You are an extractor for a B2B motion-components catalog.
You will receive the text content of one product page. Output a
ProductTypeDraft + list of ProductDraft entries matching the schema.

Conventions (mirror existing seed YAML — caesarplanetary):
- `product_type_code` is a lowercase snake_case slug. Examples: 'r_series'
  for Kofon's general-purpose R-series planetary gearboxes;
  'caesarplanetary' for the precision line. Pick the smallest scope that
  still groups together SKUs that share a `spec_schema`.
- SKU naming: <ModelCode>[-stage][-ratio][-variant]. Example:
  'RF080-1-3' = RF080 model, 1-stage, ratio 3. If the page describes one
  frame only, the model code IS the frame (e.g. 'RF080').
- Always use SI units: Nm, rpm, arcmin, kg, mm, °C, %, dB, N.
- Do NOT invent specs. Use null / omit the key if a value isn't on the page.
- Ratio bands: if a row lists ratios 3/4/5/8/10 sharing one torque
  value or range, expand to five SKUs. If the torque is a band (62-90 Nm),
  put the lower bound in `nominal_torque_nm` (worst-case the customer
  can plan against) and note this in `notes_for_reviewer`.
- Chinese text on the page is fine — translate to English in
  `description` / `name`; keep numbers and SI units verbatim.
- If the page is clearly not a product page (404, news article, listing
  page), set `products` to an empty list and explain in `notes_for_reviewer`.
"""


# ---------------- fetcher ----------------


async def _fetch_text(url: str, *, max_chars: int = 60_000) -> str:
    async with httpx.AsyncClient(
        timeout=30.0, follow_redirects=True, headers={"User-Agent": "kofon-seed-extractor/0.1"}
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    # Collapse runs of blank lines so the LLM sees one logical block per spec.
    lines = [ln for ln in (l.strip() for l in text.splitlines()) if ln]
    flat = "\n".join(lines)
    return flat[:max_chars]


# ---------------- extractor ----------------


async def extract(url: str, *, code_override: str | None = None) -> ProductTypeDraft:
    text = await _fetch_text(url)
    if not text.strip():
        raise ValueError(f"Empty page body — likely a 404 or redirect ({url}).")
    llm = get_chat_llm(temperature=0.0).with_structured_output(ProductTypeDraft)
    user = (
        f"Source URL: {url}\n\n"
        f"Page text (cleaned):\n{text}\n\n"
        "Emit the structured extraction now."
    )
    draft: ProductTypeDraft | None = await llm.ainvoke(
        [SystemMessage(content=SYSTEM), HumanMessage(content=user)]
    )
    if draft is None:
        # DeepSeek structured-output returns None when the model can't
        # form a valid response matching the schema — usually because the
        # page isn't a product detail page (listing, news, contact, 404),
        # or the LLM hit a content-policy refusal. Caller decides retry.
        raise ValueError(
            "LLM returned no structured extraction (page likely isn't a "
            f"product detail, or hit a refusal): {url}"
        )
    if code_override:
        draft.product_type_code = code_override
    draft.source_url = url
    return draft


# ---------------- writer ----------------


def _yaml_dump(data: Any) -> str:
    return yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False
    )


def write_draft(draft: ProductTypeDraft, out_dir: Path) -> tuple[Path, Path]:
    """Write product_type + products YAML drafts. Returns the two paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    code = draft.product_type_code

    pt_payload = {
        "code": code,
        "name": draft.product_type_name,
        "family": draft.family,
        "description": draft.description,
        "spec_schema": {
            k: v.model_dump(exclude_none=True) for k, v in draft.spec_schema.items()
        },
    }
    products_payload = {
        "product_type_code": code,
        "products": [p.model_dump(exclude_none=True) for p in draft.products],
    }

    pt_path = out_dir / f"{code}.product_type.yaml"
    p_path = out_dir / f"{code}.products.yaml"

    header = (
        f"# DRAFT — extracted from {draft.source_url}\n"
        f"# Review before promoting to seed/product_types/{code}.yaml\n"
    )
    if draft.notes_for_reviewer:
        header += f"# Notes: {draft.notes_for_reviewer}\n"

    pt_path.write_text(header + _yaml_dump(pt_payload), encoding="utf-8")
    p_path.write_text(
        f"# DRAFT — extracted from {draft.source_url}\n"
        f"# Review before promoting to seed/products/{code}.yaml\n"
        + _yaml_dump(products_payload),
        encoding="utf-8",
    )
    return pt_path, p_path


# ---------------- CLI ----------------


def _safe_print(*args: object) -> None:
    """Print that survives Windows cp1252 stdout when the LLM returns
    Chinese characters in reviewer notes. Loses no information — the
    YAML files themselves are written UTF-8."""
    import builtins
    try:
        builtins.print(*args)
    except UnicodeEncodeError:
        msg = " ".join(str(a) for a in args)
        sys.stdout.buffer.write(msg.encode("utf-8", errors="replace") + b"\n")


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a Kofon product page and emit draft seed YAML."
    )
    parser.add_argument("url", help="Full product page URL.")
    parser.add_argument(
        "--code",
        dest="code_override",
        default=None,
        help="Force the product_type_code (otherwise the LLM picks).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("seed/drafts"),
        help="Output directory for draft YAML (default: seed/drafts).",
    )
    args = parser.parse_args()

    draft = await extract(args.url, code_override=args.code_override)
    pt_path, p_path = write_draft(draft, args.out)

    _safe_print(f"  Family:  {draft.product_type_code}  ({draft.product_type_name})")
    _safe_print(f"  SKUs:    {len(draft.products)}")
    _safe_print(f"  Wrote:   {pt_path}")
    _safe_print(f"           {p_path}")
    if draft.notes_for_reviewer:
        _safe_print(f"\n  Reviewer notes:\n    {draft.notes_for_reviewer}\n")
    _safe_print("Next:")
    _safe_print(f"  Review the drafts, then promote:")
    _safe_print(f"    mv {pt_path} seed/product_types/{draft.product_type_code}.yaml")
    _safe_print(f"    mv {p_path}  seed/products/{draft.product_type_code}.yaml")
    _safe_print(f"  Then: python -m app.seed.load")
    return 0


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
