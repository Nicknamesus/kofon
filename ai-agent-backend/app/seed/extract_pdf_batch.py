"""Batch PDF extractor — for URLs whose HTML text isn't rich enough.

Kofon's product detail pages render most spec tables as multi-column HTML
that flattens into noise; the HTML batch (`extract_url_batch`) often gets
back `None` from DeepSeek for these and leaves an `<stem>.error.txt`
behind. Every such page does, however, link to a PDF datasheet (often via
`pdfPreview('…')` JS rather than a plain `<a href>`), and the PDF table
extraction in `extract_pdf` recovers the data cleanly.

This script:

    1. Reads either a URL file (one URL per line) or scans a drafts
       directory for `*.error.txt` files and reads their first line.
    2. Fetches each page's HTML and pulls the first PDF URL it can find
       (both real `<a href="…pdf">` and `pdfPreview('…pdf')` links).
    3. Groups URLs by PDF URL — many pages share one datasheet, so we
       only extract each PDF once.
    4. Calls `extract_pdf.extract_pdf` per unique PDF.
    5. Writes one draft pair per PDF under `seed/drafts/`, keyed by a
       short ASCII slug derived from the PDF filename. Embeds the list
       of source URL stems in the YAML header for traceability.
    6. Removes the corresponding `*.error.txt` files on success.

CLI::

    python -m app.seed.extract_pdf_batch --errors-dir seed/drafts
    python -m app.seed.extract_pdf_batch urls.txt --concurrency 3

Same review-then-promote workflow as the other batch extractors — the
loader only reads `seed/product_types/` + `seed/products/`, so drafts
stay inert until a human moves them.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
import traceback
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from app.seed.extract_pdf import extract_pdf
from app.seed.extract_url import ProductTypeDraft, _safe_print, _yaml_dump


# ---------------- HTML PDF discovery ----------------


_PDF_PREVIEW_RE = re.compile(r"pdfPreview\(\s*['\"]([^'\"]+\.pdf)['\"]", re.IGNORECASE)
_PDF_HREF_RE = re.compile(r"""href=['"]([^'"]+\.pdf)['"]""", re.IGNORECASE)


async def _find_pdf_url(client: httpx.AsyncClient, page_url: str) -> str | None:
    """Fetch a product page, return the first PDF datasheet URL on it.

    Looks at both `<a href="…pdf">` and the JS `pdfPreview('…pdf')` calls
    Kofon uses on its newer product pages. Returns None if no PDF link
    is on the page (page is likely not a product detail, or has only
    images / CAD files)."""
    resp = await client.get(page_url)
    resp.raise_for_status()
    html = resp.text
    for rx in (_PDF_PREVIEW_RE, _PDF_HREF_RE):
        m = rx.search(html)
        if m:
            return m.group(1)
    return None


# ---------------- naming ----------------


def _slug_from_pdf_url(pdf_url: str) -> str:
    """Derive an ASCII filename stem from a PDF URL.

    The PDF filenames are mostly Chinese (e.g. `1f系列精密行星减速机.pdf`)
    so we strip them to the leading ASCII tokens plus an MD5 short hash
    to keep things unique. Examples:

        '…/1f系列精密行星减速机.pdf'            -> 'pdf_1f_a1b2c3'
        '…/2k系列精密行星减速机 (1).pdf'         -> 'pdf_2k_1_d4e5f6'
        '…/谐波减速机.pdf'                       -> 'pdf_xxxxxx'        (no ascii lead)
    """
    name = Path(unquote(urlparse(pdf_url).path)).stem
    ascii_part = "".join(
        c if (c.isascii() and (c.isalnum() or c in " _-()")) else " " for c in name
    )
    ascii_part = re.sub(r"[\s()]+", "_", ascii_part).strip("_").lower()
    ascii_part = re.sub(r"_+", "_", ascii_part)
    # Stable suffix so different PDFs with the same ASCII prefix don't collide.
    import hashlib
    suffix = hashlib.md5(pdf_url.encode("utf-8")).hexdigest()[:6]
    if ascii_part:
        return f"pdf_{ascii_part}_{suffix}"
    return f"pdf_{suffix}"


def _stem_for(url: str) -> str:
    parsed = urlparse(url)
    return Path(parsed.path).stem or parsed.netloc


# ---------------- writer ----------------


def _write_pdf_draft(
    draft: ProductTypeDraft,
    out_dir: Path,
    *,
    slug: str,
    pdf_url: str,
    source_url_stems: list[str],
) -> tuple[Path, Path]:
    """Write a draft keyed by `slug` rather than the LLM-chosen code.

    Reason: many catalog page URLs (1, 2, 3, …) all map to one PDF and
    one product family. Keying by PDF gives us one draft per family
    (matching the seed/<...>/r_series.yaml shape), not one per page URL.
    The LLM-chosen `product_type_code` is still embedded inside the
    YAML body so the human reviewer can adopt it during promotion.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    pt_payload = {
        "code": draft.product_type_code,
        "name": draft.product_type_name,
        "family": draft.family,
        "description": draft.description,
        "spec_schema": {
            k: v.model_dump(exclude_none=True) for k, v in draft.spec_schema.items()
        },
    }
    products_payload = {
        "product_type_code": draft.product_type_code,
        "products": [p.model_dump(exclude_none=True) for p in draft.products],
    }

    pt_path = out_dir / f"{slug}.product_type.yaml"
    p_path = out_dir / f"{slug}.products.yaml"

    stems_joined = ", ".join(source_url_stems)
    header_common = (
        f"# DRAFT — extracted from PDF: {pdf_url}\n"
        f"# Source product pages (stems): {stems_joined}\n"
        f"# LLM-chosen code: {draft.product_type_code}\n"
        f"# Review, then promote to seed/product_types/<code>.yaml + seed/products/<code>.yaml\n"
    )
    if draft.notes_for_reviewer:
        header_common += f"# Notes: {draft.notes_for_reviewer}\n"

    pt_path.write_text(header_common + _yaml_dump(pt_payload), encoding="utf-8")
    p_path.write_text(header_common + _yaml_dump(products_payload), encoding="utf-8")
    return pt_path, p_path


# ---------------- pipeline ----------------


async def _gather_pdf_map(
    urls: list[str], *, concurrency: int
) -> tuple[dict[str, list[str]], list[tuple[str, Exception]]]:
    """url → pdf_url; returns (pdf_url → [url stems], failures)."""
    sem = asyncio.Semaphore(concurrency)
    pdf_to_stems: dict[str, list[str]] = defaultdict(list)
    failures: list[tuple[str, Exception]] = []
    not_found: list[str] = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "kofon-seed-extractor/0.1"},
    ) as client:
        async def one(url: str) -> None:
            stem = _stem_for(url)
            async with sem:
                try:
                    pdf = await _find_pdf_url(client, url)
                except Exception as exc:  # noqa: BLE001
                    failures.append((url, exc))
                    return
            if pdf is None:
                not_found.append(stem)
                return
            pdf_to_stems[pdf].append(stem)

        await asyncio.gather(*(one(u) for u in urls))

    for stem in not_found:
        failures.append((stem, RuntimeError("no PDF link on page")))
    return pdf_to_stems, failures


async def _extract_one_pdf(
    pdf_url: str,
    stems: list[str],
    out_dir: Path,
    counter: dict,
    *,
    force: bool = False,
) -> None:
    slug = _slug_from_pdf_url(pdf_url)
    pt_path = out_dir / f"{slug}.product_type.yaml"
    p_path = out_dir / f"{slug}.products.yaml"
    ocr_cache = out_dir / ".ocr_cache" / f"{slug}.ocr.txt"

    if not force and pt_path.exists() and p_path.exists():
        counter["skipped"] += 1
        _safe_print(f"[skip ] {slug}  ({len(stems)} URL stems, drafts already exist)")
        # Still remove error files since the work is already done.
        for stem in stems:
            err = out_dir / f"{stem}.error.txt"
            if err.exists():
                err.unlink()
        return

    t0 = time.monotonic()
    try:
        draft = await extract_pdf(pdf_url, ocr_cache_path=ocr_cache)
    except Exception as exc:  # noqa: BLE001
        counter["failed"] += 1
        counter["errors"].append((pdf_url, exc))
        err_path = out_dir / f"{slug}.pdf_error.txt"
        err_path.write_text(
            f"PDF URL: {pdf_url}\n"
            f"Source URL stems: {', '.join(stems)}\n"
            f"Error: {exc.__class__.__name__}: {exc}\n\n"
            + traceback.format_exc(),
            encoding="utf-8",
        )
        _safe_print(f"[FAIL] {slug}  — {exc.__class__.__name__}: {exc}")
        return

    _write_pdf_draft(
        draft, out_dir, slug=slug, pdf_url=pdf_url, source_url_stems=sorted(stems, key=_natural_key),
    )
    # Remove the stale *.error.txt files now that we have a draft covering them.
    for stem in stems:
        err = out_dir / f"{stem}.error.txt"
        if err.exists():
            err.unlink()

    elapsed = time.monotonic() - t0
    counter["ok"] += 1
    _safe_print(
        f"[ok  ] {slug}  ({draft.product_type_code}, "
        f"{len(draft.products)} SKUs, covers {len(stems)} pages, {elapsed:.1f}s)"
    )


def _natural_key(s: str) -> tuple:
    """Sort '2' before '10' when stems are numeric."""
    parts = re.split(r"(\d+)", s)
    return tuple(int(p) if p.isdigit() else p for p in parts)


def _read_url_file(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def _read_errors_dir(errors_dir: Path) -> list[str]:
    """First line of each *.error.txt is `URL: <url>`. Pull that out."""
    out: list[str] = []
    for path in sorted(errors_dir.glob("*.error.txt")):
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
        if first.startswith("URL:"):
            out.append(first.split(":", 1)[1].strip())
    return out


# ---------------- CLI ----------------


async def _amain() -> int:
    parser = argparse.ArgumentParser(
        description="Batch-extract PDF datasheets linked from Kofon product pages."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "url_file",
        nargs="?",
        type=Path,
        help="Plain text file with one product page URL per line.",
    )
    src.add_argument(
        "--errors-dir",
        type=Path,
        default=None,
        help="Scan this dir for *.error.txt; use the URL from the first line.",
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
        help="Parallel PDF extractions (default 4).",
    )
    parser.add_argument(
        "--html-concurrency",
        type=int,
        default=8,
        help="Parallel HTML fetches when mapping URLs to PDFs (default 8).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even when draft files already exist for the PDF.",
    )
    args = parser.parse_args()

    if args.errors_dir:
        if not args.errors_dir.is_dir():
            _safe_print(f"--errors-dir {args.errors_dir} doesn't exist.")
            return 1
        urls = _read_errors_dir(args.errors_dir)
    else:
        urls = _read_url_file(args.url_file)
    if not urls:
        _safe_print("No URLs to process.")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    _safe_print(f"Mapping {len(urls)} URLs → PDFs (concurrency {args.html_concurrency})…")
    t0 = time.monotonic()
    pdf_to_stems, map_failures = await _gather_pdf_map(
        urls, concurrency=args.html_concurrency
    )
    _safe_print(
        f"  found {len(pdf_to_stems)} unique PDFs covering "
        f"{sum(len(v) for v in pdf_to_stems.values())} pages; "
        f"{len(map_failures)} unmappable.\n"
    )
    for url_or_stem, exc in map_failures:
        _safe_print(f"  [unmappable] {url_or_stem} — {exc}")

    _safe_print(f"\nExtracting {len(pdf_to_stems)} PDFs (concurrency {args.concurrency})…")
    counter: dict = {"ok": 0, "skipped": 0, "failed": 0, "errors": []}
    sem = asyncio.Semaphore(args.concurrency)

    async def gated(pdf_url: str, stems: list[str]) -> None:
        async with sem:
            await _extract_one_pdf(
                pdf_url, stems, args.out, counter, force=args.force
            )

    await asyncio.gather(
        *(gated(pdf, stems) for pdf, stems in pdf_to_stems.items())
    )
    elapsed = time.monotonic() - t0

    _safe_print(
        "\n=== batch summary ===\n"
        f"  PDFs ok:      {counter['ok']}\n"
        f"  PDFs skipped: {counter['skipped']}\n"
        f"  PDFs failed:  {counter['failed']}\n"
        f"  unmappable:   {len(map_failures)}\n"
        f"  total time:   {elapsed:.1f}s\n"
    )
    if counter["errors"]:
        _safe_print("Failed PDFs:")
        for pdf, exc in counter["errors"]:
            _safe_print(f"  {pdf}  — {exc.__class__.__name__}: {exc}")

    return 0 if counter["failed"] == 0 and not map_failures else 2


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
