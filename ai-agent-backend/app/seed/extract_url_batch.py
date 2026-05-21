"""Batch extractor — run `extract_url` over many URLs in parallel.

Reads URLs (one per line) from a file, calls the single-URL extractor
with a concurrency cap, and writes drafts under `seed/drafts/`. Idempotent
— if both draft files for a URL already exist, the URL is skipped, so
re-running after a crash is cheap.

CLI::

    python -m app.seed.extract_url_batch seed/drafts/urls.txt
    python -m app.seed.extract_url_batch urls.txt --concurrency 3 --out seed/drafts

Output naming: drafts are keyed by the URL's filename stem (e.g. `120`
for `…/products_detail/120.html`) so multiple pages don't collide on
LLM-chosen `product_type_code`:

    seed/drafts/120.product_type.yaml
    seed/drafts/120.products.yaml
    seed/drafts/120.error.txt        # only when extraction fails

A final summary prints counts (ok / skipped / failed) and lists the
errored URLs so a retry pass can target just those.

Note: this is an extraction step. Merging drafts into the live
seed/product_types/ + seed/products/ folders is a separate human-review
pass (an `r_series_rf080.product_type.yaml` and `r_series_rf060.product_type.yaml`
typically need to be unified under one `r_series` code before promotion).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

import yaml

from app.seed.extract_url import _safe_print, extract, write_draft, ProductTypeDraft


def _stem_for(url: str) -> str:
    """Filename stem from the URL — e.g. '120' for .../products_detail/120.html."""
    parsed = urlparse(url)
    name = Path(parsed.path).stem or parsed.netloc
    return name


def _draft_paths(out_dir: Path, stem: str) -> tuple[Path, Path]:
    return (
        out_dir / f"{stem}.product_type.yaml",
        out_dir / f"{stem}.products.yaml",
    )


async def _process_one(
    url: str,
    out_dir: Path,
    sem: asyncio.Semaphore,
    counter: dict,
) -> None:
    stem = _stem_for(url)
    pt_path, p_path = _draft_paths(out_dir, stem)

    # Idempotent skip.
    if pt_path.exists() and p_path.exists():
        counter["skipped"] += 1
        _safe_print(f"[skip ] {stem}  ({url})")
        return

    async with sem:
        t0 = time.monotonic()
        try:
            draft: ProductTypeDraft = await extract(url)
        except Exception as exc:  # noqa: BLE001
            counter["failed"] += 1
            counter["errors"].append((url, exc))
            err_path = out_dir / f"{stem}.error.txt"
            err_path.write_text(
                f"URL: {url}\n"
                f"Error: {exc.__class__.__name__}: {exc}\n\n"
                + traceback.format_exc(),
                encoding="utf-8",
            )
            _safe_print(f"[FAIL] {stem}  ({url}) — {exc.__class__.__name__}: {exc}")
            return

    # Rename outputs to keep the URL-stem keying. write_draft uses the
    # LLM-chosen `product_type_code`; we rewrite the files under our
    # stem-keyed names so nothing collides.
    try:
        # Write with extract_url's own writer, then move to stem-keyed names.
        _, _ = write_draft(draft, out_dir)
        # Move from <code>.product_type.yaml to <stem>.product_type.yaml.
        code = draft.product_type_code
        src_pt = out_dir / f"{code}.product_type.yaml"
        src_p = out_dir / f"{code}.products.yaml"
        # Read + rewrite header to embed the URL stem for traceability.
        if src_pt.exists() and src_pt != pt_path:
            src_pt.replace(pt_path)
        if src_p.exists() and src_p != p_path:
            src_p.replace(p_path)
    except Exception as exc:  # noqa: BLE001
        counter["failed"] += 1
        counter["errors"].append((url, exc))
        _safe_print(f"[FAIL] {stem}  (write) — {exc}")
        return

    elapsed = time.monotonic() - t0
    counter["ok"] += 1
    _safe_print(
        f"[ok  ] {stem}  ({draft.product_type_code}, "
        f"{len(draft.products)} SKUs, {elapsed:.1f}s)"
    )


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description="Batch-extract Kofon product pages into draft YAML."
    )
    parser.add_argument(
        "url_file",
        type=Path,
        help="Plain text file with one URL per line. Blank / # lines ignored.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("seed/drafts"),
        help="Output directory for drafts (default: seed/drafts).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Parallel extractions (default 4 — DeepSeek handles this fine).",
    )
    args = parser.parse_args()

    urls: list[str] = []
    for line in args.url_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        urls.append(s)
    if not urls:
        _safe_print(f"No URLs in {args.url_file}.")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    counter: dict = {"ok": 0, "skipped": 0, "failed": 0, "errors": []}
    sem = asyncio.Semaphore(args.concurrency)

    _safe_print(
        f"Processing {len(urls)} URLs with concurrency={args.concurrency} → {args.out}\n"
    )
    t0 = time.monotonic()
    await asyncio.gather(
        *(_process_one(url, args.out, sem, counter) for url in urls)
    )
    elapsed = time.monotonic() - t0

    _safe_print(
        "\n=== batch summary ===\n"
        f"  ok:      {counter['ok']}\n"
        f"  skipped: {counter['skipped']}\n"
        f"  failed:  {counter['failed']}\n"
        f"  total:   {len(urls)}\n"
        f"  time:    {elapsed:.1f}s\n"
    )
    if counter["errors"]:
        _safe_print("Failed URLs (retry with these in a new urls.txt):")
        for url, exc in counter["errors"]:
            _safe_print(f"  {url}  — {exc.__class__.__name__}: {exc}")

    return 0 if counter["failed"] == 0 else 2


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
