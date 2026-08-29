"""
Comprehensive Integration Test Suite for NOVA Evidence Fusion & Dual-Track Assistant Pipeline

Classifications:
- INTEGRATION: Multi-component workflow testing (Assistant + Finding Service + Fusion Engine + Calibrator)
- END-TO-END: Pipeline execution tracing from query to context block and decision gate
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.assistant import assistant_service
from app.services.assistant.evidence_fusion import UnifiedEvidenceItem, evidence_fusion_engine
from app.services.search_analytics.calibrator import confidence_calibrator
from app.services.aggregation.enrichment import enrich_finding


@pytest.mark.asyncio
async def test_knowledge_only_query():
    """1. Knowledge-only query: 'What is the leave policy?'"""
    query = "What is the leave policy?"
    assert not assistant_service.is_security_query(query)

    mock_chunk = MagicMock()
    mock_chunk.document_id = "doc-123"
    mock_chunk.document = MagicMock()
    mock_chunk.document.filename = "Policy.pdf"
    mock_chunk.document.created_at = None
    mock_chunk.heading = "Leave Section"
    mock_chunk.section_path = "HR/Leave"
    mock_chunk.page_number = 2
    mock_chunk.content = "Employees are entitled to 20 days annual leave."

    mock_db = AsyncMock()

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock) as mock_vec, \
         patch("app.services.assistant.assistant_service.rerank_manager.rerank", return_value=[0.90]) as mock_rerank, \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        mock_vec.return_value = [(mock_chunk, 0.85)]

        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        assert mock_vec.called
        assert len(result.citations) == 1
        assert result.citations[0].source_type == "knowledge_doc"
        assert "Policy.pdf" in result.context_block


@pytest.mark.asyncio
async def test_security_only_query():
    """2. Security-only query: 'Show SQL injection findings in auth service'"""
    query = "Show SQL injection findings in auth service"
    assert assistant_service.is_security_query(query)

    mock_db = AsyncMock()

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock) as mock_vec, \
         patch("app.services.assistant.assistant_service.rerank_manager.rerank", return_value=[0.92]) as mock_rerank, \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        mock_vec.return_value = []

        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        assert len(result.citations) >= 1
        assert result.citations[0].source_type == "security_finding"


@pytest.mark.asyncio
async def test_mixed_knowledge_and_security_query():
    """3. Mixed knowledge + security query: 'How do I fix the SQL injection finding in auth.py?'"""
    query = "How do I fix the SQL injection finding in auth.py?"
    assert assistant_service.is_security_query(query)

    mock_db = AsyncMock()
    mock_chunk = MagicMock()
    mock_chunk.document_id = "doc-sqli"
    mock_chunk.document = MagicMock()
    mock_chunk.document.filename = "Secure_Coding_Guide.pdf"
    mock_chunk.document.created_at = None
    mock_chunk.heading = "Parameterized Queries"
    mock_chunk.section_path = "Database"
    mock_chunk.page_number = 5
    mock_chunk.content = "Always use bind parameters or ORM to prevent SQL injection."

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock) as mock_vec, \
         patch("app.services.assistant.assistant_service.rerank_manager.rerank", return_value=[0.90, 0.94]) as mock_rerank, \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        mock_vec.return_value = [(mock_chunk, 0.88)]

        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        assert mock_vec.called
        assert len(result.citations) >= 1


@pytest.mark.asyncio
async def test_no_evidence_query():
    """4. No-evidence query: 'I need information about an unknown vulnerability XYZ123.'"""
    query = "I need information about an unknown vulnerability XYZ123."
    mock_db = AsyncMock()

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock) as mock_vec, \
         patch("app.services.assistant.assistant_service.exa_service.search_fallback", return_value="Exa Web Fallback Result") as mock_exa, \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        mock_vec.return_value = []

        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        assert result.calibrated_trust_score == 0.0
        assert result.exa_fallback_answer == "Exa Web Fallback Result"
        assert mock_exa.called


def test_multiple_scanners_same_finding_and_enrichment():
    """5. Multiple scanners detecting the same finding + cross-scanner confidence calculation."""
    sources_single = ["semgrep"]
    sources_dual = ["semgrep", "joern"]

    conf_single = evidence_fusion_engine.calculate_cross_scanner_confidence(sources_single)
    conf_dual = evidence_fusion_engine.calculate_cross_scanner_confidence(sources_dual)

    assert conf_single == 0.85
    assert conf_dual == 0.9775  # 1 - (1 - 0.85)^2

    # Enrichment integration test
    finding_data = {
        "title": "SQL Injection",
        "category": "sqli",
        "sources": sources_dual,
        "source": "semgrep",
        "severity": "HIGH",
        "file_path": "auth.py",
        "line_number": 42,
    }
    enriched = enrich_finding(finding_data)
    assert enriched["scanner_confidence"] == 0.9775


def test_provenance_preservation():
    """6. Provenance preservation in citations and header formatting."""
    citation_sec = assistant_service.Citation(
        document_id="f-1",
        filename="Security Finding",
        page_number=None,
        section_path=None,
        heading=None,
        similarity_score=0.9775,
        rerank_score=0.95,
        excerpt="Exposed DB connection string.",
        source_type="security_finding",
        file_path="config/db.py",
        line_number=15,
        severity="CRITICAL",
        cwe_id="CWE-798",
        cve="CVE-2026-9999",
    )

    header = assistant_service._citation_header(citation_sec)
    assert "Security Finding [CRITICAL]" in header
    assert "Location: config/db.py:15" in header
    assert "CWE: CWE-798" in header
    assert "CVE: CVE-2026-9999" in header


def test_trust_score_source_reliability():
    """7. Source-aware trust score calculation based on evidence source mix."""
    rel_sec_and_doc = confidence_calibrator.compute_source_reliability(["security_finding", "knowledge_doc"])
    assert rel_sec_and_doc == pytest.approx(0.90)  # (0.95 + 0.85) / 2

    rel_web = confidence_calibrator.compute_source_reliability(["web_search"])
    assert rel_web == 0.70


def test_security_risk_aware_response_policy():
    """8. Security risk-aware response policy threshold enforcement."""
    c_vec = {"C_retrieval": 0.60, "C_agreement": 0.60, "C_citation": 0.60}

    # Normal query with trust 0.72 -> GENERATE
    eval_norm = confidence_calibrator.evaluate_trust_decision(
        trust_score=0.72, c_vector=c_vec, min_thresh=0.70, is_security_query=False
    )
    assert eval_norm["decision"] == "GENERATE"

    # Security query with trust 0.72 -> FALLBACK_WEB (because effective_thresh = 0.75)
    eval_sec = confidence_calibrator.evaluate_trust_decision(
        trust_score=0.72, c_vector=c_vec, min_thresh=0.70, is_security_query=True
    )
    assert eval_sec["decision"] == "FALLBACK_WEB"
    assert "Security query evidence confidence below threshold" in eval_sec["reasons"][0]


@pytest.mark.asyncio
async def test_existing_faq_path():
    """9. Stage 0 FAQ match path continues to work (<1ms execution)."""
    query = "What is NOVA?"
    mock_db = AsyncMock()

    mock_faq = MagicMock()
    mock_faq.response = "NOVA is Neural Orchestrated Vector Assistant."

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock) as mock_faq_match, \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):
        mock_faq_match.return_value = mock_faq
        result = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)

        assert result.sufficient is True
        assert result.faq_match_answer == "NOVA is Neural Orchestrated Vector Assistant."
        assert result.reasoning_trace["stage"] == "Stage 0 (FAQ Axiom Match)"
