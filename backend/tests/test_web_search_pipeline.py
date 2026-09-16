"""
Integration tests for NOVA Open-Web Evidence Retrieval & Verification Pipeline.
Tests internal-first policy, explicit external query triggering, evidence normalization,
cross-evidence fusion, reranking, consensus evaluation, and Safety Policy Gate enforcement.
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.assistant import assistant_service
from app.services.assistant.assistant_service import build_context_block, Citation
from app.services.assistant.evidence_fusion import UnifiedEvidenceItem, evidence_fusion_engine
from app.services.web_search.base import ExternalSearchResponse, ExternalSearchResult
from app.services.web_search.service import web_search_service


@pytest.mark.asyncio
async def test_internal_first_policy_does_not_invoke_web_search_when_internal_is_sufficient():
    """When internal knowledge vector search finds sufficient high-confidence documents,
    web search is never invoked."""
    query = "What is the company password rotation policy?"
    mock_db = AsyncMock()

    mock_chunk = MagicMock()
    mock_chunk.id = "chunk-1"
    mock_chunk.document_id = "doc-1"
    mock_chunk.content = "All corporate passwords must be changed every 90 days and contain 16 characters."
    mock_chunk.page_number = 3
    mock_chunk.section_path = "Security Policy > Section 4"
    mock_chunk.heading = "Password Rotation"
    mock_chunk.created_at = datetime.now(timezone.utc)
    mock_chunk.document = MagicMock(filename="corp_security_policy.pdf")

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=[(mock_chunk, 0.95)]), \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={"rag.enable_web_search": True}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock), \
         patch.object(web_search_service, "search", new_callable=AsyncMock) as mock_web_search:

        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        # Web search must NOT have been called
        assert not mock_web_search.called
        assert result.sufficient is True
        assert result.calibrated_trust_score > 0.70
        assert result.citations[0].source_type == "knowledge_doc"
        assert result.citations[0].filename == "corp_security_policy.pdf"
        assert result.reasoning_trace.get("fallback_triggered") is False


@pytest.mark.asyncio
async def test_explicit_external_query_triggers_web_retrieval_and_normalizes_provenance():
    """When query explicitly requests internet/web search, external search is triggered
    and evidence items are normalized with full provenance."""
    query = "Search online for latest React frontend architecture patterns"
    mock_db = AsyncMock()

    mock_search_response = ExternalSearchResponse(
        query=query,
        provider="tavily",
        status="SUCCESS",
        source_count=2,
        latency_ms=120.0,
        results=[
            ExternalSearchResult(
                title="React Architecture Principles",
                url="https://react.dev/learn",
                snippet="Modern React architecture emphasizes composition, server components, and unidirectional data flow.",
                raw_score=0.95,
                provider="tavily",
                domain="react.dev",
                published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            ),
            ExternalSearchResult(
                title="Frontend Architecture Best Practices",
                url="https://developer.mozilla.org/react-guide",
                snippet="Unidirectional state management and component modularity form the basis of scalable frontend architecture.",
                raw_score=0.92,
                provider="tavily",
                domain="developer.mozilla.org",
                published_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
            )
        ]
    )

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=[]), \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={"rag.enable_web_search": True}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock), \
         patch.object(web_search_service, "search", new_callable=AsyncMock, return_value=mock_search_response), \
         patch.object(web_search_service, "is_available", return_value=True):

        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        assert result.sufficient is True
        assert len(result.citations) >= 1
        web_citations = [c for c in result.citations if c.source_type == "EXTERNAL_WEB"]
        assert len(web_citations) >= 1
        top_citation = web_citations[0]
        assert top_citation.source_type == "EXTERNAL_WEB"
        assert top_citation.domain in ("react.dev", "developer.mozilla.org")
        assert top_citation.url.startswith("https://")
        assert top_citation.published_at is not None
        assert result.reasoning_trace.get("fallback_triggered") is True
        assert "web_search" in result.reasoning_trace
        assert result.reasoning_trace["web_search"]["provider"] == "tavily"


@pytest.mark.asyncio
async def test_untrusted_web_evidence_delimiter_in_context_block():
    """Validates that external web evidence excerpts are strictly delimited by
    <<<BEGIN_UNTRUSTED_WEB_EVIDENCE>>> ... <<<END_UNTRUSTED_WEB_EVIDENCE>>> in the context block."""
    citations = [
        Citation(
            document_id="doc-1",
            filename="Local Policy",
            page_number=1,
            section_path="Internal",
            heading="Internal",
            similarity_score=0.9,
            rerank_score=0.9,
            excerpt="Internal corporate standard excerpt.",
            source_type="knowledge_doc",
        ),
        Citation(
            document_id="ext-1",
            filename="External Guide",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.85,
            rerank_score=0.85,
            excerpt="External web snippet text from search.",
            source_type="EXTERNAL_WEB",
            url="https://csrc.nist.gov/guide",
            domain="nist.gov",
            published_at="2024-02-01",
        )
    ]

    context_block = build_context_block(citations)

    # First citation is internal and not wrapped in untrusted block
    assert "Internal corporate standard excerpt." in context_block
    assert "<<<BEGIN_UNTRUSTED_WEB_EVIDENCE source=\"knowledge_doc\">>>" not in context_block

    # Second citation is external and MUST be wrapped
    assert "<<<BEGIN_UNTRUSTED_WEB_EVIDENCE source=\"nist.gov\">>>" in context_block
    assert "External web snippet text from search." in context_block
    assert "<<<END_UNTRUSTED_WEB_EVIDENCE>>>" in context_block


@pytest.mark.asyncio
async def test_contradictory_web_evidence_triggers_safety_gate_abstain():
    """When external evidence strongly contradicts other findings, consensus evaluation
    detects critical contradiction and the Safety Policy Gate authoritatively abstains."""
    query = "Is TLS 1.0 approved for customer authentication?"
    mock_db = AsyncMock()

    # Create two contradicting external items
    mock_search_response = ExternalSearchResponse(
        query=query,
        provider="tavily",
        status="SUCCESS",
        source_count=2,
        results=[
            ExternalSearchResult(
                title="Deprecated Standards",
                url="https://csrc.nist.gov/deprecated",
                snippet="TLS 1.0 is strictly prohibited and completely deprecated due to severe cryptographic flaws.",
                raw_score=0.90,
                provider="tavily",
                domain="nist.gov",
            ),
            ExternalSearchResult(
                title="Legacy Blog Post",
                url="https://legacy-blog.com/tls",
                snippet="TLS 1.0 is fully approved and recommended for customer authentication in all systems.",
                raw_score=0.85,
                provider="tavily",
                domain="legacy-blog.com",
            )
        ]
    )

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=[]), \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={"rag.enable_web_search": True}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock), \
         patch("app.services.assistant.assistant_service.consensus_engine.evaluate_consensus", return_value=(0.10, {"status": "contradiction", "contradiction_count": 2, "agreement_score": 0.10})), \
         patch.object(web_search_service, "search", new_callable=AsyncMock, return_value=mock_search_response), \
         patch.object(web_search_service, "is_available", return_value=True):

        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        # Safety Policy Gate evaluates the contradiction
        decision = result.reasoning_trace.get("trust_decision")
        assert decision == "ABSTAIN"
        assert result.sufficient is False
        assert result.reasoning_trace.get("safety_explanation", {}).get("policy_trigger") == "CRITICAL_CONTRADICTION"
