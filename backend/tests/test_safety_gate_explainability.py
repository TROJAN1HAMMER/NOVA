"""
Comprehensive Test Suite for NOVA Explainable Safety Gate / Contradiction Explanation
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.assistant import assistant_service
from app.services.search_analytics.calibrator import confidence_calibrator
from app.services.ai.nli_engine import nli_engine
from app.services.ai.consensus_engine import consensus_engine


@pytest.mark.asyncio
async def test_1_strong_supporting_evidence_generate():
    """1. Strong supporting evidence -> GENERATE decision."""
    trust_eval = {"trust_score": 0.92, "decision": "GENERATE"}
    c_vector = {"C_retrieval": 0.88, "C_agreement": 0.95, "C_citation": 0.90}
    citations = [
        assistant_service.Citation(
            document_id="doc-sup-1",
            filename="Policy.pdf",
            page_number=1,
            section_path="Access Control",
            heading="Passwords",
            similarity_score=0.90,
            rerank_score=0.92,
            excerpt="Passwords must be at least 16 characters in length.",
        )
    ]
    consensus_mat = {"contradiction_count": 0, "relationships": []}

    exp = confidence_calibrator.build_safety_explanation(
        trust_eval=trust_eval,
        c_vector=c_vector,
        consensus_mat=consensus_mat,
        citations=citations,
        is_security_query=False,
    )

    assert exp["decision"] == "GENERATE"
    assert exp["policy_trigger"] == "NORMAL_CONFIRMED"
    assert exp["contradiction_count"] == 0
    assert len(exp["supporting_evidence"]) == 1
    assert "Answer generated from trusted evidence" in exp["explanation"]


@pytest.mark.asyncio
async def test_2_no_evidence_fallback():
    """2. No evidence -> FALLBACK/ABSTAIN decision."""
    trust_eval = {"trust_score": 0.0, "decision": "FALLBACK_WEB"}
    c_vector = {"C_retrieval": 0.0, "C_agreement": 1.0, "C_citation": 0.0}

    exp = confidence_calibrator.build_safety_explanation(
        trust_eval=trust_eval,
        c_vector=c_vector,
        consensus_mat={"contradiction_count": 0, "relationships": []},
        citations=[],
        is_security_query=False,
    )

    assert exp["decision"] == "FALLBACK_WEB"
    assert exp["policy_trigger"] == "LOW_RETRIEVAL_SIMILARITY"
    assert len(exp["supporting_evidence"]) == 0
    assert "Vector retrieval similarity (0.00)" in exp["explanation"]


@pytest.mark.asyncio
async def test_3_explicit_contradiction_fallback():
    """3. Explicit contradiction -> FALLBACK decision & CRITICAL_CONTRADICTION trigger."""
    trust_eval = {"trust_score": 0.98, "decision": "FALLBACK_WEB"}
    c_vector = {"C_retrieval": 0.95, "C_agreement": 0.10, "C_citation": 0.90}
    citations = [
        assistant_service.Citation(
            document_id="f-vuln",
            filename="auth.py",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.95,
            rerank_score=0.95,
            excerpt="Critical unpatched SQL injection flaw in auth.py line 42 allows database bypass.",
            source_type="security_finding",
            file_path="auth.py",
            line_number=42,
            severity="CRITICAL",
            cwe_id="CWE-89",
        ),
        assistant_service.Citation(
            document_id="k-sec",
            filename="auth.py",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.92,
            rerank_score=0.92,
            excerpt="auth.py line 42 is secure and not vulnerable to SQL injection after parameterization.",
            source_type="knowledge_doc",
            file_path="auth.py",
            line_number=42,
        ),
    ]
    consensus_mat = {
        "contradiction_count": 1,
        "relationships": [
            {
                "item_a_id": "f-vuln",
                "item_b_id": "k-sec",
                "relationship": "CONTRADICTS",
                "confidence": 0.91,
                "item_a_excerpt": citations[0].excerpt,
                "item_b_excerpt": citations[1].excerpt,
            }
        ],
    }

    exp = confidence_calibrator.build_safety_explanation(
        trust_eval=trust_eval,
        c_vector=c_vector,
        consensus_mat=consensus_mat,
        citations=citations,
        is_security_query=True,
    )

    assert exp["decision"] == "FALLBACK_WEB"
    assert exp["policy_trigger"] == "CRITICAL_CONTRADICTION"
    assert exp["evidence_relationship"] == "CONTRADICTS"
    assert exp["nli_confidence"] == 0.91
    assert len(exp["contradicting_evidence"]) == 2
    assert exp["contradicting_evidence"][0]["source_id"] == "f-vuln"
    assert exp["contradicting_evidence"][1]["source_id"] == "k-sec"
    assert "Two evidence items" in exp["explanation"]
    assert "auth.py:42" in exp["explanation"]


@pytest.mark.asyncio
async def test_4_implicit_security_contradiction_fallback():
    """4. Implicit security contradiction -> FALLBACK decision."""
    trust_eval = {"trust_score": 0.94, "decision": "FALLBACK_WEB"}
    c_vector = {"C_retrieval": 0.90, "C_agreement": 0.10, "C_citation": 0.85}
    citations = [
        assistant_service.Citation(
            document_id="f-impl-1",
            filename="auth.py",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.90,
            rerank_score=0.90,
            excerpt="auth.py line 42 allows full database bypass.",
            file_path="auth.py",
            line_number=42,
        ),
        assistant_service.Citation(
            document_id="f-impl-2",
            filename="auth.py",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.88,
            rerank_score=0.88,
            excerpt="auth.py line 42 validates user authorization tokens.",
            file_path="auth.py",
            line_number=42,
        ),
    ]
    consensus_mat = {
        "contradiction_count": 1,
        "relationships": [
            {
                "item_a_id": "f-impl-1",
                "item_b_id": "f-impl-2",
                "relationship": "CONTRADICTS",
                "confidence": 0.88,
                "item_a_excerpt": citations[0].excerpt,
                "item_b_excerpt": citations[1].excerpt,
            }
        ],
    }

    exp = confidence_calibrator.build_safety_explanation(
        trust_eval=trust_eval,
        c_vector=c_vector,
        consensus_mat=consensus_mat,
        citations=citations,
        is_security_query=True,
    )

    assert exp["policy_trigger"] == "CRITICAL_CONTRADICTION"
    assert exp["evidence_relationship"] == "CONTRADICTS"
    assert exp["contradicting_evidence"][0]["security_property"] == "AUTHORIZATION_AUTHENTICATION"


@pytest.mark.asyncio
async def test_5_mixed_support_and_contradiction_fallback():
    """5. Mixed support + contradiction -> FALLBACK decision overrides support."""
    trust_eval = {"trust_score": 0.85, "decision": "FALLBACK_WEB"}
    c_vector = {"C_retrieval": 0.85, "C_agreement": 0.10, "C_citation": 0.80}
    consensus_mat = {
        "contradiction_count": 1,
        "relationships": [
            {"item_a_id": "a", "item_b_id": "b", "relationship": "SUPPORTS", "confidence": 0.90},
            {"item_a_id": "b", "item_b_id": "c", "relationship": "CONTRADICTS", "confidence": 0.89},
        ],
    }

    exp = confidence_calibrator.build_safety_explanation(
        trust_eval=trust_eval,
        c_vector=c_vector,
        consensus_mat=consensus_mat,
        citations=[],
        is_security_query=True,
    )

    assert exp["decision"] == "FALLBACK_WEB"
    assert exp["policy_trigger"] == "CRITICAL_CONTRADICTION"


@pytest.mark.asyncio
async def test_6_remediation_guidance_generate():
    """6. Remediation guidance -> GENERATE decision."""
    trust_eval = {"trust_score": 0.95, "decision": "GENERATE"}
    c_vector = {"C_retrieval": 0.92, "C_agreement": 0.95, "C_citation": 0.90}
    citations = [
        assistant_service.Citation(
            document_id="f-rem-1",
            filename="auth.py",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.95,
            rerank_score=0.95,
            excerpt="SQL Injection vulnerability in auth.py line 42.",
            source_type="security_finding",
            cwe_id="CWE-89",
        ),
        assistant_service.Citation(
            document_id="k-rem-2",
            filename="Remediation_Guide.pdf",
            page_number=3,
            section_path="Fixes",
            heading="SQLi Fix",
            similarity_score=0.90,
            rerank_score=0.90,
            excerpt="To fix CWE-89 SQL Injection in auth.py line 42, use parameterized queries.",
            source_type="knowledge_doc",
            cwe_id="CWE-89",
        ),
    ]
    consensus_mat = {
        "contradiction_count": 0,
        "relationships": [{"item_a_id": "f-rem-1", "item_b_id": "k-rem-2", "relationship": "SUPPORTS", "confidence": 0.92}],
    }

    exp = confidence_calibrator.build_safety_explanation(
        trust_eval=trust_eval,
        c_vector=c_vector,
        consensus_mat=consensus_mat,
        citations=citations,
        is_security_query=True,
    )

    assert exp["decision"] == "GENERATE"
    assert exp["policy_trigger"] == "NORMAL_CONFIRMED"


@pytest.mark.asyncio
async def test_7_explanation_contains_correct_evidence_ids():
    """7. Explanation contains correct evidence IDs."""
    citations = [
        assistant_service.Citation(
            document_id="ID_ALPHA_123",
            filename="alpha.py",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.9,
            rerank_score=0.9,
            excerpt="Alpha code excerpt.",
        ),
        assistant_service.Citation(
            document_id="ID_BETA_456",
            filename="beta.py",
            page_number=None,
            section_path=None,
            heading=None,
            similarity_score=0.9,
            rerank_score=0.9,
            excerpt="Beta code excerpt.",
        ),
    ]
    consensus_mat = {
        "contradiction_count": 1,
        "relationships": [
            {
                "item_a_id": "ID_ALPHA_123",
                "item_b_id": "ID_BETA_456",
                "relationship": "CONTRADICTS",
                "confidence": 0.95,
            }
        ],
    }

    exp = confidence_calibrator.build_safety_explanation(
        trust_eval={"trust_score": 0.9, "decision": "FALLBACK_WEB"},
        c_vector={"C_retrieval": 0.9, "C_agreement": 0.1},
        consensus_mat=consensus_mat,
        citations=citations,
        is_security_query=True,
    )

    assert exp["contradicting_evidence"][0]["source_id"] == "ID_ALPHA_123"
    assert exp["contradicting_evidence"][1]["source_id"] == "ID_BETA_456"


@pytest.mark.asyncio
async def test_8_explanation_contains_correct_policy_trigger():
    """8. Explanation contains correct policy trigger."""
    exp = confidence_calibrator.build_safety_explanation(
        trust_eval={"trust_score": 0.60, "decision": "FALLBACK_WEB"},
        c_vector={"C_retrieval": 0.9, "C_agreement": 0.9},
        consensus_mat={"contradiction_count": 0, "relationships": []},
        citations=[],
        is_security_query=True,
    )
    assert exp["policy_trigger"] == "SECURITY_QUERY_LOW_CONFIDENCE"


@pytest.mark.asyncio
async def test_9_existing_assistant_response_remains_compatible():
    """9. Existing assistant response contract remains backward compatible."""
    mock_db = AsyncMock()
    mock_chunk = MagicMock()
    mock_chunk.document_id = "doc-compat-1"
    mock_chunk.document = MagicMock()
    mock_chunk.document.filename = "Guide.pdf"
    mock_chunk.document.created_at = None
    mock_chunk.heading = "Intro"
    mock_chunk.section_path = "Main"
    mock_chunk.page_number = 1
    mock_chunk.content = "General guide text."

    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=[(mock_chunk, 0.85)]), \
         patch("app.services.assistant.assistant_service.rerank_manager.rerank", return_value=[0.90]), \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        res = await assistant_service.retrieve_and_orchestrate(mock_db, query="What is the guide?")

        assert hasattr(res, "citations")
        assert hasattr(res, "reasoning_trace")
        assert "safety_explanation" in res.reasoning_trace
        assert res.reasoning_trace["safety_explanation"]["decision"] in ["GENERATE", "FALLBACK_WEB"]
