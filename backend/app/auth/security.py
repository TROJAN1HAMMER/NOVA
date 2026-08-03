"""
NOVA — Password Hashing & JWT Primitives
Pure functions with no FastAPI or ORM dependency — testable in isolation
and reusable from a future CLI or Celery task if needed.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.models.enums import UserRole

settings = get_settings()

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, expires_delta: timedelta, token_type: str, *, extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, role: UserRole) -> str:
    """
    Embeds `role` in the access token itself (unlike the refresh token,
    which stays minimal) so `PermissionMiddleware` can apply its coarse,
    role-based gate without a DB round-trip on every request. This is a
    convenience claim, not the source of truth: `get_current_user`
    (app/auth/dependencies.py) still re-fetches the user from the database
    on every request for anything permission-sensitive, so a stale role in
    an already-issued token (e.g. an admin demotes someone mid-session)
    can only ever *under*-grant relative to the DB — `require_permission`
    checks `current_user.role` freshly loaded from the DB, never the JWT
    claim — and is corrected the moment the access token expires (default
    30 minutes) or the user refreshes.
    """
    return _create_token(
        str(user_id),
        timedelta(minutes=settings.access_token_expire_minutes),
        token_type="access",
        extra_claims={"role": role.value},
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(
        str(user_id),
        timedelta(days=settings.refresh_token_expire_days),
        token_type="refresh",
    )


def decode_token(token: str) -> dict[str, Any]:
    """Raises jose.JWTError on any invalid, expired, or tampered token."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
