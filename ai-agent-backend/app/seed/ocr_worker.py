"""PaddleOCR worker for image-only PDFs — runs in the .venv-ocr Python.

Why a separate venv: paddlepaddle has no wheels for Python 3.14 (the main
project venv). Calling out to a 3.12 venv just for OCR keeps the main
service untouched.

Usage (invoked as a subprocess from the main venv)::

    .venv-ocr/Scripts/python.exe -m app.seed.ocr_worker <pdf-path> <out-txt>

Input:  local PDF path (downloading is the caller's job; that way the
        main process can reuse its httpx session and referer header).
Output: a UTF-8 text file with one section per page, blank-line
        separated, matching the shape the LLM prompt already expects::

            ## Page 1
            <recognized text>

            ## Page 2
            <recognized text>

Pages are rendered at 200 DPI — high enough for Chinese gearbox spec
tables, but not so high that OCR takes forever. Lang is 'ch' so the
model bundles Chinese + Latin recognition in one pass.

The worker exits 0 on success even if a particular page has no text;
total empty output is logged but not treated as fatal so the caller
can decide what to do.
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import fitz  # pymupdf — renders pages to bitmaps without needing Poppler
from paddleocr import PaddleOCR


def _ocr_pdf(pdf_path: Path, *, dpi: int = 200, lang: str = "ch") -> list[str]:
    """Render each page to PNG, OCR it, return one block of text per page.

    Using PaddleOCR 2.x because 3.x hits an unimplemented PIR/OneDNN op
    on Windows CPU (`ConvertPirAttribute2RuntimeAttribute not support`).
    The 2.x API is `ocr.ocr(img, cls=True)` returning per-image lists of
    `[bbox, (text, conf)]` pairs."""
    # Construct the OCR pipeline once — heavy init (downloads models on first
    # run into ~/.paddleocr/whl/).
    ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    pages_text: list[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            print(f"  ocr page {i}/{len(doc)}", file=sys.stderr, flush=True)
            pix = page.get_pixmap(dpi=dpi)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(pix.tobytes("png"))
                tmp_path = tmp.name
            try:
                results = ocr.ocr(tmp_path, cls=True)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            pages_text.append(_collect_text(results))
    return pages_text


def _collect_text(results) -> str:
    """PaddleOCR 2.x returns `[[[bbox, (text, conf)], ...]]` — one outer
    list per image. We join the texts in reading order; PaddleOCR already
    orders detection boxes top-to-bottom, left-to-right by default."""
    if not results or not results[0]:
        return ""
    lines: list[str] = []
    for entry in results[0]:
        try:
            text = entry[1][0]
        except Exception:  # noqa: BLE001
            continue
        if text and text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python -m app.seed.ocr_worker <pdf-path> <out-txt>", file=sys.stderr)
        return 2
    pdf_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    pages = _ocr_pdf(pdf_path)

    buf = io.StringIO()
    for i, text in enumerate(pages, start=1):
        buf.write(f"\n## Page {i}\n")
        if text:
            buf.write(text)
        buf.write("\n")
    out_path.write_text(buf.getvalue(), encoding="utf-8")

    total = sum(len(p) for p in pages)
    print(f"  ocr done: {len(pages)} pages, {total} chars total", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
