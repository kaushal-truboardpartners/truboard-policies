"""Pydantic response schemas for the admin API."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel


class UploadResultItem(BaseModel):
    """One file's outcome in POST /api/admin/upload.

    Files are processed independently — a failure on one ('error') does not block
    the others. Success fields (id/policy_name/version) are set when status is
    'uploaded'; `error` carries the reason when status is 'error'.
    """

    filename: str
    status: Literal["uploaded", "error"]
    id: uuid.UUID | None = None
    policy_name: str | None = None
    version: int | None = None
    error: str | None = None


class JobEnqueuedResponse(BaseModel):
    """Returned immediately after enqueuing an ingestion job."""

    job_id: uuid.UUID
    document_id: uuid.UUID
    status: str = "queued"


class PolicyListItem(BaseModel):
    """One row returned by GET /api/admin/policies."""

    id: uuid.UUID
    policy_name: str
    version: int
    is_deleted: bool


class ReplaceResultItem(BaseModel):
    """Response from POST /api/admin/policies/{id}/replace."""

    old_id: uuid.UUID
    new_id: uuid.UUID
    policy_name: str
    version: int
    job_id: uuid.UUID
    status: str = "queued"
