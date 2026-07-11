"""Text chunking pipeline.

Per CLAUDE.md / FRD:
- Text blocks: recursive character splitting, 800 token target / 120 token overlap.
- Table blocks: atomic — one table → one chunk, never split.
- Token counting always via tiktoken, never len() (CLAUDE.md invariant).
- Each chunk carries: chunk_index, chunk_type, page_number, section_heading.
- ``section_heading`` is inferred from the last H1/H2-style line seen before the chunk.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

import tiktoken

from admin.ingestion.extractor import RawBlock

logger = logging.getLogger(__name__)

# Token budget per chunk (target) and overlap for text splits.
_CHUNK_TOKENS = 800
_OVERLAP_TOKENS = 120

# Heading heuristic: a short capitalised line (≤ 80 chars) not ending in punctuation.
_HEADING_RE = re.compile(r"^[A-Z][^\n]{0,78}[^.!?,;:]$")

_ENC: tiktoken.Encoding | None = None


def _enc() -> tiktoken.Encoding:
    global _ENC
    if _ENC is None:
        _ENC = tiktoken.encoding_for_model("gpt-4o")
    return _ENC


def _count_tokens(text: str) -> int:
    return len(_enc().encode(text))


def _decode_tokens(token_ids: list[int]) -> str:
    return _enc().decode(token_ids)


# ---- heading inference ------------------------------------------------------


def _infer_heading(text: str) -> str | None:
    """Return the last heading-like line from ``text``, or None."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line and _HEADING_RE.match(line):
            return line
    return None


# ---- recursive text splitter ------------------------------------------------


def _split_text(
    text: str,
    target_tokens: int = _CHUNK_TOKENS,
    overlap_tokens: int = _OVERLAP_TOKENS,
) -> list[str]:
    """Recursively split ``text`` into token-bounded chunks with overlap.

    Split order: paragraph → sentence → word boundary.
    Overlap is achieved by carrying the tail of the previous chunk into the next.
    """
    tokens = _enc().encode(text)
    if len(tokens) <= target_tokens:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + target_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = _decode_tokens(chunk_tokens).strip()
        if chunk_text:
            chunks.append(chunk_text)
        if end >= len(tokens):
            break
        # Advance by (target - overlap) so the next chunk re-reads the tail.
        step = target_tokens - overlap_tokens
        start += max(step, 1)

    return chunks


# ---- public API -------------------------------------------------------------


@dataclass
class Chunk:
    """A single chunk ready for embedding and DB insertion."""

    chunk_index: int
    chunk_type: Literal["text", "table"]
    page_number: int
    section_heading: str | None
    text: str  # the text to embed and store


def build_chunks(blocks: list[RawBlock]) -> list[Chunk]:
    """Convert extractor output into final embedding-ready chunks.

    Processing order preserves document reading order.  Table blocks become a
    single atomic chunk each; text blocks are recursively split.

    ``chunk_index`` is global across the document (0-based monotone increment).
    """
    chunks: list[Chunk] = []
    last_heading: str | None = None
    idx = 0

    for block in blocks:
        if block.block_type == "table":
            # Tables are atomic — one table → one chunk (CLAUDE.md).
            chunks.append(
                Chunk(
                    chunk_index=idx,
                    chunk_type="table",
                    page_number=block.page_number,
                    section_heading=last_heading,
                    text=block.content,
                )
            )
            idx += 1

        else:
            # Update heading context from this text block.
            h = _infer_heading(block.content)
            if h:
                last_heading = h

            splits = _split_text(block.content)
            if not splits:
                logger.debug("Page %d text block produced no chunks (empty)", block.page_number)
                continue

            for piece in splits:
                chunks.append(
                    Chunk(
                        chunk_index=idx,
                        chunk_type="text",
                        page_number=block.page_number,
                        section_heading=last_heading,
                        text=piece,
                    )
                )
                idx += 1

    logger.info("build_chunks: %d raw blocks → %d chunks", len(blocks), len(chunks))
    return chunks
