"""One-time normalization of seed/products + seed/product_types.

Fixes two structural inconsistencies left by the extraction/promotion
pipeline, both of which broke the chatbot's search:

  1. Product/CAD links buried in `specs.datasheet_url` / `specs.cad_url`
     are lifted to the product-level columns (where the schema + tools
     expect them) and removed from `specs` and from the type spec_schema.

  2. Frame size is unified to a single invariant:
       - `frame_size_mm` : a clean integer (mm), or absent
       - `frame_size`    : a human/model label string, or absent
     Previously the value lived under either key with mixed int/string
     types ("090", "110×71", "KGR070", ...), so the numeric search filter
     silently matched nothing.

Comment-preserving (ruamel). Only files that actually change are written.
Run from ai-agent-backend/.  `--check` prints the diff summary without
writing.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from ruamel.yaml import YAML

SEED_ROOT = Path(__file__).resolve().parents[2] / "seed"
PRODUCTS = SEED_ROOT / "products"
TYPES = SEED_ROOT / "product_types"
LINK_KEYS = ("datasheet_url", "cad_url")

yaml = YAML()
yaml.preserve_quotes = True
yaml.allow_unicode = True
# The seed files write None as an explicit `null`; ruamel's default emits an
# empty scalar, which would churn every nullable spec line. Keep `null`.
yaml.representer.add_representer(
    type(None),
    lambda r, d: r.represent_scalar("tag:yaml.org,2002:null", "null"),
)

_COMPOSITE = re.compile(r"^\d+\s*[×xX]")


def parse_frame(raw) -> tuple[int | None, str | None]:
    """Return (frame_size_mm:int|None, frame_size_label:str|None)."""
    if raw is None:
        return None, None
    if isinstance(raw, int):  # incl. ruamel ScalarInt — force a plain int
        return int(raw), None
    s = str(raw).strip()
    if not s:
        return None, None
    if s.isdigit():  # pure numeric, incl. leading zeros ("090" -> 90)
        return int(s), None
    groups = re.findall(r"\d+", s)
    if not groups:
        return None, s  # no number at all — keep as label only
    if _COMPOSITE.match(s):
        # dimension like "110×71" / "90×82.5" — leading token is the frame
        return int(groups[0]), s
    if any(c.isalpha() for c in s):
        # model code like "KGR070" / "ST115" / "2S250" — trailing group
        return int(groups[-1]), s
    # numeric-ish with punctuation ("90.5") — take first group
    return int(groups[0]), s


def normalize_product(p) -> None:
    """Mutate one product dict in place (idempotent)."""
    specs = p.get("specs")
    if specs is None:
        return

    # 1. Lift links out of specs onto the product.
    for key in LINK_KEYS:
        if key in specs:
            val = specs.pop(key)
            if not p.get(key) and val:
                p[key] = val

    # 2. Unify frame size to plain values: frame_size_mm (int) + optional
    #    frame_size (str label). Resolve from both keys, then delete +
    #    reinsert in canonical order at the original position. Plain int/str
    #    force ruamel to drop any preserved leading-zero formatting
    #    ("090" -> 90). Idempotent: on a second pass the numeric mm is read
    #    from frame_size_mm and the label is kept from frame_size, rather
    #    than re-parsing one and dropping the other.
    if "frame_size_mm" in specs or "frame_size" in specs:
        mm = label = None
        for candidate in (specs.get("frame_size_mm"), specs.get("frame_size")):
            if candidate is None:
                continue
            cand_mm, cand_label = parse_frame(candidate)
            if mm is None:
                mm = cand_mm
            if label is None:
                label = cand_label
        keys = list(specs.keys())
        idx = min(
            (keys.index(k) for k in ("frame_size_mm", "frame_size") if k in keys),
            default=len(keys),
        )
        for k in ("frame_size_mm", "frame_size"):
            if k in specs:
                del specs[k]
        if mm is not None:
            specs.insert(idx, "frame_size_mm", mm)
            idx += 1
        if label is not None:
            specs.insert(idx, "frame_size", label)


def normalize_type(doc) -> None:
    """Clean a product_type's spec_schema in place (idempotent)."""
    schema = doc.get("spec_schema")
    if schema is None:
        return
    # Remove link/page keys — they are not specs.
    for key in (*LINK_KEYS, "datasheet_page"):
        if key in schema:
            del schema[key]
    # Make frame_size_mm a proper integer field with a clear label.
    if "frame_size_mm" in schema:
        node = schema["frame_size_mm"]
        node["type"] = "integer"
        if not str(node.get("label", "")).strip() or node.get("label") == "Frame size":
            node["label"] = "Frame size (mm)"
    if "frame_size" in schema:
        schema["frame_size"]["type"] = "string"


def _dump(doc) -> str:
    buf = io.StringIO()
    yaml.dump(doc, buf)
    return buf.getvalue()


# Top-level `description:` block: the key line plus its indented
# continuation lines, up to the next column-0 key. ruamel re-folds folded
# scalars on dump (cosmetic only — content is identical), so we splice the
# original block back to keep diffs limited to real schema changes.
_DESC_RE = re.compile(r"(?ms)^description:.*?(?=^\S)")


def _preserve_description(original: str, dumped: str) -> str:
    m = _DESC_RE.search(original)
    if m and _DESC_RE.search(dumped):
        return _DESC_RE.sub(lambda _: m.group(0), dumped, count=1)
    return dumped


def main() -> None:
    check = "--check" in sys.argv
    prod_changed = type_changed = 0

    for path in sorted(PRODUCTS.glob("*.yaml")):
        doc = yaml.load(path.read_text(encoding="utf-8"))
        before = _dump(doc)
        for p in doc.get("products", []):
            normalize_product(p)
        after = _dump(doc)
        if before != after:
            prod_changed += 1
            if not check:
                path.write_text(after, encoding="utf-8")

    for path in sorted(TYPES.glob("*.yaml")):
        raw = path.read_text(encoding="utf-8")
        doc = yaml.load(raw)
        before = _preserve_description(raw, _dump(doc))
        normalize_type(doc)
        after = _preserve_description(raw, _dump(doc))
        if before != after:
            type_changed += 1
            if not check:
                path.write_text(after, encoding="utf-8")

    verb = "would change" if check else "changed"
    print(f"products: {verb} {prod_changed} files")
    print(f"product_types: {verb} {type_changed} files")


if __name__ == "__main__":
    main()
