"""Pydantic response schemas for the documents API."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentListItem(BaseModel):
    """One row in GET /api/documents — alphabetical, active documents only."""

    id: uuid.UUID
    policy_name: str
    version: int


class DocumentUrlResponse(BaseModel):
    """GET /api/documents/{id}/url — a fresh, short-lived read-only SAS URL."""

    url: str
    expires_at: datetime
