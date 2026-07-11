"""Batch embedding via the configured LLM provider.

Per CLAUDE.md:
- Always uses ``text-embedding-3-small`` (1536-dim) — same model for both
  OpenAI and Azure OpenAI; resolved through ``LLMClient.embedding_model``.
- Batches requests to stay within the API's per-request token limit.
- Returns embeddings in the same order as the input texts.
"""

from __future__ import annotations

import logging

from llm.client import LLMClient

logger = logging.getLogger(__name__)

# OpenAI / Azure OpenAI embedding endpoint accepts up to 2048 inputs per call.
# We use a conservative batch size so a single over-large document doesn't
# saturate the context window; 100 chunks ≈ safe ceiling.
_BATCH_SIZE = 100


async def embed_texts(texts: list[str], llm: LLMClient) -> list[list[float]]:
    """Return a 1536-dim embedding for each text in ``texts``.

    Processes in batches of ``_BATCH_SIZE`` and preserves input order.

    Raises ``RuntimeError`` if the API returns a different number of embeddings
    than requested — a mismatch would corrupt the chunk→embedding alignment.
    """
    if not texts:
        return []

    all_embeddings: list[list[float]] = []

    for batch_start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[batch_start : batch_start + _BATCH_SIZE]
        logger.debug(
            "Embedding batch %d–%d / %d",
            batch_start,
            batch_start + len(batch) - 1,
            len(texts),
        )

        response = await llm.client.embeddings.create(
            model=llm.embedding_model,
            input=batch,
        )

        # The API returns embeddings in the same order as the input — verify.
        if len(response.data) != len(batch):
            raise RuntimeError(
                f"Embedding response length mismatch: sent {len(batch)}, "
                f"got {len(response.data)}"
            )

        all_embeddings.extend(item.embedding for item in response.data)

    return all_embeddings
