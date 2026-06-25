"""Test fixtures. Sets dummy env vars before any app import so settings validation passes
without real Azure credentials."""

import os

# Must run at import time, before `config`/`main` are imported by test modules.
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "teststorage")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_KEY", "test-storage-key")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)
os.environ.setdefault("AUTH_DEV_MODE", "true")
