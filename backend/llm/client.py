"""Provider-agnostic LLM client.

The rest of the app (embedder, chat pipeline) talks ONLY to `LLMClient` — never to
`openai` SDK classes directly. That keeps the OpenAI ⇄ Azure OpenAI swap a one-line
config change (`LLM_PROVIDER`), exactly as planned for the dev→prod transition.

Both providers expose the same async surface (`.chat.completions.create`,
`.embeddings.create`) and the same models (gpt-4o, text-embedding-3-small, 1536-dim),
so call sites only need the resolved model/deployment name, which this wrapper holds.
"""

from dataclasses import dataclass

from openai import AsyncAzureOpenAI, AsyncOpenAI

from config import Settings, get_settings

# Union of the two async client types — identical interface, different construction.
AsyncOpenAIClient = AsyncOpenAI | AsyncAzureOpenAI


@dataclass(frozen=True, slots=True)
class LLMClient:
    """Thin holder: the async SDK client plus the model names to pass at call time.

    `chat_model` / `embedding_model` abstract the OpenAI "model name" vs Azure
    "deployment name" distinction — call sites pass them verbatim and stay
    provider-agnostic:

        resp = await llm.client.chat.completions.create(
            model=llm.chat_model, temperature=0, messages=[...],
        )
        emb = await llm.client.embeddings.create(
            model=llm.embedding_model, input=[...],
        )
    """

    client: AsyncOpenAIClient
    chat_model: str
    embedding_model: str
    provider: str

    async def aclose(self) -> None:
        await self.client.close()


def build_llm_client(settings: Settings | None = None) -> LLMClient:
    """Construct the LLMClient for the configured provider.

    Used both in the FastAPI lifespan (request path) and inside ingestion
    BackgroundTasks (which build their own, since the request-scoped one isn't
    available there). Credentials are already validated at settings load
    (`Settings._validate_active_provider`).
    """
    settings = settings or get_settings()

    if settings.llm_provider == "azure":
        client: AsyncOpenAIClient = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=settings.llm_timeout_seconds,
        )
        return LLMClient(
            client=client,
            chat_model=settings.azure_openai_deployment,
            embedding_model=settings.azure_openai_embedding_deployment,
            provider="azure",
        )

    # Default: vanilla OpenAI (dev).
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
    )
    return LLMClient(
        client=client,
        chat_model=settings.openai_model,
        embedding_model=settings.openai_embedding_model,
        provider="openai",
    )


from fastapi import Request

def get_llm_client(request: Request) -> LLMClient:
    """FastAPI dependency: the process-wide LLM client created in the app lifespan."""
    return request.app.state.llm_client
