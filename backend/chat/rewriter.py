"""Hinglish query detection and rewrite.

Per FRD FR-RAG-004 / FR-RAG-005:
- Detect Hinglish: query classified as Hinglish if a significant proportion
  of tokens are non-ASCII (i.e. Devanagari / romanised Hindi markers).
  We use a lightweight heuristic — no external library needed.
- Rewrite: a single, cheap LLM call with max_tokens=200, temperature=0.
  The rewritten query is what gets embedded and sent to retrieval.
  The original query is preserved for display in the UI.

Per CLAUDE.md: temperature=0 always, even on the rewrite call.
"""

from __future__ import annotations

import logging
import re

from llm.client import LLMClient

logger = logging.getLogger(__name__)

# Devanagari Unicode block: U+0900–U+097F.
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097f]")

# Romanised Hindi markers — common words / particles that don't appear in
# ordinary English text. A word-token match is enough for our purposes.
_HINDI_MARKERS = frozenset(
    [
        "kya", "hai", "hain", "nahi", "nahin", "kaise", "kab", "kahan",
        "kaun", "kyun", "kyunki", "aur", "lekin", "mujhe", "muje", "mera",
        "meri", "mere", "humara", "humari", "aapka", "aapki", "aapke",
        "hoga", "hogi", "chahiye", "milega", "milegi", "bata", "batao",
        "iske", "uske", "inhe", "unhe", "yahan", "wahan", "abhi", "pehle",
        "baad", "kitna", "kitne", "kitni", "sab", "kuch", "bahut",
    ]
)

# Fraction of word-tokens that must be Hinglish markers to trigger rewrite.
_THRESHOLD = 0.15

_REWRITE_PROMPT = (
    "Rewrite the following in clear English, preserving intent exactly. "
    "Output only the rewritten query:\n\n{query}"
)


def is_hinglish(text: str) -> bool:
    """Return True if ``text`` appears to be a Hinglish (Hindi-English mix) query.

    Checks:
    1. Presence of Devanagari characters — immediate true.
    2. Fraction of lowercase word-tokens matching known Hindi romanisation markers.
    """
    if _DEVANAGARI_RE.search(text):
        return True

    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    if not tokens:
        return False

    hindi_count = sum(1 for t in tokens if t in _HINDI_MARKERS)
    return (hindi_count / len(tokens)) >= _THRESHOLD


async def rewrite_to_english(query: str, llm: LLMClient) -> str:
    """Rewrite ``query`` to plain English via a lightweight LLM call.

    Returns the rewritten query string.  On any error, returns the original
    query so the pipeline can continue (graceful degradation).
    """
    prompt = _REWRITE_PROMPT.format(query=query)
    try:
        response = await llm.client.chat.completions.create(
            model=llm.chat_model,
            temperature=0,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        rewritten = (response.choices[0].message.content or "").strip()
        if rewritten:
            logger.info("Hinglish rewrite: %r → %r", query[:80], rewritten[:80])
            return rewritten
    except Exception:  # noqa: BLE001
        logger.warning("Hinglish rewrite failed — using original query", exc_info=True)

    return query
