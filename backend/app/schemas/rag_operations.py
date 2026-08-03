"""
NOVA — RAG Operations Schemas (Milestone 5)
Backs the benchmark trigger, search-analytics summary, and feedback
submission/summary endpoints — see app/api/v1/endpoints/rag_operations.py.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class BenchmarkStageSchema(BaseModel):
    stage: str
    avg_duration_ms: float
    detail: Optional[str] = None


class BenchmarkResultSchema(BaseModel):
    ran_at: str
    stages: list[BenchmarkStageSchema]
    total_duration_ms: float
    documents_indexed: int
    llm_configured: bool


class SearchAnalyticsRecentEntry(BaseModel):
    feature: str
    query: str
    result_count: int
    top_score: Optional[float] = None
    latency_ms: float
    created_at: str


class SearchAnalyticsSummaryResponse(BaseModel):
    total_searches: int
    average_latency_ms: Optional[float] = None
    average_result_count: Optional[float] = None
    zero_result_count: int
    zero_result_rate: Optional[float] = None
    recent_searches: list[SearchAnalyticsRecentEntry]


class FeedbackSubmitRequest(BaseModel):
    feature: str = Field(max_length=32)
    reference_id: str = Field(max_length=255)
    rating: Literal[-1, 1]
    comment: Optional[str] = Field(default=None, max_length=2000)


class FeedbackSummaryResponse(BaseModel):
    total_feedback: int
    positive_count: int
    negative_count: int
    positive_rate: Optional[float] = None
