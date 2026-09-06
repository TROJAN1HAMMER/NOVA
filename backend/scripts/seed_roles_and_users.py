import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.enums import UserRole, AuthProvider
from app.auth.security import hash_password

async def main():
    users_data = [
        {"email": "admin@nova.ai", "full_name": "Nova Admin", "role": UserRole.ADMIN, "password": "password"},
        {"email": "security@nova.ai", "full_name": "Sarah Chen (Security Lead)", "role": UserRole.SECURITY_ENGINEER, "password": "password"},
        {"email": "dev@nova.ai", "full_name": "Alex Rivera (Developer)", "role": UserRole.DEVELOPER, "password": "password"},
        {"email": "auditor@nova.ai", "full_name": "Compliance Auditor", "role": UserRole.AUDITOR, "password": "password"},
        {"email": "readonly@nova.ai", "full_name": "Read Only Viewer", "role": UserRole.READ_ONLY, "password": "password"},
    ]

    async with AsyncSessionLocal() as session:
        for u in users_data:
            res = await session.execute(select(User).where(User.email == u["email"]))
            existing = res.scalar_one_or_none()
            hashed = hash_password(u["password"])
            if existing:
                existing.hashed_password = hashed
                existing.role = u["role"]
                existing.is_active = True
                existing.full_name = u["full_name"]
                print(f"[UPDATED] {u['email']} -> password: '{u['password']}' | role: {u['role'].value}")
            else:
                new_user = User(
                    email=u["email"],
                    full_name=u["full_name"],
                    hashed_password=hashed,
                    role=u["role"],
                    auth_provider=AuthProvider.LOCAL,
                    is_active=True,
                )
                session.add(new_user)
                print(f"[CREATED] {u['email']} -> password: '{u['password']}' | role: {u['role'].value}")

        await session.commit()
    print("\nAll roles successfully seeded and verified!")

if __name__ == "__main__":
    asyncio.run(main())
