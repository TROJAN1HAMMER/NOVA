"""
Comprehensive Test Suite for NLI-Based Pairwise Evidence Consensus Engine

Classifications:
- UNIT: Tests for NLIEngine classification, metadata matching, and relationship mapping
- INTEGRATION: Multi-component workflow testing (Assistant + NLI Consensus + Trust Engine + Decision Gate)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.ai.nli_engine import nli_engine, EvidenceRelationship
from app.services.ai.consensus_engine import consensus_engine
from app.services.search_analytics.calibrator import confidence_calibrator
from app.services.assistant import assistant_service


@pytest.fixture(autouse=True)
def mock_cache_and_rerank():
    """Autouse fixture to mock cache and rerank_manager in unit tests."""
    with patch("app.services.ai.nli_engine.response_cache.get_cached", return_value=None), \
         patch("app.services.ai.nli_engine.response_cache.set_cached", return_value=None), \
         patch("app.services.ai.nli_engine.rerank_manager.rerank", return_value=[0.88]) as mock:
        yield mock


def test_nli_supports_relationship():
    """1. SUPPORTS relationship: Security finding + Remediation guide."""
    item_finding = {
        "source_id": "f-101",
        "source_type": "security_finding",
        "excerpt": "SQL Injection vulnerability detected in app/auth.py line 42 due to unescaped string formatting.",
        "cwe_id": "CWE-89",
        "file_path": "app/auth.py",
    }
    item_remediation = {
        "source_id": "k-202",
        "source_type": "knowledge_doc",
        "excerpt": "To fix CWE-89 SQL injection, use parameterized queries or ORM bind parameters in app/auth.py.",
        "cwe_id": "CWE-89",
        "file_path": "app/auth.py",
    }

    rel = nli_engine.analyze_pair(item_finding, item_remediation)
    assert rel.relationship == "SUPPORTS"
    assert rel.nli_label == "ENTAILMENT"
    assert rel.confidence >= 0.70


def test_nli_contradicts_relationship():
    """2. CONTRADICTS relationship: Conflicting vulnerability status assertions in same file/component."""
    item_vulnerable = {
        "source_id": "f-301",
        "source_type": "security_finding",
        "excerpt": "Critical unpatched SQL injection flaw in auth.py line 42 allows full database bypass.",
        "file_path": "auth.py",
    }
    item_secure = {
        "source_id": "k-302",
        "source_type": "knowledge_doc",
        "excerpt": "auth.py line 42 is secure and not vulnerable to SQL injection after complete parameterization.",
        "file_path": "auth.py",
    }

    rel = nli_engine.analyze_pair(item_vulnerable, item_secure)
    assert rel.relationship == "CONTRADICTS"
    assert rel.nli_label == "CONTRADICTION"
    assert rel.confidence >= 0.80


def test_nli_related_relationship():
    """3. RELATED relationship: Shared topic context without explicit entailment or contradiction."""
    item_a = {
        "source_id": "k-401",
        "source_type": "knowledge_doc",
        "excerpt": "PostgreSQL database connection parameters and SSL configuration settings.",
    }
    item_b = {
        "source_id": "k-402",
        "source_type": "knowledge_doc",
        "excerpt": "Frontend user interface color theme and button style guide.",
    }

    with patch("app.services.ai.nli_engine.rerank_manager.rerank", return_value=[-0.2]):
        rel = nli_engine.analyze_pair(item_a, item_b)
        assert rel.relationship == "RELATED"
        assert rel.nli_label == "NEUTRAL"


def test_nli_unrelated_relationship():
    """4. UNRELATED relationship: Distinct topic scope without semantic alignment."""
    item_hr = {
        "source_id": "k-501",
        "source_type": "knowledge_doc",
        "excerpt": "Employees receive 20 days annual vacation leave per calendar year.",
    }
    item_crypto = {
        "source_id": "f-502",
        "source_type": "security_finding",
        "excerpt": "Weak AES-128 key generation algorithm detected in crypto service.",
    }

    with patch("app.services.ai.nli_engine.rerank_manager.rerank", return_value=[-3.0]):
        rel = nli_engine.analyze_pair(item_hr, item_crypto)
        assert rel.relationship == "UNRELATED"
        assert rel.nli_label == "NEUTRAL"


def test_bidirectional_nli_evaluation():
    """5. Bidirectional NLI evaluation across cross-source evidence set."""
    items = [
        {
            "source_id": "f-1",
            "source_type": "security_finding",
            "excerpt": "XSS flaw in user input rendering.",
            "cwe_id": "CWE-79",
        },
        {
            "source_id": "k-1",
            "source_type": "knowledge_doc",
            "excerpt": "Sanitize user input with HTML escaping to remediate CWE-79 XSS.",
            "cwe_id": "CWE-79",
        },
    ]

    relationships = nli_engine.analyze_evidence_set(items)
    assert len(relationships) == 1
    assert relationships[0].relationship == "SUPPORTS"


def test_metadata_aware_relationship_refinement():
    """6. Metadata-aware refinement using CWE and file_path alignment."""
    item_finding = {
        "source_id": "f-cwe",
        "source_type": "security_finding",
        "excerpt": "Vulnerability identified in authentication module.",
        "cwe_id": "CWE-89",
        "file_path": "auth.py",
    }
    item_guide = {
        "source_id": "k-cwe",
        "source_type": "knowledge_doc",
        "excerpt": "Guide for mitigating SQL injection risks.",
        "cwe_id": "CWE-89",
        "file_path": "auth.py",
    }

    rel = nli_engine.analyze_pair(item_finding, item_guide)
    assert rel.relationship == "SUPPORTS"


def test_consensus_agreement_calculation():
    """7. Consensus agreement score calculation incorporating NLI relationships."""
    items_supported = [
        {"source_id": "f-1", "source_type": "security_finding", "excerpt": "SQL Injection vulnerability in auth.py.", "cwe_id": "CWE-89"},
        {"source_id": "k-1", "source_type": "knowledge_doc", "excerpt": "Use parameterized queries for CWE-89 SQL Injection in auth.py.", "cwe_id": "CWE-89"},
    ]
    agreement_sup, mat_sup = consensus_engine.evaluate_consensus(items_supported)
    assert agreement_sup >= 0.85
    assert mat_sup["support_count"] == 1
    assert mat_sup["contradiction_count"] == 0

    items_contradicted = [
        {"source_id": "f-1", "source_type": "security_finding", "excerpt": "Critical unpatched SQL injection flaw in auth.py line 42.", "file_path": "auth.py"},
        {"source_id": "k-1", "source_type": "knowledge_doc", "excerpt": "auth.py line 42 is secure and not vulnerable to SQL injection.", "file_path": "auth.py"},
    ]
    agreement_con, mat_con = consensus_engine.evaluate_consensus(items_contradicted)
    assert agreement_con <= 0.10  # Contradiction drops agreement severely
    assert mat_con["contradiction_count"] == 1


def test_trust_score_integration_flow():
    """8. Trust score integration flow with NLI agreement input."""
    trust_high = confidence_calibrator.calibrate(
        retrieval_score=0.85, agreement_score=0.90, citation_coverage=0.85, reasoning_score=0.80, freshness_score=0.90
    )[0]

    trust_low = confidence_calibrator.calibrate(
        retrieval_score=0.30, agreement_score=0.10, citation_coverage=0.30, reasoning_score=0.40, freshness_score=0.50
    )[0]

    assert trust_high > trust_low
    assert trust_low < 0.75


def test_high_risk_security_contradiction_fallback():
    """9. High-risk security contradiction drops trust score below threshold, triggering fallback."""
    c_vec = {"C_retrieval": 0.80, "C_agreement": 0.10, "C_citation": 0.70}
    decision = confidence_calibrator.evaluate_trust_decision(
        trust_score=0.55, c_vector=c_vec, min_thresh=0.70, is_security_query=True
    )
    assert decision["decision"] in ["FALLBACK_WEB", "ABSTAIN"]


@pytest.mark.asyncio
async def test_normal_knowledge_query_pipeline():
    """10. Normal knowledge query executes NLI consensus cleanly."""
    query = "What is the leave policy?"
    mock_db = AsyncMock()

    mock_chunk = MagicMock()
    mock_chunk.document_id = "doc-1"
    mock_chunk.document = MagicMock()
    mock_chunk.document.filename = "LeavePolicy.pdf"
    mock_chunk.document.created_at = None
    mock_chunk.heading = "Annual Leave"
    mock_chunk.section_path = "HR"
    mock_chunk.page_number = 1
    mock_chunk.content = "Employees receive 20 days annual leave."

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock) as mock_vec, \
         patch("app.services.assistant.assistant_service.rerank_manager.rerank", return_value=[0.90]), \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        mock_vec.return_value = [(mock_chunk, 0.85)]

        res = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)
        assert res.calibrated_trust_score >= 0.70
        assert res.sufficient is True


@pytest.mark.asyncio
async def test_no_evidence_query_path():
    """11. No evidence query returns 0 trust and triggers web fallback safely."""
    query = "Unknown query XYZ999."
    mock_db = AsyncMock()

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=[]), \
         patch("app.services.assistant.assistant_service.exa_service.search_fallback", return_value="Exa Web Summary") as mock_exa, \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        res = await assistant_service.retrieve_and_orchestrate(mock_db, query=query)
        assert res.calibrated_trust_score == 0.0
        assert res.exa_fallback_answer == "Exa Web Summary"
        assert mock_exa.called


def test_graceful_fallback_on_nli_exception():
    """12. Graceful fallback if NLI engine throws an exception."""
    with patch.object(nli_engine, "analyze_evidence_set", side_effect=RuntimeError("NLI Engine Error")):
        chunks = [{"excerpt": "Text A"}, {"excerpt": "Text B"}]
        agreement, consensus_mat = consensus_engine.evaluate_consensus(chunks)
        assert agreement >= 0.0
        assert consensus_mat["status"] == "evaluated_fallback"
