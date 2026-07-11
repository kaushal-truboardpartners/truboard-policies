"""PDF text and table extraction with pdfplumber.

Per CLAUDE.md:
- Tables are atomic — never split across chunks.
- pdfplumber's find_tables() may return overlapping bboxes on complex layouts;
  deduplicate by bbox-area overlap before extraction.
- Returns a list of RawBlock (text or table) in page/position order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

import pdfplumber
import pdfplumber.page

logger = logging.getLogger(__name__)

# Two bboxes overlap if their intersection area exceeds this fraction of the
# smaller bbox's area. Keeps legitimate adjacent tables while dropping true dupes.
_OVERLAP_THRESHOLD = 0.5


@dataclass
class RawBlock:
    """A single extraction unit from one PDF page.

    ``block_type`` is "text" or "table".
    ``content`` is the string representation (text as-is; table as Markdown).
    ``page_number`` is 1-indexed.
    ``bbox`` is (x0, top, x1, bottom) in pdfplumber points — used only during
    extraction for overlap deduplication and is not persisted.
    """

    block_type: Literal["text", "table"]
    content: str
    page_number: int
    bbox: tuple[float, float, float, float] = field(repr=False)


# ---- bbox overlap helpers ---------------------------------------------------


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, top, x1, bottom = bbox
    return max(0.0, x1 - x0) * max(0.0, bottom - top)


def _intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    ix0 = max(a[0], b[0])
    itop = max(a[1], b[1])
    ix1 = min(a[2], b[2])
    ibottom = min(a[3], b[3])
    return max(0.0, ix1 - ix0) * max(0.0, ibottom - itop)


def _overlaps(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    inter = _intersection_area(a, b)
    if inter == 0:
        return False
    smaller = min(_bbox_area(a), _bbox_area(b))
    return smaller > 0 and (inter / smaller) > _OVERLAP_THRESHOLD


def _dedup_bboxes(
    tables: list[pdfplumber.page.Table],
) -> list[pdfplumber.page.Table]:
    """Drop tables whose bbox substantially overlaps an already-accepted table."""
    accepted: list[pdfplumber.page.Table] = []
    for tbl in tables:
        if tbl.bbox is None:
            continue
        if any(_overlaps(tbl.bbox, kept.bbox) for kept in accepted if kept.bbox):
            logger.debug("Dropping overlapping table bbox %s", tbl.bbox)
            continue
        accepted.append(tbl)
    return accepted


# ---- table → Markdown -------------------------------------------------------


def _table_to_markdown(rows: list[list[str | None]]) -> str:
    """Convert a list-of-rows (from pdfplumber) to a GFM Markdown table string.

    Empty cells become an empty string. The first row is the header.
    """
    if not rows:
        return ""

    def _cell(v: str | None) -> str:
        return (v or "").replace("|", "\\|").replace("\n", " ").strip()

    header = [_cell(c) for c in rows[0]]
    separator = ["---"] * len(header)
    body = [[_cell(c) for c in row] for row in rows[1:]]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in body:
        # Pad short rows so column count is consistent.
        while len(row) < len(header):
            row.append("")
        lines.append("| " + " | ".join(row[: len(header)]) + " |")

    return "\n".join(lines)


# ---- per-page extraction ----------------------------------------------------


def _extract_page(page: pdfplumber.page.Page, page_number: int) -> list[RawBlock]:
    """Extract text and tables from a single page.

    Strategy:
    1. Find and dedup tables; record their bboxes.
    2. Extract text from the page area *outside* all table bboxes.
    3. Return text block first, then table blocks (both in page order).
    """
    tables = _dedup_bboxes(page.find_tables())

    # Mask out table regions so their cells don't bleed into the text block.
    if tables:
        # pdfplumber.Page.filter() keeps only chars/words outside the table bboxes.
        table_bboxes = [t.bbox for t in tables if t.bbox]
        page_outside = page.filter(
            lambda obj, bboxes=table_bboxes: not any(
                obj.get("x0", 0) >= b[0]
                and obj.get("x1", 0) <= b[2]
                and obj.get("top", 0) >= b[1]
                and obj.get("bottom", 0) <= b[3]
                for b in bboxes
            )
        )
    else:
        page_outside = page

    blocks: list[RawBlock] = []

    # Text block (may be empty on image-only pages).
    text = (page_outside.extract_text() or "").strip()
    if text:
        page_bbox: tuple[float, float, float, float] = (
            page.bbox[0],
            page.bbox[1],
            page.bbox[2],
            page.bbox[3],
        )
        blocks.append(
            RawBlock(
                block_type="text",
                content=text,
                page_number=page_number,
                bbox=page_bbox,
            )
        )

    # Table blocks.
    for tbl in tables:
        rows = tbl.extract()
        if not rows:
            continue
        md = _table_to_markdown(rows)
        if md:
            blocks.append(
                RawBlock(
                    block_type="table",
                    content=md,
                    page_number=page_number,
                    bbox=tbl.bbox or (0.0, 0.0, 0.0, 0.0),
                )
            )

    return blocks


# ---- public API -------------------------------------------------------------


def extract_pdf(pdf_bytes: bytes) -> list[RawBlock]:
    """Extract all text and table blocks from ``pdf_bytes``.

    Returns blocks in document order (page 1 text, page 1 tables, page 2 …).
    Raises ``ValueError`` if pdfplumber cannot open the bytes.
    """
    import io

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            blocks: list[RawBlock] = []
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    blocks.extend(_extract_page(page, i))
                except Exception:  # noqa: BLE001
                    logger.warning("Page %d extraction failed — skipping", i, exc_info=True)
            return blocks
    except Exception as exc:
        raise ValueError(f"Failed to open PDF: {exc}") from exc
