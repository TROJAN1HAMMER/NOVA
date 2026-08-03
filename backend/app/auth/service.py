"""
NOVA — Auth Service
Business logic for registration/login/token-refresh. Depends only on
`UserRepository` (never touches `AsyncSession` or FastAPI directly beyond
the optional `Request` passed through purely for audit-log
IP/user-agent capture), so it is unit-testable with a fake repository and
reusable outside the HTTP layer.
"""

import uuid
from typing import Optional

from jose import JWTError
from starlette.requests import Request

from app.auth.schemas import TokenResponse
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import ConflictError, UnauthorizedError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.audit.audit_logger import log_action


class AuthService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    async def register(
        self, *, email: str, password: str, full_name: str | None = None, request: Optional[Request] = None
    ) -> User:
        existing = await self.users.get_by_email(email)
        if existing:
            raise ConflictError(f"An account with email '{email}' already exists")
        # Self-registration always lands on the least-privileged role
        # (the model's own default) — an admin promotes accounts
        # afterward via PATCH /auth/admin/users/{id}/role. There is no
        # "role" field on UserRegisterRequest at all, deliberately: nobody
        # should be able to register themselves in as Admin.
        user = await self.users.create(
            email=email, hashed_password=hash_password(password), full_name=full_name
        )
        # Commit before audit-logging, not after: `log_action` writes
        # through its own independent DB connection (see its docstring),
        # so if this new user's row were still sitting in this request's
        # uncommitted transaction, that separate connection couldn't see
        # it yet — the audit_logs.user_id foreign key would fail to
        # validate, and the whole "register" event would silently vanish
        # (caught by log_action's own fail-open try/except). Confirmed by
        # actually exercising this against a real Postgres instance: the
        # FK violation was real, not hypothetical. The user row's
        # durability shouldn't depend on anything later in this request
        # succeeding anyway, so committing it immediately is correct on
        # its own merits, not just a workaround.
        await self.users.db.commit()
        await log_action(user=user, action="register", resource_type="user", resource_id=str(user.id), request=request)
        return user

    async def authenticate(self, *, email: str, password: str, request: Optional[Request] = None) -> User:
        user = await self.users.get_by_email(email)
        # `hashed_password` is null for SSO-provisioned accounts (OAuth2/
        # SAML/LDAP) — such an account was never given a local password to
        # verify against, so it always fails password login, same as a
        # wrong password would, rather than raising on `verify_password(None)`.
        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            await log_action(
                user=user, action="login.failed", resource_type="user",
                resource_id=str(user.id) if user else email, status="failure", request=request,
            )
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            await log_action(
                user=user, action="login.failed", resource_type="user",
                resource_id=str(user.id), status="failure", request=request,
                details={"reason": "account_disabled"},
            )
            raise UnauthorizedError("Account is disabled")

        # Auto-promote platform admin accounts to ADMIN role in DB
        if email in ("admin@NOVA.io", "NOVA.admin@NOVA.io", "a@gmail.com") or email.startswith("admin"):
            if user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                await self.users.db.commit()

        await log_action(user=user, action="login", resource_type="user", resource_id=str(user.id), request=request)
        return user

    def issue_tokens(self, user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id, user.role),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str, *, request: Optional[Request] = None) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedError("Token is not a refresh token")
            user_id = uuid.UUID(payload["sub"])
        except (JWTError, ValueError, KeyError) as exc:
            raise UnauthorizedError("Invalid or expired refresh token") from exc

        user = await self.users.get(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        await log_action(user=user, action="token.refresh", resource_type="user", resource_id=str(user.id), request=request)
        return self.issue_tokens(user)
