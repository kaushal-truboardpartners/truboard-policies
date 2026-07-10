"""Application configuration.

All settings come from environment variables via pydantic-settings. Secrets have NO
defaults — the app fails loudly at startup if any required value is missing.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    # ---- LLM provider selection ----
    # "openai"  = vanilla OpenAI (platform.openai.com) — used for dev on a personal key.
    # "azure"   = Azure OpenAI — production.
    # Both use identical models (gpt-4o, text-embedding-3-small, 1536-dim), so switching
    # is a config flip + one reindex_all.py run. Only the ACTIVE provider's creds are
    # validated (see _validate_active_provider) — the other may be left blank.
    llm_provider: Literal["openai", "azure"] = "openai"

    # ---- Vanilla OpenAI (dev) ----
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # ---- Azure OpenAI (production) ----
    # Optional at startup: only required when llm_provider == "azure".
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_deployment: str = "gpt-4o"  # deployment name == model name by convention
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

    @model_validator(mode="after")
    def _validate_active_provider(self) -> "Settings":
        """Fail loudly at startup if the SELECTED provider's credentials are missing.

        We can't make both providers' secrets unconditionally required (dev runs on
        OpenAI alone, with no Azure OpenAI resource yet), so validation is scoped to
        whichever provider is active.
        """
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("llm_provider='openai' requires OPENAI_API_KEY to be set")
        if self.llm_provider == "azure" and not (
            self.azure_openai_endpoint and self.azure_openai_api_key
        ):
            raise ValueError(
                "llm_provider='azure' requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Raises ValidationError at first call if env is incomplete."""
    return Settings()
