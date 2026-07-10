"""Smoke-test the configured LLM provider end to end.

Provider-agnostic: it exercises whatever LLM_PROVIDER points at (openai for dev,
azure for prod), so the SAME check validates the dev key today and the Azure
resource later. Run after setting OPENAI_API_KEY (dev) or the Azure creds (prod):

    cd backend && python scripts/smoke_llm.py

Passing here means the provider abstraction, credentials, model names, and the
1536-dim embedding contract all line up — safe to start ingestion.
"""

import asyncio
import sys

from config import get_settings
from llm.client import build_llm_client


async def main() -> int:
    settings = get_settings()
    llm = build_llm_client(settings)
    print(f"Provider : {llm.provider}")
    print(f"Chat     : {llm.chat_model}")
    print(f"Embedding: {llm.embedding_model}\n")

    try:
        # 1. Chat — temperature=0 mirrors the production invariant.
        chat = await llm.client.chat.completions.create(
            model=llm.chat_model,
            temperature=0,
            max_tokens=5,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
        )
        reply = (chat.choices[0].message.content or "").strip()
        print(f"[chat] ok → {reply!r}")

        # 2. Embedding — MUST be embedding_dim (1536) to match the pgvector column.
        emb = await llm.client.embeddings.create(
            model=llm.embedding_model,
            input=["hello from truboard"],
        )
        dim = len(emb.data[0].embedding)
        print(f"[embed] ok → dim={dim}")
        if dim != settings.embedding_dim:
            print(
                f"\nFAIL: embedding dim {dim} != configured {settings.embedding_dim}. "
                "Wrong model/deployment — stop before ingesting.",
                file=sys.stderr,
            )
            return 1
    finally:
        await llm.aclose()

    print("\nAll checks passed. Ingestion is safe to run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
