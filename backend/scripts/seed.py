import asyncio
import uuid
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.models.user import User
from app.models.enums import UserRole, AuthProvider
from app.models.faq_rule import FAQRule
from app.auth.security import hash_password

logger = structlog.get_logger(__name__)

# The DATABASE_URL is expected to be loaded from the environment by docker-compose
from app.config import get_settings
settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def seed():
    async with AsyncSessionLocal() as session:
        # Seed Admin User
        admin_email = "admin@NOVA.io"
        result = await session.execute(select(User).where(User.email == admin_email))
        admin = result.scalars().first()

        if not admin:
            logger.info("Seeding admin user...")
            admin = User(
                email=admin_email,
                hashed_password=hash_password("password"),
                full_name="NOVA Administrator",
                role=UserRole.ADMIN,
                auth_provider=AuthProvider.LOCAL,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            logger.info(f"Admin user seeded with ID: {admin.id}")
        else:
            logger.info(f"Admin user already exists with ID: {admin.id}")

        # Seed FAQ Rules
        faqs = [
            {
                "keyword": "what is aekof",
                "response": "AEKOF (Adaptive Enterprise Knowledge Operating Framework) is the core architecture powering NOVA, featuring dynamic routing, confidence calibration, and graph-based retrieval.",
            },
            {
                "keyword": "how to reset password",
                "response": "To reset your password, contact your system administrator or use the SSO provider's recovery options.",
            },
            {
                "keyword": "what is graphrag",
                "response": "GraphRAG extracts entities and relationships into a Knowledge Graph to answer complex, multi-hop queries that require global context.",
            }
        ]

        for faq_data in faqs:
            res = await session.execute(select(FAQRule).where(FAQRule.keyword == faq_data["keyword"]))
            if not res.scalars().first():
                rule = FAQRule(
                    keyword=faq_data["keyword"],
                    response=faq_data["response"],
                    is_active=True,
                    is_draft=False,
                    created_by_id=admin.id
                )
                session.add(rule)
        
        await session.commit()
        logger.info("FAQ Rules seeded.")

async def main():
    await seed()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
