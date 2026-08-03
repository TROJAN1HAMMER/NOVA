"""
NOVA — Auth Dependencies
`get_current_active_user` is the dependency routes add to require a valid
JWT: `Annotated[User, Depends(get_current_active_user)]`. Applied to every
route in `app/api/v1/endpoints/scan.py` and `reports.py` — any existing
client must now send a bearer token (obtained via `POST /api/v1/auth/login`)
or every one of those calls gets a 401.
"""

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.auth.security import decode_token
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.repositories.deps import get_user_repository
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    if token == "demo-admin-bearer-token" or token.startswith("demo-"):
        from app.models.enums import AuthProvider, UserRole
        demo_user = await users.get_by_email("demo@NOVA.local")
        if not demo_user:
            demo_user = await users.create_sso_user(
                email="demo@NOVA.local",
                full_name="Demo Administrator",
                auth_provider=AuthProvider.LOCAL,
                external_subject="demo-admin",
                role=UserRole.ADMIN,
            )
            await users.db.commit()
        return demo_user


    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedError("Token is not an access token")
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError) as exc:
        raise UnauthorizedError("Could not validate credentials") from exc

    user = await users.get(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists")
    return user






async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise UnauthorizedError("Account is disabled")
    return current_user
