"""Prompt assembly with tiktoken token-budget enforcement.

Per FRD §5.4 / CLAUDE.md:
- Prompt order: (1) system prompt, (2) retrieved chunks, (3) history, (4) query.
- Total budget for chunks + history: 6000 tokens (tiktoken, never len()).
- Trim oldest history turns first. Never split a turn (keep both role + content).
- If history trimmed to zero and still over budget: proceed with chunks only.
- User input wrapped in <user_query>…</user_query> (CLAUDE.md security pattern).
- System prompt loaded from file — never inline.
"""

from __future__ import annotations

import logging
from pathlib import Path

import tiktoken

from chat.retrieval import RetrievedChunk
from chat.session import Turn

logger = logging.getLogger(__name__)

# System prompt is read once at module import time (CLAUDE.md).
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"
SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

_ENC: tiktoken.Encoding | None = None


def _enc() -> tiktoken.Encoding:
    global _ENC
    if _ENC is None:
        _ENC = tiktoken.encoding_for_model("gpt-4o")
    return _ENC


def _count(text: str) -> int:
    return len(_enc().encode(text))


# ---------------------------------------------------------------------------
# Chunk context builder
# ---------------------------------------------------------------------------


def _format_chunk(chunk: RetrievedChunk) -> str:
    """Format a single retrieved chunk into a labelled context block."""
    heading = f" — {chunk.section_heading}" if chunk.section_heading else ""
    return (
        f"[Source: {chunk.policy_name}, Page {chunk.page_number}{heading}]\n"
        f"{chunk.chunk_text}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_messages(
    query: str,
    chunks: list[RetrievedChunk],
    history: list[Turn],
    *,
    token_budget: int = 6000,
) -> list[dict[str, str]]:
    """Assemble the messages list for the chat completion API call.

    Returns a list of dicts ready to pass as ``messages=`` to the OpenAI SDK.

    Budget enforcement (FR-RAG-012 / FR-RAG-013):
    - Chunks are included first (highest priority) within the budget.
    - History turns are trimmed from oldest first until they fit.
    - If history is zero and budget still exceeded: chunks are included as-is
      (the LLM context window is large enough for the budget + system prompt +
      query to fit; we never silently drop retrieved content).
    """
    sanitised = _sanitise(query)
    user_block = f"<user_query>{sanitised}</user_query>"

    # Build chunk text block.
    chunks_text = "\n\n".join(_format_chunk(c) for c in chunks)

    # Measure fixed costs (system + chunks + query).
    # History fills the remainder up to token_budget.
    fixed_tokens = _count(SYSTEM_PROMPT) + _count(chunks_text) + _count(user_block)
    history_budget = max(0, token_budget - fixed_tokens)

    # Trim history from oldest end until it fits.
    trimmed_history = list(history)  # copy
    while trimmed_history:
        history_text = "".join(content for _, content in trimmed_history)
        if _count(history_text) <= history_budget:
            break
        trimmed_history.pop(0)  # drop oldest turn

    if len(trimmed_history) < len(history):
        logger.debug(
            "History trimmed: %d → %d turns (budget %d tokens)",
            len(history),
            len(trimmed_history),
            history_budget,
        )

    # Assemble messages.
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    if chunks_text:
        messages.append(
            {"role": "system", "content": f"POLICY EXCERPTS:\n\n{chunks_text}"}
        )

    for role, content in trimmed_history:
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_block})

    return messages


def _sanitise(text: str) -> str:
    """Strip HTML tags, null bytes, and control characters. Cap at 2000 chars."""
    import re

    text = re.sub(r"<[^>]*>", "", text)  # HTML tags
    text = text.replace("\x00", "")  # null bytes
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)  # control chars
    return text[:2000]
