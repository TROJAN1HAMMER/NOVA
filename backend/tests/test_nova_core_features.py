"""
Unit and Integration Tests for NOVA Patent-Defensible Core Features:
- 8-Vector Dynamic Confidence Calibrator
- Unified Evidence Fusion Engine
- Cross-Scanner Confidence Boosting
- Security Finding Evidence Formatting
"""

import pytest
from datetime import datetime, timezone
from app.services.search_analytics.calibrator import confidence_calibrator
from app.services.assistant.evidence_fusion import UnifiedEvidenceItem, evidence_fusion_engine


def test_confidence_calibrator_dynamic_freshness():
    now = datetime.now(timezone.utc)
    freshness_high = confidence_calibrator.compute_freshness([now])
    assert freshness_high >= 0.99

    freshness_none = confidence_calibrator.compute_freshness([])
    assert freshness_none == 0.75


def test_confidence_calibrator_source_reliability():
    rel_sec = confidence_calibrator.compute_source_reliability(["security_finding", "official_doc"])
    assert rel_sec == 0.95

    rel_web = confidence_calibrator.compute_source_reliability(["web_search"])
    assert rel_web == 0.70


def test_cross_scanner_confidence_boost():
    single = evidence_fusion_engine.calculate_cross_scanner_confidence(["semgrep"])
    assert single == 0.85

    dual = evidence_fusion_engine.calculate_cross_scanner_confidence(["semgrep", "joern"])
    assert dual > 0.95

    triple = evidence_fusion_engine.calculate_cross_scanner_confidence(["semgrep", "joern", "secrets"])
    assert triple > 0.99


def test_evidence_fusion_ranking():
    k_item = UnifiedEvidenceItem(
        source_type="knowledge_doc",
        source_id="k1",
        title="Doc 1",
        content="Excerpt 1",
        similarity_score=0.80,
        rerank_score=0.80,
        reliability_weight=0.85,
    )
    s_item = UnifiedEvidenceItem(
        source_type="security_finding",
        source_id="s1",
        title="Finding 1",
        content="Finding excerpt",
        similarity_score=0.95,
        rerank_score=0.95,
        reliability_weight=0.95,
    )

    fused = evidence_fusion_engine.fuse_evidence([k_item], [s_item], top_k=2)
    assert len(fused) == 2
    assert fused[0].source_type == "security_finding"  # Higher weighted score
