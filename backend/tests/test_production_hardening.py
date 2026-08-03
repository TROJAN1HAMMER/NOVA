"""
NOVA — Production Hardening Unit Tests (RAG Milestone 5)
Targets the genuinely pure logic this milestone added: the Celery retry
backoff calculation and the new Pydantic input-size caps. Everything else
in this milestone (document versioning, duplicate detection, embedding/
rerank caching, rate limiting, metrics recording, the benchmark service)
is inherently DB/Redis/model-dependent orchestration — consistent with
every earlier milestone's own testing philosophy, that's integration-
level and covered by the manual testing procedure in
docs/production_hardening.md instead of a mocked unit test here.
"""

import pytest
from pydantic import ValidationError

from app.schemas.assistant import ChatMessage, ChatRequest
from app.schemas.executive_intelligence import ExecutiveAskRequest, ExecutiveCitation, ExecutivePdfExportRequest
from app.tasks.knowledge_tasks import retry_backoff_seconds


class TestRetryBackoffSeconds:
    def test_first_attempt_is_15_seconds(self):
        assert retry_backoff_seconds(0) == 15

    def test_second_attempt_doubles(self):
        assert retry_backoff_seconds(1) == 30

    def test_third_attempt_doubles_again(self):
        assert retry_backoff_seconds(2) == 60

    def test_monotonically_increasing(self):
        values = [retry_backoff_seconds(i) for i in range(4)]
        assert values == sorted(values)
        assert len(set(values)) == len(values)


class TestChatRequestCaps:
    def test_accepts_within_limits(self):
        request = ChatRequest(message="hello", history=[ChatMessage(role="user", content="hi")])
        assert request.message == "hello"

    def test_rejects_history_over_max_length(self):
        history = [ChatMessage(role="user", content="x") for _ in range(51)]
        with pytest.raises(ValidationError):
            ChatRequest(message="hello", history=history)

    def test_accepts_history_at_max_length(self):
        history = [ChatMessage(role="user", content="x") for _ in range(50)]
        request = ChatRequest(message="hello", history=history)
        assert len(request.history) == 50

    def test_rejects_message_over_max_length(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="x" * 4001, history=[])

    def test_rejects_chat_message_content_over_max_length(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="x" * 8001)

    def test_rejects_empty_message(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="", history=[])


class TestExecutiveAskRequestCaps:
    def test_rejects_history_over_max_length(self):
        history = [ChatMessage(role="user", content="x") for _ in range(51)]
        with pytest.raises(ValidationError):
            ExecutiveAskRequest(question="What are our biggest risks?", history=history)

    def test_rejects_question_over_max_length(self):
        with pytest.raises(ValidationError):
            ExecutiveAskRequest(question="x" * 2001, history=[])


class TestExecutiveCitationCaps:
    def test_rejects_excerpt_over_max_length(self):
        with pytest.raises(ValidationError):
            ExecutiveCitation(
                document_id="doc-1",
                filename="policy.pdf",
                similarity_score=0.8,
                excerpt="x" * 4001,
            )

    def test_accepts_excerpt_at_max_length(self):
        citation = ExecutiveCitation(
            document_id="doc-1",
            filename="policy.pdf",
            similarity_score=0.8,
            excerpt="x" * 4000,
        )
        assert len(citation.excerpt) == 4000


class TestExecutivePdfExportRequestCaps:
    def _snapshot(self):
        from app.schemas.executive_intelligence import EvidenceSnapshotSchema

        return EvidenceSnapshotSchema(
            generated_at="2026-07-20T00:00:00Z",
            total_repositories=1,
            total_completed_scans=1,
            total_findings=0,
            findings_by_severity={},
        )

    def test_rejects_answer_over_max_length(self):
        with pytest.raises(ValidationError):
            ExecutivePdfExportRequest(
                question="What are our biggest risks?",
                answer="x" * 20001,
                evidence=self._snapshot(),
                citations=[],
                confidence=None,
            )

    def test_rejects_too_many_citations(self):
        citation = ExecutiveCitation(
            document_id="doc-1", filename="policy.pdf", similarity_score=0.8, excerpt="short"
        )
        with pytest.raises(ValidationError):
            ExecutivePdfExportRequest(
                question="What are our biggest risks?",
                answer="A short answer.",
                evidence=self._snapshot(),
                citations=[citation] * 21,
                confidence=None,
            )

    def test_accepts_within_limits(self):
        request = ExecutivePdfExportRequest(
            question="What are our biggest risks?",
            answer="A short answer.",
            evidence=self._snapshot(),
            citations=[],
            confidence=0.9,
        )
        assert request.answer == "A short answer."


class TestFeedbackSubmitRequest:
    def test_accepts_positive_rating(self):
        from app.schemas.rag_operations import FeedbackSubmitRequest

        payload = FeedbackSubmitRequest(feature="assistant_chat", reference_id="msg-1", rating=1)
        assert payload.rating == 1

    def test_accepts_negative_rating(self):
        from app.schemas.rag_operations import FeedbackSubmitRequest

        payload = FeedbackSubmitRequest(feature="assistant_chat", reference_id="msg-1", rating=-1)
        assert payload.rating == -1

    def test_rejects_zero_rating(self):
        from app.schemas.rag_operations import FeedbackSubmitRequest

        with pytest.raises(ValidationError):
            FeedbackSubmitRequest(feature="assistant_chat", reference_id="msg-1", rating=0)

    def test_rejects_out_of_range_rating(self):
        from app.schemas.rag_operations import FeedbackSubmitRequest

        with pytest.raises(ValidationError):
            FeedbackSubmitRequest(feature="assistant_chat", reference_id="msg-1", rating=5)
