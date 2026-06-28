"""Pydantic response schemas for the admin API."""

import uuid
from typing import Literal

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
