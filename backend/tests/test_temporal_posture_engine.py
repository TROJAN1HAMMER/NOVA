"""
Comprehensive Test Suite for NOVA Temporal Security Posture & Trend Engine
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.security_intelligence.posture_trend_engine import posture_trend_engine
from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator
from app.services.security_intelligence.evidence_provider import security_evidence_provider
from app.services.assistant import assistant_service


def test_1_first_posture_snapshot():
    """1. First posture snapshot yields None delta and FIRST_RUN trend."""
    delta, trend = posture_trend_engine.compute_delta_and_trend(98.2, None)
    assert delta is None
    assert trend == "FIRST_RUN"


def test_2_second_snapshot_delta():
    """2. Second snapshot computes valid delta."""
    delta, trend = posture_trend_engine.compute_delta_and_trend(95.0, 98.0)
    assert delta == -3.0
    assert trend == "DEGRADED"


def test_3_positive_posture_delta():
    """3. Positive posture delta classifies as IMPROVED."""
    delta, trend = posture_trend_engine.compute_delta_and_trend(98.5, 92.0)
    assert delta == +6.5
    assert trend == "IMPROVED"


def test_4_negative_posture_delta():
    """4. Negative posture delta classifies as DEGRADED."""
    delta, trend = posture_trend_engine.compute_delta_and_trend(85.0, 95.0)
    assert delta == -10.0
    assert trend == "DEGRADED"


def test_5_unchanged_posture():
    """5. Small delta within threshold classifies as UNCHANGED."""
    delta, trend = posture_trend_engine.compute_delta_and_trend(95.5, 95.0)
    assert delta == +0.5
    assert trend == "UNCHANGED"


def test_6_new_risk_detection():
    """6. New risk detection between runs."""
    prev = [{"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"}]
    curr = [
        {"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"},
        {"risk_type": "XSS", "affected_scope": "profile.py", "status": "OPEN"},
    ]
    evol = posture_trend_engine.compute_risk_evolution(curr, prev)
    assert evol["new_risks_count"] == 1
    assert evol["new_risks"][0]["affected_scope"] == "profile.py"


def test_7_resolved_risk_detection():
    """7. Resolved risk detection when risk is fixed."""
    prev = [
        {"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"},
        {"risk_type": "XSS", "affected_scope": "profile.py", "status": "OPEN"},
    ]
    curr = [{"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"}]
    evol = posture_trend_engine.compute_risk_evolution(curr, prev)
    assert evol["resolved_risks_count"] == 1
    assert evol["resolved_risks"][0]["affected_scope"] == "profile.py"


def test_8_persistent_risk_detection():
    """8. Persistent risk detection across runs."""
    prev = [{"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"}]
    curr = [{"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"}]
    evol = posture_trend_engine.compute_risk_evolution(curr, prev)
    assert evol["persistent_risks_count"] == 1


def test_9_multiple_risk_changes():
    """9. Multiple new and resolved risk changes simultaneously."""
    prev = [{"risk_type": "R1", "affected_scope": "a.py", "status": "OPEN"}]
    curr = [{"risk_type": "R2", "affected_scope": "b.py", "status": "OPEN"}]
    evol = posture_trend_engine.compute_risk_evolution(curr, prev)
    assert evol["new_risks_count"] == 1
    assert evol["resolved_risks_count"] == 1


def test_10_correct_scope_isolation():
    """10. History isolation by target_scope."""
    res_a = security_intelligence_orchestrator.run_full_analysis("repo_A")
    res_b = security_intelligence_orchestrator.run_full_analysis("repo_B")

    hist_a = security_intelligence_orchestrator.get_posture_history("repo_A")
    hist_b = security_intelligence_orchestrator.get_posture_history("repo_B")

    assert len(hist_a) >= 1
    assert len(hist_b) >= 1
    assert hist_a[0]["target_scope"] == "repo_A"
    assert hist_b[0]["target_scope"] == "repo_B"


def test_11_api_history_response():
    """11. Orchestrator returns snapshot and history array."""
    res = security_intelligence_orchestrator.run_full_analysis("repo_test_api")
    assert "snapshot" in res
    assert "posture" in res
    assert res["snapshot"]["target_scope"] == "repo_test_api"


def test_12_security_evidence_provider_temporal_evidence():
    """12. SecurityEvidenceProvider exports temporal posture item."""
    security_intelligence_orchestrator.run_full_analysis(".")
    ev_items = security_evidence_provider.get_security_evidence("posture trend changed")
    posture_items = [i for i in ev_items if "posture" in i["title"].lower() or "posture" in i["content"].lower()]
    assert len(posture_items) >= 1
    assert posture_items[0]["reliability_weight"] == 0.95


@pytest.mark.asyncio
async def test_13_assistant_temporal_evidence_retrieval():
    """13. Assistant RAG retrieves temporal posture evidence."""
    mock_db = AsyncMock()
    with patch("app.services.assistant.assistant_service.faq_service.match_faq", new_callable=AsyncMock, return_value=None), \
         patch("app.services.assistant.assistant_service.vector_store.similarity_search", new_callable=AsyncMock, return_value=[]), \
         patch("app.services.assistant.assistant_service.rerank_manager.rerank", return_value=[0.92]), \
         patch("app.services.assistant.assistant_service.settings_service.get_settings", new_callable=AsyncMock, return_value={}), \
         patch("app.services.assistant.assistant_service.analytics_service.log_search", new_callable=AsyncMock):

        res = await assistant_service.retrieve_and_orchestrate(mock_db, query="How has our security posture changed?")
        assert res.retrieved_count >= 1
        assert any(c.source_type == "security_finding" for c in res.citations)


def test_14_no_historical_data_handling():
    """14. Graceful first-run output without historical snapshot."""
    snap = posture_trend_engine.generate_snapshot_record(
        analysis_run_id="run-0",
        target_scope="empty_repo",
        assets=[],
        controls=[],
        assessments=[],
        previous_snapshot=None,
        previous_assessments=None,
    )
    assert snap["delta_score"] is None
    assert snap["trend_direction"] == "FIRST_RUN"


def test_15_existing_security_intelligence_regression():
    """15. Verified existing Security Intelligence orchestrator executes cleanly."""
    res = security_intelligence_orchestrator.run_full_analysis(".")
    assert res["status"] == "COMPLETED"
    assert "assessments" in res
    assert "context_graph" in res


def test_16_existing_trust_nli_regression():
    """16. Regression check that TrustScore calibrator & NLI continue working."""
    from app.services.search_analytics.calibrator import confidence_calibrator
    trust, c_vec = confidence_calibrator.calibrate(retrieval_score=0.90, agreement_score=0.95)
    assert trust >= 0.70
    assert "C_retrieval" in c_vec
