"""
NOVA — System Settings Schemas
Pydantic DTOs for reading, updating, and resetting system configuration & RAG hyperparameters.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SystemSettingsResponse(BaseModel):
    settings: dict[str, Any]


class SystemSettingsUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(min_length=1)


class SingleSettingUpdateRequest(BaseModel):
    value: Any


class SingleSettingResponse(BaseModel):
    key: str
    value: Any


class SystemSettingsResetRequest(BaseModel):
    keys: Optional[list[str]] = None
