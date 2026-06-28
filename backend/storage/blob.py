"""Azure Blob Storage service.

Wraps the async Azure Blob client for upload I/O and mints fresh, read-only SAS
URLs for reads. Per CLAUDE.md: only `blob_key` is persisted — SAS tokens are
never stored and are generated fresh (1h, read-only) on every request.

`generate_sas_url` is synchronous: `generate_blob_sas` is pure local crypto with
no network call and needs no client instance. Only `upload_pdf` does network I/O,
so it uses the async client (`azure.storage.blob.aio`).
"""

import logging
from datetime import UTC, datetime, timedelta

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobSasPermissions, ContentSettings, generate_blob_sas
from azure.storage.blob.aio import BlobServiceClient
from fastapi import Request

from config import Settings

logger = logging.getLogger(__name__)


class BlobUploadError(Exception):
    """A blob upload failed. The underlying Azure error is logged, not surfaced —
    callers translate this into a safe, generic client-facing message."""


class BlobStorageService:
    """Async Azure Blob client wrapper for the policies container."""

    def __init__(self, settings: Settings) -> None:
        if not (
            settings.azure_storage_account_name
            and settings.azure_storage_account_key
            and settings.azure_storage_container
        ):
            raise ValueError("Azure Storage configuration is missing")

        self._account = settings.azure_storage_account_name
        self._key = settings.azure_storage_account_key
        self._container = settings.azure_storage_container
        self._sas_expiry_hours = settings.sas_token_expiry_hours

        connection_string = (
            "DefaultEndpointsProtocol=https;"
            f"AccountName={self._account};"
            f"AccountKey={self._key};"
            "EndpointSuffix=core.windows.net"
        )
        self._client = BlobServiceClient.from_connection_string(connection_string)
        self._container_client = self._client.get_container_client(self._container)
        self._container_ready = False

    async def _ensure_container(self) -> None:
        """Create the (private) container if it doesn't exist. Runs once per process."""
        if self._container_ready:
            return
        try:
            await self._container_client.create_container()
            logger.info("Created blob container %s", self._container)
        except ResourceExistsError:
            pass
        self._container_ready = True

    async def upload_pdf(self, content: bytes, blob_key: str) -> str:
        """Upload PDF bytes to ``blob_key``. Returns the base blob URL (no SAS).

        ``overwrite=False`` — blob_key embeds a UUID, so a collision means a bug,
        not a re-upload; fail loudly rather than clobber.

        Raises ``BlobUploadError`` on any storage failure (full detail logged).
        """
        blob_client = self._container_client.get_blob_client(blob_key)
        try:
            await self._ensure_container()
            await blob_client.upload_blob(
                content,
                overwrite=False,
                content_settings=ContentSettings(content_type="application/pdf"),
            )
        except Exception as exc:  # noqa: BLE001 — wrap any Azure SDK error uniformly
            logger.error("Failed to upload %s to Azure Blob Storage: %s", blob_key, exc)
            raise BlobUploadError(blob_key) from exc

        logger.info("Uploaded %s to Azure Blob Storage", blob_key)
        return blob_client.url

    def generate_sas_url(self, blob_key: str) -> tuple[str, datetime]:
        """Mint a fresh, read-only SAS URL for ``blob_key``.

        Returns ``(url, expires_at)``. Never persisted (CLAUDE.md).
        """
        expires_at = datetime.now(UTC) + timedelta(hours=self._sas_expiry_hours)
        sas_token = generate_blob_sas(
            account_name=self._account,
            container_name=self._container,
            blob_name=blob_key,
            account_key=self._key,
            permission=BlobSasPermissions(read=True),
            expiry=expires_at,
        )
        url = (
            f"https://{self._account}.blob.core.windows.net/"
            f"{self._container}/{blob_key}?{sas_token}"
        )
        return url, expires_at

    async def close(self) -> None:
        await self._client.close()


def get_blob_service(request: Request) -> BlobStorageService:
    """FastAPI dependency: the process-wide blob service created in the app lifespan."""
    return request.app.state.blob_service
