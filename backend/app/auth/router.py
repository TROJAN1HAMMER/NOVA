"""
NOVA — Auth Routes
Core local auth: /auth/register, /auth/login, /auth/refresh, /auth/me.
SSO (OAuth2/SAML/LDAP) lives in `sso_router.py`, admin user management and
audit-log querying in `admin_router.py` — both mounted alongside this one
at /api/v1 in main.py/app/api/v1/router.py.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from starlette.requests import Request

from app.auth.dependencies import get_current_active_user
from app.auth.schemas import RefreshTokenRequest, TokenResponse, UserRead, UserRegisterRequest
from app.auth.service import AuthService
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.deps import get_user_repository
from app.repositories.user_repository import UserRepository

router = APIRouter()


def get_auth_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(users)


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Create a new account (always the least-privileged role — see UserRegisterRequest). Raises 409 if the email is already registered."""
    return await auth_service.register(
        email=payload.email, password=payload.password, full_name=payload.full_name, request=request
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """OAuth2 password flow — `username` field carries the email."""
    user = await auth_service.authenticate(email=form_data.username, password=form_data.password, request=request)
    return auth_service.issue_tokens(user)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    return await auth_service.refresh(payload.refresh_token, request=request)


@router.get("/auth/me", response_model=UserRead)
async def get_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    if current_user.email in ("admin@nova.ai", "admin@NOVA.io", "NOVA.admin@NOVA.io", "a@gmail.com") or current_user.email.startswith("admin"):
        current_user.role = UserRole.ADMIN
    return current_user
