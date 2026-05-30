"""One-time dedup of synonym keys in product_types' spec_schema.

The draft-merge step (one product_type built from several extracted drafts)
produced families where the SAME spec lives under two different key names —
e.g. `stage`/`stages`, `noise_db`/`noise_db_a`,
`input_speed_rpm_max`/`max_input_speed_rpm`. Both names appear in
spec_schema (so the configurator renders duplicate fields) and different
subsets of SKUs populate one or the other. No SKU populates both, so
collapsing to one canonical key per concept is a safe rename.

MERGES below were chosen by inspection (identical labels, disjoint SKU sets):
canonical key ← [synonyms]. Product specs are migrated to the canonical key
(with an optional value transform) and synonym keys are dropped from the
spec_schema. Idempotent: once synonyms are gone, re-running is a no-op.

Comment/format-preserving (reuses normalize.py's ruamel config). Run with
`python -m app.seed.dedup_specs` (`--check` for a dry run). Re-seed after.
"""
from __future__ import annotations

import re
import sys

import yaml as _pyyaml

from app.seed.normalize import (
    PRODUCTS,
    TYPES,
    _dump,
    _preserve_description,
    yaml,
)


def _stage_to_int(v):
    """'2-stage' -> 2 ; '1' -> 1 ; 1 -> 1."""
    m = re.search(r"\d+", str(v))
    return int(m.group()) if m else v


def _to_int(v):
    """Coerce a clean numeric value to int, else leave unchanged."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f == int(f) else v


# code -> list of merges. Each merge:
#   canonical: the key to keep
#   synonyms:  keys to fold into canonical and drop from spec_schema
#   transform: optional fn applied to a synonym value before assigning
#   coerce:    optional fn applied to the canonical value afterwards
MERGES: dict[str, list[dict]] = {
    "kgr_series": [
        {"canonical": "stages", "synonyms": ["stage"],
         "transform": _stage_to_int, "coerce": _to_int},
        {"canonical": "no_load_torque_nm", "synonyms": ["mean_no_load_torque_nm"]},
        {"canonical": "noise_db", "synonyms": ["noise_db_a"]},
    ],
    "kpx_s_series": [
        {"canonical": "max_input_speed_rpm", "synonyms": ["input_speed_rpm_max"]},
        {"canonical": "noise_db", "synonyms": ["noise_db_a"]},
    ],
    "w_series": [
        {"canonical": "stages", "synonyms": ["stage"], "coerce": _to_int},
        {"canonical": "max_continuous_input_speed_rpm",
         "synonyms": ["input_speed_rpm_max"]},
        {"canonical": "max_instantaneous_input_speed_rpm",
         "synonyms": ["input_speed_instantaneous_rpm_max"]},
        {"canonical": "moment_of_inertia_g_cm2",
         "synonyms": ["moment_of_inertia_gcm2"]},
        {"canonical": "temperature_range_c",
         "synonyms": ["recommended_temperature_range_c"]},
    ],
    "zf_s_series": [
        {"canonical": "output_moment_of_inertia_kg_cm2",
         "synonyms": ["output_inertia_kgcm2"]},
    ],
    "kfdg_series": [
        {"canonical": "max_thrust_screw_input_torque_Nm",
         "synonyms": ["max_thrust_screw_input_torque_nm"]},
    ],
    "pl_tightening_machine": [
        {"canonical": "service_life_cycles", "synonyms": ["life_cycles"]},
    ],
}


def _migrate_specs(specs, merge) -> bool:
    """Fold synonym keys into the canonical key, in place. Return changed."""
    changed = False
    canonical = merge["canonical"]
    transform = merge.get("transform")
    for syn in merge["synonyms"]:
        if syn not in specs:
            continue
        idx = list(specs.keys()).index(syn)
        val = specs.pop(syn)
        changed = True
        if val is not None and specs.get(canonical) is None:
            new = transform(val) if transform else val
            # Reuse the synonym's slot so key order stays stable.
            specs.insert(idx, canonical, new)
    coerce = merge.get("coerce")
    if coerce and specs.get(canonical) is not None:
        new = coerce(specs[canonical])
        if new != specs[canonical] or type(new) is not type(specs[canonical]):
            specs[canonical] = new
            changed = True
    return changed


def main() -> None:
    check = "--check" in sys.argv

    # 1. Migrate product specs.
    prod_changed = 0
    # Build code -> merges lookup is already MERGES.
    for path in sorted(PRODUCTS.glob("*.yaml")):
        raw = path.read_text(encoding="utf-8")
        doc = yaml.load(raw)
        code = doc.get("product_type_code")
        merges = MERGES.get(code)
        if not merges:
            continue
        before = _dump(doc)
        for p in doc.get("products", []):
            specs = p.get("specs")
            if specs is None:
                continue
            for merge in merges:
                _migrate_specs(specs, merge)
        after = _dump(doc)
        if before != after:
            prod_changed += 1
            if not check:
                path.write_text(after, encoding="utf-8")

    # 2. Drop synonym keys from spec_schema.
    type_changed = 0
    for path in sorted(TYPES.glob("*.yaml")):
        raw = path.read_text(encoding="utf-8")
        doc = yaml.load(raw)
        merges = MERGES.get(doc.get("code"))
        if not merges:
            continue
        before = _preserve_description(raw, _dump(doc))
        schema = doc.get("spec_schema") or {}
        for merge in merges:
            for syn in merge["synonyms"]:
                if syn in schema:
                    del schema[syn]
        after = _preserve_description(raw, _dump(doc))
        if before != after:
            type_changed += 1
            if not check:
                path.write_text(after, encoding="utf-8")

    verb = "would change" if check else "changed"
    print(f"products: {verb} {prod_changed} files")
    print(f"product_types: {verb} {type_changed} files")

    # 3. Sanity: report any remaining duplicate labels in touched schemas.
    if not check:
        for path in sorted(TYPES.glob("*.yaml")):
            d = _pyyaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if d.get("code") not in MERGES:
                continue
            schema = d.get("spec_schema") or {}
            labels = [str(n.get("label", "")).strip().lower()
                      for n in schema.values() if isinstance(n, dict)]
            dups = {l for l in labels if labels.count(l) > 1 and l}
            if dups:
                print(f"  WARNING {path.name}: still-duplicate labels {dups}")


if __name__ == "__main__":
    main()
