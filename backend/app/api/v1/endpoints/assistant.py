"""
AEKOF — AI Assistant API Endpoints (Sessions + SSE Chat Stream)
"""

import asyncio
import json
import time
import uuid
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import Permission, require_permission
from app.db.session import get_db
from app.middleware.rate_limit import require_rate_limit
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from app.schemas.assistant import ChatRequest
from app.services.assistant import assistant_service
from app.services.assistant.memory_service import memory_service

logger = structlog.get_logger(__name__)
router = APIRouter()

_RATE_LIMIT = require_rate_limit("assistant_chat", limit=30, window_seconds=60)


class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"


class ChatSessionResponse(BaseModel):
    id: uuid.UUID
    title: str
    context_summary: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list
    confidence_vector: dict
    calibrated_trust_score: Optional[float] = None
    reasoning_trace: dict
    created_at: str

    model_config = {"from_attributes": True}


def _sse_pack(data: str, *, event: str | None = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    data_lines = "\n".join(f"data: {line}" for line in data.split("\n"))
    return f"{prefix}{data_lines}\n\n"


@router.get("/assistant/sessions")
async def list_sessions(
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    sessions = await memory_service.list_sessions(db, current_user.id)
    return [
        {
            "id": s.id,
            "title": s.title,
            "context_summary": s.context_summary,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


@router.post("/assistant/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session = await memory_service.get_or_create_session(db, current_user.id)
    if payload.title and payload.title != "New Chat":
        session.title = payload.title
        await db.commit()
    return {
        "id": session.id,
        "title": session.title,
        "context_summary": session.context_summary,
        "created_at": session.created_at.isoformat(),
    }


@router.get("/assistant/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "citations": m.citations,
            "confidence_vector": m.confidence_vector,
            "calibrated_trust_score": m.calibrated_trust_score,
            "reasoning_trace": m.reasoning_trace,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.delete("/assistant/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.delete(session)
    await db.commit()


@router.post("/assistant/chat")
async def chat(
    payload: ChatRequest,
    current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    _rate_limited: Annotated[User, Depends(_RATE_LIMIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    request_start = time.monotonic()
    session = await memory_service.get_or_create_session(db, current_user.id, getattr(payload, "session_id", None))

    retrieval = await assistant_service.retrieve_and_orchestrate(db, query=payload.message, user_id=current_user.id)

    loop = asyncio.get_running_loop()

    def _event_source():
        yield _sse_pack(
            json.dumps(
                {
                    "session_id": str(session.id),
                    "retrieved_count": retrieval.retrieved_count,
                    "confidence": retrieval.confidence,
                    "confidence_vector": retrieval.confidence_vector,
                    "calibrated_trust_score": retrieval.calibrated_trust_score,
                    "reasoning_trace": retrieval.reasoning_trace,
                    "citations": [
                        {
                            "document_id": c.document_id,
                            "filename": c.filename,
                            "page_number": c.page_number,
                            "section_path": c.section_path,
                            "heading": c.heading,
                            "similarity_score": c.similarity_score,
                            "rerank_score": c.rerank_score,
                            "excerpt": c.excerpt,
                        }
                        for c in retrieval.citations
                    ],
                }
            ),
            event="retrieval",
        )

        full_response_chunks: list[str] = []
        try:
            history = [turn.model_dump() for turn in (payload.history or [])]
            for chunk in assistant_service.stream_answer(retrieval, message=payload.message, history=history):
                full_response_chunks.append(chunk)
                yield _sse_pack(chunk, event="token")
        except Exception as exc:
            logger.warning("assistant_api.stream_failed", error=str(exc))
            yield _sse_pack("The response stream failed part-way through.", event="error")
            return

        full_answer = "".join(full_response_chunks)

        # Thread-safe async task to save turn history
        asyncio.run_coroutine_threadsafe(
            memory_service.save_turn(
                db=None,
                session_id=session.id,
                user_message=payload.message,
                assistant_response=full_answer,
                citations=[
                    {
                        "document_id": c.document_id,
                        "filename": c.filename,
                        "page_number": c.page_number,
                        "section_path": c.section_path,
                        "excerpt": c.excerpt,
                    }
                    for c in retrieval.citations
                ],
                confidence_vector=retrieval.confidence_vector,
                calibrated_trust_score=retrieval.calibrated_trust_score,
                reasoning_trace=retrieval.reasoning_trace,
                consensus_matrix=retrieval.consensus_matrix,
            ),
            loop,
        )

        yield _sse_pack(
            json.dumps(
                {
                    "session_id": str(session.id),
                    "confidence": retrieval.confidence,
                    "calibrated_trust_score": retrieval.calibrated_trust_score,
                    "retrieved_count": retrieval.retrieved_count,
                    "latency_ms": round((time.monotonic() - request_start) * 1000, 1),
                }
            ),
            event="done",
        )

    return StreamingResponse(
        _event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
