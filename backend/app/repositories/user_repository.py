"""
NOVA — User Repository
"""

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuthProvider, UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get(self, user_id: uuid.UUID) -> Optional[User]:
        return await self.db.get(User, user_id)

    async def get_by_external_subject(self, auth_provider: AuthProvider, external_subject: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(
                User.auth_provider == auth_provider, User.external_subject == external_subject
            )
        )
        return result.scalar_one_or_none()

    async def create(self, *, email: str, hashed_password: str, full_name: Optional[str] = None) -> User:
        user = User(email=email, hashed_password=hashed_password, full_name=full_name)
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def create_sso_user(
        self,
        *,
        email: str,
        full_name: Optional[str],
        auth_provider: AuthProvider,
        external_subject: str,
        role: UserRole = UserRole.READ_ONLY,
    ) -> User:
        """
        No password — identity is vouched for by the IdP, not a local
        secret. Same least-privileged default role as local self-
        registration: an SSO login provisioning a brand-new account is
        just as untrusted-by-default as a fresh email/password signup.
        """
        user = User(
            email=email,
            hashed_password=None,
            full_name=full_name,
            auth_provider=auth_provider,
            external_subject=external_subject,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        result = await self.db.execute(
            select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def update_role(self, user_id: uuid.UUID, role: UserRole) -> Optional[User]:
        user = await self.get(user_id)
        if user is not None:
            user.role = role
            await self.db.flush()
        return user

    async def set_active(self, user_id: uuid.UUID, is_active: bool) -> Optional[User]:
        user = await self.get(user_id)
        if user is not None:
            user.is_active = is_active
            await self.db.flush()
        return user
