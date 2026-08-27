"""
AEKOF — Dynamic System Settings & RAG Hyperparameter Service
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting

logger = structlog.get_logger(__name__)

DEFAULT_SETTINGS = {
    "rag.chunk_size": 1000,
    "rag.chunk_overlap": 200,
    "rag.temperature": 0.7,
    "rag.top_k": 5,
    "rag.similarity_threshold": 0.15,
    "rag.enable_web_search": True,
    "rag.enable_faq_router": True,
    "rag.enable_consensus": True,
    "rag.system_prompt": """You are AEKOF, a concise, professional Enterprise Knowledge Intelligence Assistant.

Rules:
1. For general factual/support queries, answer using the provided Context and Evidence.
2. If exact details are NOT present in the Context block below, respond with: "Sorry, I don't know based on the given context."
3. Provide resolution steps in bullet points when applicable.

Context:
{context}

User Question:
{question}

Answer:
""",
}


class SettingsService:
    async def get_settings(self, db: AsyncSession) -> dict:
        result = await db.execute(select(SystemSetting))
        rows = result.scalars().all()
        settings = DEFAULT_SETTINGS.copy()
        for row in rows:
            settings[row.key] = row.value
        return settings

    async def get_setting(self, db: AsyncSession, key: str, default: any = None) -> any:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value
        return DEFAULT_SETTINGS.get(key, default)

    async def update_settings(self, db: AsyncSession, settings_dict: dict) -> dict:
        for key, value in settings_dict.items():
            result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(SystemSetting(key=key, value=value))
        await db.commit()
        return await self.get_settings(db)

    async def update_setting(self, db: AsyncSession, key: str, value: any) -> any:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(SystemSetting(key=key, value=value))
        await db.commit()
        return await self.get_setting(db, key)

    async def reset_settings(self, db: AsyncSession, keys: list[str] | None = None) -> dict:
        if keys:
            for k in keys:
                result = await db.execute(select(SystemSetting).where(SystemSetting.key == k))
                row = result.scalar_one_or_none()
                if row:
                    await db.delete(row)
        else:
            result = await db.execute(select(SystemSetting))
            rows = result.scalars().all()
            for row in rows:
                await db.delete(row)
        await db.commit()
        return await self.get_settings(db)


settings_service = SettingsService()
