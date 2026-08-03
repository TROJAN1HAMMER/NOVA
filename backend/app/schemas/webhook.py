"""
NOVA — Webhook Schemas
"""

import uuid
from typing import Optional

from pydantic import BaseModel


class WebhookAckResponse(BaseModel):
    status: str  # "scan_queued" | "ignored" | "ping_ok"
    message: str
    scan_job_id: Optional[uuid.UUID] = None
    repository_id: Optional[uuid.UUID] = None
