"""Application configuration.

All settings come from environment variables via pydantic-settings. Secrets have NO
defaults — the app fails loudly at startup if any required value is missing.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env, resolved absolutely so native dev (run from backend/) finds it.
# In Docker, compose injects env vars directly and these take precedence.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Azure OpenAI (secrets: no defaults) ----
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # ---- Azure Blob Storage (secrets: no defaults) ----
    azure_storage_account_name: str
    azure_storage_account_key: str
    azure_storage_container: str = "truboard-policies"

    # ---- Database (secret: no default) ----
    database_url: str

    # ---- OAuth / Auth ----
    oauth_introspect_url: str = ""  # Base URL of the OAuth provider (e.g. https://idp.truboard.com)
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    allowed_origin: str = "http://localhost:5173"
    auth_dev_mode: bool = False
    auth_dev_default_user: str = "admin@truboard.com"

    # ---- RAG / retrieval ----
    rate_limit_queries: int = 30
    rate_limit_window_seconds: int = 3600
    max_upload_size_mb: int = 50
    sas_token_expiry_hours: int = 1
    retrieval_confidence_threshold: float = 0.75
    retrieval_scoped_top_k: int = 3
    retrieval_global_top_k: int = 5
    dedup_cosine_threshold: float = 0.97
    context_token_budget: int = 6000
    llm_max_output_tokens: int = 800
    llm_timeout_seconds: int = 15

    # ---- Embedding dimensionality (text-embedding-3-small) ----
    embedding_dim: int = Field(default=1536)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Raises ValidationError at first call if env is incomplete."""
    return Settings()
