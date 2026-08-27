"""
NOVA — System Settings Endpoints
Administrative endpoints for reading, updating, and resetting dynamic platform settings & RAG hyperparameters.
Protected by Permission.ADMIN_WRITE with audit logging for all mutations.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.auth.permissions import Permission, require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.settings import (
    SingleSettingResponse,
    SingleSettingUpdateRequest,
    SystemSettingsResetRequest,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
)
from app.services.audit.audit_logger import log_action
from app.services.settings_service import DEFAULT_SETTINGS, settings_service

router = APIRouter()


@router.get("/settings", response_model=SystemSettingsResponse, summary="Get System Settings")
async def get_system_settings(
    _current_user: Annotated[User, Depends(require_permission(Permission.ADMIN_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemSettingsResponse:
    """Retrieve all resolved system settings (factory defaults overlaid with database customizations)."""
    settings = await settings_service.get_settings(db)
    return SystemSettingsResponse(settings=settings)


@router.get("/settings/{key}", response_model=SingleSettingResponse, summary="Get Single Setting")
async def get_single_setting(
    key: str,
    _current_user: Annotated[User, Depends(require_permission(Permission.ADMIN_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SingleSettingResponse:
    """Retrieve a single system setting value by its configuration key."""
    val = await settings_service.get_setting(db, key, default=None)
    if val is None and key not in DEFAULT_SETTINGS:
        raise NotFoundError(f"Setting '{key}' not found")
    return SingleSettingResponse(key=key, value=val)


@router.put("/settings", response_model=SystemSettingsResponse, summary="Bulk Update System Settings")
async def update_system_settings(
    payload: SystemSettingsUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_permission(Permission.ADMIN_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemSettingsResponse:
    """Bulk update or insert multiple system settings."""
    settings = await settings_service.update_settings(db, payload.settings)
    await log_action(
        user=current_user,
        action="settings.bulk_updated",
        resource_type="system_settings",
        resource_id="bulk",
        request=request,
        details={"updated_keys": list(payload.settings.keys())},
    )
    return SystemSettingsResponse(settings=settings)


@router.put("/settings/{key}", response_model=SingleSettingResponse, summary="Update Single Setting")
async def update_single_setting(
    key: str,
    payload: SingleSettingUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(require_permission(Permission.ADMIN_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SingleSettingResponse:
    """Update or insert a single system setting by key."""
    val = await settings_service.update_setting(db, key, payload.value)
    await log_action(
        user=current_user,
        action="settings.key_updated",
        resource_type="system_settings",
        resource_id=key,
        request=request,
        details={"key": key, "value": payload.value},
    )
    return SingleSettingResponse(key=key, value=val)


@router.post("/settings/reset", response_model=SystemSettingsResponse, summary="Reset System Settings")
async def reset_system_settings(
    request: Request,
    current_user: Annotated[User, Depends(require_permission(Permission.ADMIN_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: Optional[SystemSettingsResetRequest] = None,
) -> SystemSettingsResponse:
    """Reset specified settings keys (or all settings if none provided) back to factory defaults."""
    keys = payload.keys if payload else None
    settings = await settings_service.reset_settings(db, keys=keys)
    await log_action(
        user=current_user,
        action="settings.reset",
        resource_type="system_settings",
        resource_id="reset",
        request=request,
        details={"reset_keys": keys or "all"},
    )
    return SystemSettingsResponse(settings=settings)
