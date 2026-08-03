"""
NOVA — Executive Intelligence Routes (RAG Milestone 4)
Gated by `get_current_active_user` only (no fine-grained Permission) —
the same precedent app/api/v1/endpoints/finding_intelligence.py already
set for a read-oriented, retrieval-backed feature: the frontend's
route-level RBAC (matching /executive's existing role set: Admin,
Security Manager, Executive/Board, and Read Only — a different, wider-
than-KNOWLEDGE_READ audience than the AI Assistant/Knowledge Base pages)
is the actual access boundary for who reaches this panel at all.

Both routes here are POST-shaped but semantically read-only (POST only
carries a request body) — see app/middleware/permission_middleware.py's
READ_ONLY_QUERY_PATH_PREFIXES, which this module's paths are added to so
the Read Only/Executive roles aren't wrongly blocked by the coarse
verb-based rule.
"""

import json
import time
from dataclasses import asdict
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.db.session import get_db
from app.middleware.rate_limit import require_rate_limit
from app.models.user import User
from app.schemas.executive_intelligence import ExecutiveAskRequest, ExecutivePdfExportRequest
from app.services.executive_intelligence import executive_intelligence_service, pdf_export

logger = structlog.get_logger(__name__)
router = APIRouter()

_ASK_RATE_LIMIT = require_rate_limit("executive_ask", limit=20, window_seconds=60)
_EXPORT_RATE_LIMIT = require_rate_limit("executive_export_pdf", limit=10, window_seconds=60)


def _sse_pack(data: str, *, event: str | None = None) -> str:
    prefix = f"event: {event}\n" if event else ""
    data_lines = "\n".join(f"data: {line}" for line in data.split("\n"))
    return f"{prefix}{data_lines}\n\n"


@router.post("/executive-intelligence/ask")
async def ask_executive_intelligence(
    payload: ExecutiveAskRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    _rate_limited: Annotated[User, Depends(_ASK_RATE_LIMIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    SSE stream. Event sequence:
      "evidence"             — always first: the deterministic scan-history
                               snapshot (see evidence_service.py) + any
                               supplementary knowledge-base citations.
      "insufficient_context" — sent INSTEAD of any "token"s when there is
                               neither scan history nor KB support at all
                               (an empty, brand-new deployment) — the LLM
                               is never called in this case.
      "token"                 — one or more, the streamed answer text.
      "done"                  — latency, always last after "token"s.
      "error"                  — only if the stream fails part-way through.
    """
    start = time.monotonic()
    evidence = await executive_intelligence_service.gather_evidence(
        db, question=payload.question, user_id=current_user.id
    )

    def _event_source():
        yield _sse_pack(
            json.dumps(
                {
                    "evidence": asdict(evidence.snapshot),
                    "citations": [asdict(c) for c in evidence.citations],
                    "kb_confidence": evidence.kb_confidence,
                    "kb_retrieved_count": evidence.kb_retrieved_count,
                }
            ),
            event="evidence",
        )

        if not evidence.has_any_grounding:
            yield _sse_pack(
                json.dumps(
                    {
                        "message": executive_intelligence_service.NO_DATA_MESSAGE,
                        "latency_ms": round((time.monotonic() - start) * 1000, 1),
                    }
                ),
                event="insufficient_context",
            )
            return

        try:
            history = [turn.model_dump() for turn in payload.history]
            for chunk in executive_intelligence_service.stream_answer(
                evidence, question=payload.question, history=history
            ):
                yield _sse_pack(chunk, event="token")
        except Exception as exc:
            logger.warning("executive_intelligence_api.stream_failed", error=str(exc))
            yield _sse_pack("The response stream failed part-way through.", event="error")
            return

        yield _sse_pack(
            json.dumps({"latency_ms": round((time.monotonic() - start) * 1000, 1)}),
            event="done",
        )

    return StreamingResponse(
        _event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/executive-intelligence/export-pdf")
async def export_executive_intelligence_pdf(
    payload: ExecutivePdfExportRequest,
    _current_user: Annotated[User, Depends(get_current_active_user)],
    _rate_limited: Annotated[User, Depends(_EXPORT_RATE_LIMIT)],
):
    """Renders exactly the question/answer/evidence/citations passed in — see
    app/services/executive_intelligence/pdf_export.py's docstring for why
    this never recomputes anything server-side at export time."""
    pdf_bytes = pdf_export.render_pdf(
        question=payload.question,
        answer=payload.answer,
        evidence=payload.evidence.model_dump(),
        citations=[c.model_dump() for c in payload.citations],
        confidence=payload.confidence,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="NOVA-executive-intelligence.pdf"'},
    )
