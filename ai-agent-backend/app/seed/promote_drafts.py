"""Promote draft seed YAML into the active `seed/product_types/` +
`seed/products/` folders that the loader scans.

The catalog ingest produces draft YAML keyed by URL stem (e.g.
`120.product_type.yaml`) or by PDF slug. The seed loader only reads
`seed/product_types/<code>.yaml` and `seed/products/<code>.yaml` — one
file per `product_type_code`. This script bridges the two:

    1. Group draft files by their `product_type_code` (inside the YAML).
    2. For each code, merge:
       - `spec_schema`: union of keys across drafts. First draft wins on
         conflicting type/label so the result is deterministic.
       - `products`: concatenated, deduped by `sku` (first occurrence wins).
       - top-level metadata (`name`, `family`, `description`): first draft's
         value; later drafts may differ slightly but we don't try to merge.
    3. Skip codes that already have a hand-curated file under
       `seed/product_types/` (the human's intent there is authoritative).
       Logged so the reviewer can decide whether to merge later.
    4. Skip codes matching `--skip` substrings (default: `r_series*`,
       because the curated RF080 seed is canonical for that family).

CLI::

    python -m app.seed.promote_drafts                          # dry run
    python -m app.seed.promote_drafts --apply                  # write files
    python -m app.seed.promote_drafts --apply --skip foo --skip bar

After promoting, run `python -m app.seed.load` to push everything into
Postgres. The draft files are left in place under `seed/drafts/` so the
extractor's idempotent-skip and your review trail stay intact.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

SEED_ROOT = Path(__file__).resolve().parents[2] / "seed"
DRAFTS_DIR = SEED_ROOT / "drafts"
TYPES_DIR = SEED_ROOT / "product_types"
PRODUCTS_DIR = SEED_ROOT / "products"


# LLM-chosen draft codes → consolidated target code.
#
# Background: the URL-extractor and PDF-extractor pick a `product_type_code`
# per page based on the visible product name on that page. The result is
# overly fine-grained — e.g. the KR family of right-angle gearmotors has
# one page per frame size, and each got its own code (`kr045_30`,
# `kr060_22`, …). For the chatbot to do meaningful "I'll show you that
# family" grouping, those need to roll up into one type with a `frame_size`
# spec column.
#
# Only safe merges live here — same product line, same spec_schema shape,
# different frame sizes or trivial variants. Anything ambiguous (powered
# vs hand-crank, planetary vs harmonic) stays separate.
MERGE_MAP: dict[str, str] = {
    # KR* right-angle gearmotor family — 9 LLM codes → 1.
    "k_r_series": "kr_series",
    "kr045_30": "kr_series",
    "kr045_series": "kr_series",
    "kr060_22": "kr_series",
    "kr070_25": "kr_series",
    "kr070_series": "kr_series",
    "kr080_19": "kr_series",
    "kr080_series": "kr_series",
    "kr090_25": "kr_series",
    "kr090_series": "kr_series",
    "kr095_23": "kr_series",
    "kr110_23": "kr_series",
    "kr128_22": "kr_series",
    "kr128_series": "kr_series",
    # W-series micro planetary gearbox — frame size 8/10/12 → one type.
    "w8_micro": "w_series",
    "w10_micro": "w_series",
    "w12_micro": "w_series",
    # PWZQ heavy-duty travel drives — variants of one family.
    "pwzq_heavy_duty_travel": "pwzq_series",
    "pwzq_hub_mounted": "pwzq_series",
    # TL torque-limiter / tightening series.
    "tl_series_tightening": "tl_series",
    # Two R-frame industrial planetary drafts → one combined type, kept
    # separate from the hand-curated `r_series` (which is RF080-only).
    "r060_series": "r_industrial_series",
    "r080_series": "r_industrial_series",
    # KGR family — KGR070 page + the broader KGR series.
    "kgr070": "kgr_series",
}


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! failed to parse {path.name}: {exc}", file=sys.stderr)
        return None


def _yaml_dump(data: Any) -> str:
    return yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False
    )


def _gather() -> dict[str, dict[str, list[Path]]]:
    """Group drafts by *target* product_type_code (after MERGE_MAP).

    Returns `{target_code: {'pt': [...], 'p': [...], 'src_codes': set}}`.
    `src_codes` records what the LLM originally called things so the
    written file's header can show the merge trail."""
    by_code: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"pt": [], "p": [], "src_codes": set()}
    )
    for path in sorted(DRAFTS_DIR.glob("*.product_type.yaml")):
        data = _load_yaml(path)
        code = (data or {}).get("code")
        if not code:
            continue
        target = MERGE_MAP.get(code, code)
        by_code[target]["pt"].append(path)
        by_code[target]["src_codes"].add(code)
    for path in sorted(DRAFTS_DIR.glob("*.products.yaml")):
        data = _load_yaml(path)
        code = (data or {}).get("product_type_code")
        if not code:
            continue
        target = MERGE_MAP.get(code, code)
        by_code[target]["p"].append(path)
        by_code[target]["src_codes"].add(code)
    return by_code


def _merge_pt(paths: list[Path]) -> dict[str, Any]:
    """Merge product_type drafts under one code.

    First file wins on scalar fields (code/name/family/description). For
    `spec_schema`, we take the union of keys; first occurrence wins on
    conflicting type/label."""
    merged: dict[str, Any] = {}
    schema: dict[str, dict[str, Any]] = {}
    for path in paths:
        doc = _load_yaml(path) or {}
        for k in ("code", "name", "family", "description"):
            if k not in merged and doc.get(k):
                merged[k] = doc[k]
        for spec_key, spec_val in (doc.get("spec_schema") or {}).items():
            if spec_key not in schema:
                schema[spec_key] = spec_val
    merged["spec_schema"] = schema
    return merged


def _merge_products(
    paths: list[Path], *, global_seen: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Concatenate products, dedup by `sku`.

    Two dedup layers:
      - within-code: first occurrence in this code's drafts wins (same as before).
      - cross-code: if a SKU has already been claimed by a previously-promoted
        code, we drop it here. Reason: the loader's product table has a UNIQUE
        constraint on `sku`, so attempting to upsert the same SKU under two
        product_type_ids in one INSERT raises CardinalityViolationError.
        Returns the kept products and the SKUs dropped to cross-code conflict
        (caller logs them so the human can rationalize codes later)."""
    seen: set[str] = set()
    dropped_cross_code: list[str] = []
    out: list[dict[str, Any]] = []
    for path in paths:
        doc = _load_yaml(path) or {}
        for p in doc.get("products") or []:
            sku = p.get("sku")
            if not sku or sku in seen:
                continue
            if sku in global_seen:
                dropped_cross_code.append(sku)
                continue
            seen.add(sku)
            global_seen.add(sku)
            out.append(p)
    return out, dropped_cross_code


def _should_skip(code: str, skip_patterns: list[str]) -> bool:
    """Skip when the code equals a pattern or starts with `<pattern>_`.

    Substring match would over-fire: pattern `r_series` would also kill
    `kgr_series` and `k_r_series`, which are unrelated families."""
    for pat in skip_patterns:
        if code == pat or code.startswith(pat + "_"):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote drafts into seed/.")
    ap.add_argument(
        "--apply", action="store_true", help="Actually write files (default: dry run)."
    )
    ap.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Substring filter — codes containing this string are skipped. "
        "Defaults to `r_series` to preserve the hand-curated RF080 seed.",
    )
    args = ap.parse_args()
    skip_patterns = args.skip or ["r_series"]

    by_code = _gather()
    existing_pt = {p.stem for p in TYPES_DIR.glob("*.yaml")}
    existing_p = {p.stem for p in PRODUCTS_DIR.glob("*.yaml")}

    promoted = 0
    skipped_collision = 0
    skipped_pattern = 0
    skipped_empty = 0
    total_skus = 0
    total_cross_drops = 0
    # Track SKUs across all codes so cross-code duplicates are dropped
    # (loader's UNIQUE(sku) makes the INSERT fail otherwise).
    global_seen: set[str] = set()

    for code, items in sorted(by_code.items()):
        if _should_skip(code, skip_patterns):
            skipped_pattern += 1
            print(f"  [skip pat ] {code}  ({len(items['p'])} drafts)")
            continue
        if code in existing_pt or code in existing_p:
            skipped_collision += 1
            print(f"  [skip seed] {code}  (already in seed/, leave for human merge)")
            continue

        pt_merged = _merge_pt(items["pt"])
        # Drafts carry the LLM's per-page code; overwrite with the target
        # code so the YAML stays self-consistent with the filename.
        pt_merged["code"] = code
        products, dropped_cross = _merge_products(items["p"], global_seen=global_seen)
        if dropped_cross:
            total_cross_drops += len(dropped_cross)
            preview = ", ".join(dropped_cross[:3])
            extra = f" (+{len(dropped_cross) - 3} more)" if len(dropped_cross) > 3 else ""
            print(
                f"  [dedup x  ] {code}: dropped {len(dropped_cross)} SKU(s) "
                f"already claimed by an earlier code: {preview}{extra}"
            )

        pt_path = TYPES_DIR / f"{code}.yaml"
        p_path = PRODUCTS_DIR / f"{code}.yaml"

        # Header comment with provenance. When MERGE_MAP rolled multiple
        # LLM codes into one target, list them so the human review trail
        # explains why this file unions e.g. kr045_30 + kr060_22 + …
        src_codes = sorted(items["src_codes"])
        merged_from = ""
        if src_codes != [code]:
            merged_from = f"# Merged LLM codes: {', '.join(src_codes)}\n"
        header_pt = (
            f"# Promoted from {len(items['pt'])} draft(s) under seed/drafts/.\n"
            f"{merged_from}"
            f"# Sources: {', '.join(p.stem for p in items['pt'])}\n"
        )
        header_p = (
            f"# Promoted from {len(items['p'])} draft(s) under seed/drafts/.\n"
            f"{merged_from}"
            f"# Sources: {', '.join(p.stem for p in items['p'])}\n"
            f"# SKUs: {len(products)}\n"
        )

        if not products:
            skipped_empty += 1
            print(
                f"  [skip empty] {code}  (no SKUs — likely PDF-only family, "
                f"OCR/extract didn't finish)"
            )
            continue

        promoted += 1
        total_skus += len(products)
        action = "WRITE" if args.apply else "would-write"
        print(
            f"  [{action}] {code:35s} "
            f"{len(pt_merged.get('spec_schema', {})):2d} spec keys, "
            f"{len(products):3d} SKUs"
        )
        if args.apply:
            pt_path.write_text(header_pt + _yaml_dump(pt_merged), encoding="utf-8")
            p_path.write_text(
                header_p
                + _yaml_dump({"product_type_code": code, "products": products}),
                encoding="utf-8",
            )

    print()
    print("=== promotion summary ===")
    print(f"  promoted:           {promoted}")
    print(f"  skipped (collision):{skipped_collision}")
    print(f"  skipped (pattern):  {skipped_pattern}")
    print(f"  skipped (empty):    {skipped_empty}")
    print(f"  cross-code dropped: {total_cross_drops}")
    print(f"  total SKUs written: {total_skus}")
    if not args.apply:
        print("\n(dry run — pass --apply to actually write files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
