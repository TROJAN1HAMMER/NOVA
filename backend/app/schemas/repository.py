"""
NOVA — Repository Pydantic Schemas
"""

import uuid
from typing import Optional

from pydantic import BaseModel

from app.models.enums import RepoProviderType


class RepositoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: Optional[str] = None
    provider: RepoProviderType
    default_branch: Optional[str] = None
    scheduled_scan_enabled: bool = False

    model_config = {"from_attributes": True}


class ScheduledScanUpdateRequest(BaseModel):
    enabled: bool
