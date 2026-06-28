"""Test fixtures. Sets dummy env vars before any app import so settings validation passes
without real credentials."""

import os

# Must run at import time, before `config`/`main` are imported by test modules.
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "teststorage")
# Real Azure storage keys are base64; SAS signing decodes the key, so keep it valid base64.
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_KEY", "dGVzdC1zdG9yYWdlLWtleQ==")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("AUTH_DEV_MODE", "true")
os.environ.setdefault("OAUTH_INTROSPECT_URL", "https://test-idp.example.com")
os.environ.setdefault("OAUTH_CLIENT_ID", "test-client")
os.environ.setdefault("OAUTH_CLIENT_SECRET", "test-secret")
