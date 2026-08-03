"""
AEKOF — FAQ Keyword Router & Dual-Loop Self-Healing Gap Service
"""

import uuid
import structlog
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faq_rule import FAQRule
from app.models.knowledge import SearchAnalyticsLog

logger = structlog.get_logger(__name__)


class FAQService:
    async def match_faq(self, db: AsyncSession, query: str) -> Optional[FAQRule]:
        """Stage 0: Deterministic rule match (<1ms). Returns active FAQ match or None."""
        q_lower = query.lower().strip()
        result = await db.execute(
            select(FAQRule).where(FAQRule.is_active == True, FAQRule.is_draft == False)
        )
        rules = result.scalars().all()
        matches = [rule for rule in rules if rule.keyword.lower() in q_lower]
        if matches:
            # Pick rule with longest matching keyword
            best_match = max(matches, key=lambda r: len(r.keyword))
            logger.info("faq_service.match_found", keyword=best_match.keyword)
            return best_match
        return None

    async def list_rules(self, db: AsyncSession, include_drafts: bool = False) -> list[FAQRule]:
        query = select(FAQRule)
        if not include_drafts:
            query = query.where(FAQRule.is_draft == False)
        result = await db.execute(query.order_by(FAQRule.created_at.desc()))
        return list(result.scalars().all())

    async def create_rule(
        self, db: AsyncSession, keyword: str, response: str, user_id: Optional[uuid.UUID] = None, is_draft: bool = False
    ) -> FAQRule:
        rule = FAQRule(
            keyword=keyword.strip(),
            response=response.strip(),
            is_active=True,
            is_draft=is_draft,
            created_by_id=user_id,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    async def promote_draft(self, db: AsyncSession, rule_id: uuid.UUID) -> Optional[FAQRule]:
        result = await db.execute(select(FAQRule).where(FAQRule.id == rule_id))
        rule = result.scalar_one_or_none()
        if rule:
            rule.is_draft = False
            rule.is_active = True
            await db.commit()
            await db.refresh(rule)
        return rule

    async def delete_rule(self, db: AsyncSession, rule_id: uuid.UUID) -> bool:
        result = await db.execute(select(FAQRule).where(FAQRule.id == rule_id))
        rule = result.scalar_one_or_none()
        if rule:
            await db.delete(rule)
            await db.commit()
            return True
        return False


faq_service = FAQService()
