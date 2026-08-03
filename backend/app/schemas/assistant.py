"""
NOVA — AI Assistant Schemas
No response_model on the chat endpoint itself (it returns a raw SSE
text/event-stream, same as scan.py's `stream_finding_explanation`) — this
only validates the incoming request.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    # Client-managed conversation history (see assistant_service.py's
    # module docstring for why this isn't persisted server-side in this
    # milestone) — only the most recent
    # `settings.assistant_max_history_turns` are ever used, regardless of
    # how many are sent. `max_length` here (Milestone 5 hardening) still
    # matters despite that server-side slicing: without it, a request
    # carrying thousands of history entries pays the cost of being
    # received, parsed, and validated in full before any slicing happens.
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)
