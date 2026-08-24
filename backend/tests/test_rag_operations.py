"""
NOVA — RAG Operations & Benchmark Service Unit Tests
Validates live timing probes (embedding, search, rerank, LLM gateway),
RAG operations endpoints (benchmark, search analytics, feedback),
and RBAC permission enforcement (TEAM_ANALYTICS_READ).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.rag_operations import (
    get_feedback_summary as api_get_feedback_summary,
    get_search_analytics as api_get_search_analytics,
    run_benchmark as api_run_benchmark,
    submit_feedback as api_submit_feedback,
)
from app.auth.permissions import Permission, require_permission
from app.core.exceptions import ForbiddenError
from app.models.enums import AuthProvider, UserRole
from app.models.user import User
from app.schemas.rag_operations import (
    BenchmarkResultSchema,
    FeedbackSubmitRequest,
    FeedbackSummaryResponse,
    SearchAnalyticsSummaryResponse,
)
from app.services.benchmark.benchmark_service import (
    BenchmarkResult,
    StageTiming,
    run_benchmark,
)


# ── 1. Benchmark Service Unit Tests ───────────────────────────────────────────


class TestBenchmarkServiceUnit:
    @pytest.mark.asyncio
    async def test_run_benchmark_with_llm_configured(self):
        mock_db = AsyncMock()

        # Mock vector store similarity search returning 2 candidate pairs
        mock_chunk = MagicMock()
        mock_chunk.content = "Sample benchmark content"
        mock_candidates = [(mock_chunk, 0.85), (mock_chunk, 0.75)]

        # Mock LLM completion response
        mock_llm_response = MagicMock()
        mock_llm_response.provider = "mock_provider"

        mock_gateway = MagicMock()
        mock_gateway.complete.return_value = mock_llm_response

        with (
            patch("app.services.benchmark.benchmark_service.embedding_manager.embed_query", return_value=[0.1] * 384),
            patch("app.services.benchmark.benchmark_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=mock_candidates),
            patch("app.services.benchmark.benchmark_service.rerank_manager.rerank", return_value=["Sample benchmark content"]),
            patch("app.services.benchmark.benchmark_service.get_gateway", return_value=mock_gateway),
            patch("app.services.benchmark.benchmark_service._count_indexed_documents", new_callable=AsyncMock, return_value=8),
        ):
            result = await run_benchmark(mock_db)

            assert isinstance(result, BenchmarkResult)
            assert result.documents_indexed == 8
            assert result.llm_configured is True
            assert result.total_duration_ms >= 0.0

            stage_names = [s.stage for s in result.stages]
            assert "embedding_per_query" in stage_names
            assert "vector_search_per_query" in stage_names
            assert "rerank_candidates" in stage_names
            assert "llm_completion" in stage_names

            llm_stage = next(s for s in result.stages if s.stage == "llm_completion")
            assert llm_stage.detail == "provider=mock_provider"

    @pytest.mark.asyncio
    async def test_run_benchmark_without_llm_configured(self):
        mock_db = AsyncMock()

        mock_chunk = MagicMock()
        mock_chunk.content = "Sample benchmark content"
        mock_candidates = [(mock_chunk, 0.85)]

        mock_gateway = MagicMock()
        mock_gateway.complete.return_value = None

        with (
            patch("app.services.benchmark.benchmark_service.embedding_manager.embed_query", return_value=[0.1] * 384),
            patch("app.services.benchmark.benchmark_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=mock_candidates),
            patch("app.services.benchmark.benchmark_service.rerank_manager.rerank", return_value=["Sample benchmark content"]),
            patch("app.services.benchmark.benchmark_service.get_gateway", return_value=mock_gateway),
            patch("app.services.benchmark.benchmark_service._count_indexed_documents", new_callable=AsyncMock, return_value=3),
        ):
            result = await run_benchmark(mock_db)

            assert result.documents_indexed == 3
            assert result.llm_configured is False

            llm_stage = next(s for s in result.stages if s.stage == "llm_completion")
            assert llm_stage.detail == "no provider configured"

    @pytest.mark.asyncio
    async def test_run_benchmark_empty_vector_candidates(self):
        mock_db = AsyncMock()

        mock_gateway = MagicMock()
        mock_gateway.complete.return_value = None

        with (
            patch("app.services.benchmark.benchmark_service.embedding_manager.embed_query", return_value=[0.1] * 384),
            patch("app.services.benchmark.benchmark_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=[]),
            patch("app.services.benchmark.benchmark_service.get_gateway", return_value=mock_gateway),
            patch("app.services.benchmark.benchmark_service._count_indexed_documents", new_callable=AsyncMock, return_value=0),
        ):
            result = await run_benchmark(mock_db)

            assert result.documents_indexed == 0
            stage_names = [s.stage for s in result.stages]
            assert "embedding_per_query" in stage_names
            assert "vector_search_per_query" in stage_names
            # Rerank stage should be skipped when no candidates exist
            assert "rerank_candidates" not in stage_names


# ── 2. RAG Operations Endpoints Tests ─────────────────────────────────────────


class TestRAGOperationsEndpoints:
    @pytest.mark.asyncio
    async def test_api_run_benchmark(self):
        user = User(
            id=uuid.uuid4(),
            email="secops@nova.example",
            role=UserRole.SECURITY_ENGINEER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        mock_benchmark_res = BenchmarkResult(
            ran_at="2026-08-24T15:00:00Z",
            stages=[
                StageTiming(stage="embedding_per_query", avg_duration_ms=25.0, detail=None),
                StageTiming(stage="vector_search_per_query", avg_duration_ms=15.0, detail="3 matches"),
            ],
            total_duration_ms=40.0,
            documents_indexed=5,
            llm_configured=True,
        )

        with patch("app.api.v1.endpoints.rag_operations.benchmark_service.run_benchmark", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_benchmark_res
            res = await api_run_benchmark(_current_user=user, db=mock_db)

            assert isinstance(res, BenchmarkResultSchema)
            assert res.ran_at == "2026-08-24T15:00:00Z"
            assert res.total_duration_ms == 40.0
            assert res.documents_indexed == 5
            assert res.llm_configured is True
            assert len(res.stages) == 2
            mock_run.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_api_get_search_analytics(self):
        user = User(
            id=uuid.uuid4(),
            email="secops@nova.example",
            role=UserRole.SECURITY_ENGINEER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        summary_data = {
            "total_searches": 150,
            "average_latency_ms": 45.2,
            "average_result_count": 4.1,
            "zero_result_count": 6,
            "zero_result_rate": 0.04,
            "recent_searches": [],
        }

        with patch("app.api.v1.endpoints.rag_operations.analytics_service.get_summary", new_callable=AsyncMock) as mock_summary:
            mock_summary.return_value = summary_data
            res = await api_get_search_analytics(_current_user=user, db=mock_db, feature="assistant_chat")

            assert isinstance(res, SearchAnalyticsSummaryResponse)
            assert res.total_searches == 150
            assert res.zero_result_count == 6
            assert res.zero_result_rate == 0.04
            mock_summary.assert_called_once_with(mock_db, feature="assistant_chat")

    @pytest.mark.asyncio
    async def test_api_submit_feedback(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        feedback_id = uuid.uuid4()
        mock_entry = MagicMock()
        mock_entry.id = feedback_id

        payload = FeedbackSubmitRequest(
            feature="assistant_chat",
            reference_id="ref_query_123",
            rating=1,
            comment="Excellent synthesis",
        )

        with patch("app.api.v1.endpoints.rag_operations.feedback_service.submit_feedback", new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = mock_entry
            res = await api_submit_feedback(payload=payload, current_user=user, db=mock_db)

            assert res == {"id": str(feedback_id), "status": "recorded"}
            mock_submit.assert_called_once_with(
                mock_db,
                feature="assistant_chat",
                reference_id="ref_query_123",
                rating=1,
                comment="Excellent synthesis",
                user_id=user.id,
            )
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_get_feedback_summary(self):
        user = User(
            id=uuid.uuid4(),
            email="auditor@nova.example",
            role=UserRole.AUDITOR,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        summary_data = {
            "total_feedback": 80,
            "positive_count": 72,
            "negative_count": 8,
            "positive_rate": 0.90,
        }

        with patch("app.api.v1.endpoints.rag_operations.feedback_service.get_summary", new_callable=AsyncMock) as mock_summary:
            mock_summary.return_value = summary_data
            res = await api_get_feedback_summary(_current_user=user, db=mock_db, feature=None)

            assert isinstance(res, FeedbackSummaryResponse)
            assert res.total_feedback == 80
            assert res.positive_count == 72
            assert res.negative_count == 8
            assert res.positive_rate == 0.90
            mock_summary.assert_called_once_with(mock_db, feature=None)


# ── 3. RAG Operations Permissions Tests ───────────────────────────────────────


class TestRAGOperationsPermissions:
    @pytest.mark.asyncio
    async def test_team_analytics_read_permission_gating(self):
        dep = require_permission(Permission.TEAM_ANALYTICS_READ)

        # ADMIN, SECURITY_ENGINEER, AUDITOR must succeed
        allowed_roles = [
            UserRole.ADMIN,
            UserRole.SECURITY_ENGINEER,
            UserRole.AUDITOR,
        ]
        for role in allowed_roles:
            user = User(
                id=uuid.uuid4(),
                email=f"{role.value}@nova.example",
                role=role,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
            )
            assert await dep(current_user=user) == user

        # DEVELOPER, READ_ONLY must be rejected with 403 ForbiddenError
        unauthorized_roles = [
            UserRole.DEVELOPER,
            UserRole.READ_ONLY,
        ]
        with patch("app.auth.permissions.log_action", new_callable=AsyncMock):
            for role in unauthorized_roles:
                user = User(
                    id=uuid.uuid4(),
                    email=f"{role.value}@nova.example",
                    role=role,
                    is_active=True,
                    auth_provider=AuthProvider.LOCAL,
                )
                with pytest.raises(ForbiddenError):
                    await dep(current_user=user)
