"""
AEKOF — FAQ Rules & Knowledge Gap Inbox Endpoints
"""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.user import User
from app.services.faq_service import faq_service

router = APIRouter()


class FAQRuleCreate(BaseModel):
    keyword: str
    response: str


class FAQRuleResponse(BaseModel):
    id: uuid.UUID
    keyword: str
    response: str
    is_active: bool
    is_draft: bool

    model_config = {"from_attributes": True}


@router.get("/faq", response_model=list[FAQRuleResponse])
async def list_faq(
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rules = await faq_service.list_rules(db, include_drafts=False)
    return rules


@router.post("/faq", response_model=FAQRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_faq(
    payload: FAQRuleCreate,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rule = await faq_service.create_rule(db, keyword=payload.keyword, response=payload.response, user_id=current_user.id)
    return rule


@router.delete("/faq/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    rule_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await faq_service.delete_rule(db, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ rule not found.")


@router.get("/faq/gap-inbox", response_model=list[FAQRuleResponse])
async def get_gap_inbox(
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rules = await faq_service.list_rules(db, include_drafts=True)
    return [r for r in rules if r.is_draft]


@router.post("/faq/gap-inbox/{rule_id}/promote", response_model=FAQRuleResponse)
async def promote_draft_faq(
    rule_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rule = await faq_service.promote_draft(db, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Draft FAQ rule not found.")
    return rule
