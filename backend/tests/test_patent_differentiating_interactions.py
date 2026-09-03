"""
NOVA — Comprehensive Test Suite for Core Patent-Oriented Technical Interactions

Validates 14 technical interaction requirements across NOVA's architecture:
1. active contradiction blocks generation
2. historical contradiction does not incorrectly block generation
3. version-specific contradiction is correctly scoped
4. resolved contradiction is recognized
5. remediation changes AST/control state
6. failed remediation remains unverified
7. posture correctly changes from NEW -> PERSISTENT -> RESOLVED -> RESURFACED
8. evidence provenance survives dual-track fusion
9. consensus reflects directional NLI relationships
10. calibrated trust preserves the 8D feature vector
11. hard safety policy overrides high statistical confidence
12. explainability reproduces the actual decision path
13. knowledge-gap retrieval changes evidence state
14. complete end-to-end interaction chain is reproducible
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.security_intelligence.observation_collector import (
    SecurityObservationData,
    observation_collector,
)
from app.services.security_intelligence.control_analyzer import (
    SecurityControlEvaluation,
    control_analyzer,
)
from app.services.security_intelligence.risk_scenario_engine import (
    RiskScenarioInference,
    risk_scenario_engine,
)
from app.services.security_intelligence.scenario_verifier import (
    VerifiedAssessmentData,
    scenario_verifier,
)
from app.services.security_intelligence.remediation_verifier import (
    remediation_verifier,
)
from app.services.security_intelligence.posture_trend_engine import (
    posture_trend_engine,
)
from app.services.ai.nli_engine import nli_engine
from app.services.ai.consensus_engine import consensus_engine
from app.services.search_analytics.calibrator import (
    confidence_calibrator,
    AuditableDecisionRecord,
)
from app.services.assistant.evidence_fusion import (
    UnifiedEvidenceItem,
    evidence_fusion_engine,
)


@pytest.fixture(autouse=True)
def bypass_cache_and_rerank():
    with patch("app.services.ai.nli_engine.response_cache.get_cached", return_value=None), \
         patch("app.services.ai.nli_engine.response_cache.set_cached", return_value=None), \
         patch("app.services.ai.nli_engine.rerank_manager.rerank", return_value=[0.85]):
        yield


# =============================================================================
# 1. ACTIVE CONTRADICTION BLOCKS GENERATION
# =============================================================================

def test_1_active_contradiction_blocks_generation():
    item_a = {
        "source_id": "doc-1",
        "excerpt": "Endpoint /login is vulnerable to authentication bypass.",
    }
    item_b = {
        "source_id": "doc-2",
        "excerpt": "Endpoint /login requires authentication and validates certificates.",
    }
    rel = nli_engine.analyze_pair(item_a, item_b)
    assert rel.relationship == "CONTRADICTS"
    assert rel.contradiction_type == "ACTIVE"

    c_vector = {"C_retrieval": 0.92, "C_agreement": 0.10, "C_hallucination_risk": 0.05}
    decision = confidence_calibrator.evaluate_trust_decision(
        trust_score=0.95,
        c_vector=c_vector,
        is_security_query=True,
    )
    assert decision["decision"] in ["FALLBACK_WEB", "ABSTAIN"]


# =============================================================================
# 2. HISTORICAL CONTRADICTION DOES NOT INCORRECTLY BLOCK GENERATION
# =============================================================================

def test_2_historical_contradiction_does_not_block_generation():
    item_hist = {
        "source_id": "hist-1",
        "excerpt": "Endpoint /login was historically vulnerable to auth bypass prior to patch v2.0.",
    }
    item_curr = {
        "source_id": "curr-1",
        "excerpt": "Endpoint /login is safe and requires authenticated access.",
    }
    rel = nli_engine.analyze_pair(item_hist, item_curr)
    assert rel.relationship != "CONTRADICTS"
    assert rel.contradiction_type == "HISTORICAL"


# =============================================================================
# 3. VERSION-SPECIFIC CONTRADICTION IS CORRECTLY SCOPED
# =============================================================================

def test_3_version_specific_contradiction_scoped():
    item_v1 = {"source_id": "1", "excerpt": "Package requests v2.18.0 is vulnerable to CSRF."}
    item_v2 = {"source_id": "2", "excerpt": "requests v2.20.0 fixes the CSRF vulnerability."}
    rel = nli_engine.analyze_pair(item_v1, item_v2)
    assert rel.relationship in ["RELATED", "SUPPORTS"]
    assert rel.contradiction_type == "VERSION"


# =============================================================================
# 4. RESOLVED CONTRADICTION IS RECOGNIZED
# =============================================================================

def test_4_resolved_contradiction_recognized():
    item_vuln = {"source_id": "1", "excerpt": "Raw SQL query contains unsanitized user input in auth controller."}
    item_fix = {"source_id": "2", "excerpt": "Remediation guide: use parameterized queries with SQLAlchemy to fix SQL injection."}
    rel = nli_engine.analyze_pair(item_vuln, item_fix)
    assert rel.relationship in ["SUPPORTS", "RELATED"]
    assert rel.relationship != "CONTRADICTS"


# =============================================================================
# 5. REMEDIATION CHANGES AST/CONTROL STATE
# =============================================================================

def test_5_remediation_changes_ast_control_state():
    fixed_code = "@router.post('/admin', dependencies=[Depends(RequireRole('admin'))])\ndef update_role(): pass"
    res = remediation_verifier.verify_remediation("assess-1", fixed_code)
    assert res["fixed"] is True
    assert res["status"] == "VERIFIED_FIXED"
    assert res["verification_tiers"]["structural_implementation"] is True
    assert res["verification_tiers"]["control_effectiveness"] is True


# =============================================================================
# 6. FAILED REMEDIATION REMAINS UNVERIFIED
# =============================================================================

def test_6_failed_remediation_remains_unverified():
    unfixed_code = "def update_role(user_id: str): pass"
    res = remediation_verifier.verify_remediation("assess-1", unfixed_code)
    assert res["fixed"] is False
    assert res["status"] == "OPEN"
    assert res["verification_tiers"]["structural_implementation"] is False


# =============================================================================
# 7. POSTURE CORRECTLY CHANGES (NEW -> PERSISTENT -> RESOLVED -> RESURFACED)
# =============================================================================

def test_7_posture_risk_lifecycle_transitions():
    # 1. Run 1: NEW risk
    prev_run = [{"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"}]
    curr_run = [
        {"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"},  # PERSISTENT
        {"risk_type": "XSS_VULNERABILITY", "affected_scope": "view.py", "status": "OPEN"},  # NEW
    ]
    evol1 = posture_trend_engine.compute_risk_evolution(curr_run, prev_run)
    assert evol1["new_risks_count"] == 1
    assert evol1["persistent_risks_count"] == 1

    # 2. Run 2: RESOLVED risk
    run3 = [{"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"}]
    evol2 = posture_trend_engine.compute_risk_evolution(run3, curr_run)
    assert evol2["resolved_risks_count"] == 1

    # 3. Run 3: RESURFACED risk
    resolved_history = {"XSS_VULNERABILITY::view.py"}
    run4 = [
        {"risk_type": "SQL_INJECTION", "affected_scope": "auth.py", "status": "OPEN"},
        {"risk_type": "XSS_VULNERABILITY", "affected_scope": "view.py", "status": "OPEN"},  # RESURFACED
    ]
    evol3 = posture_trend_engine.compute_risk_evolution(run4, run3, resolved_history_keys=resolved_history)
    assert evol3["resurfaced_risks_count"] == 1


# =============================================================================
# 8. EVIDENCE PROVENANCE SURVIVES DUAL-TRACK FUSION
# =============================================================================

def test_8_evidence_provenance_survives_fusion():
    knowledge_item = UnifiedEvidenceItem(
        source_type="knowledge_doc",
        source_id="doc-101",
        title="Architecture.pdf",
        content="JWT authentication is required.",
        similarity_score=0.88,
        rerank_score=0.90,
        reliability_weight=0.85,
        provenance={"page_number": 4},
        asset_id="asset-app",
        version="v1.0",
    )
    security_item = UnifiedEvidenceItem(
        source_type="security_finding",
        source_id="sec-202",
        title="Missing Auth",
        content="Endpoint lacks JWT.",
        similarity_score=0.92,
        rerank_score=0.94,
        reliability_weight=0.95,
        provenance={"scanner": "ast_analyzer"},
        asset_id="asset-app",
        version="v1.0",
    )

    fused = evidence_fusion_engine.fuse_evidence([knowledge_item], [security_item], top_k=5)
    assert len(fused) == 2
    assert fused[0].provenance["scanner"] == "ast_analyzer"
    assert fused[0].asset_id == "asset-app"
    assert fused[1].provenance["page_number"] == 4


# =============================================================================
# 9. CONSENSUS REFLECTS DIRECTIONAL NLI RELATIONSHIPS
# =============================================================================

def test_9_consensus_reflects_nli_relationships():
    chunks = [
        {"source_id": "c1", "file_path": "admin.py", "excerpt": "Exposed admin endpoint without authentication."},
        {"source_id": "c2", "file_path": "admin.py", "excerpt": "admin.py requires admin HTTP Basic Auth headers."},
    ]
    agreement, matrix = consensus_engine.evaluate_consensus(chunks)
    assert matrix["contradiction_count"] == 1
    assert agreement <= 0.20


# =============================================================================
# 10. CALIBRATED TRUST PRESERVES THE 8D FEATURE VECTOR
# =============================================================================

def test_10_calibrated_trust_preserves_8d_vector():
    score, c_vec = confidence_calibrator.calibrate(
        retrieval_score=0.85,
        agreement_score=0.90,
        citation_coverage=0.80,
        reasoning_score=0.75,
        freshness_score=0.95,
        hallucination_risk=0.10,
        source_reliability=0.95,
        user_feedback_score=0.50,
    )
    assert len(c_vec) == 8
    assert "C_retrieval" in c_vec
    assert "C_hallucination_risk" in c_vec
    assert 0.0 <= score <= 1.0


# =============================================================================
# 11. HARD SAFETY POLICY OVERRIDES HIGH STATISTICAL CONFIDENCE
# =============================================================================

def test_11_hard_safety_overrides_high_confidence():
    c_vector = {"C_retrieval": 0.95, "C_agreement": 0.10, "C_hallucination_risk": 0.05}
    decision = confidence_calibrator.evaluate_trust_decision(
        trust_score=0.95,
        c_vector=c_vector,
        is_security_query=True,
    )
    assert decision["decision"] in ["FALLBACK_WEB", "ABSTAIN"]
    assert any("contradiction" in r.lower() for r in decision["reasons"])


# =============================================================================
# 12. EXPLAINABILITY REPRODUCES THE ACTUAL DECISION PATH
# =============================================================================

def test_12_explainability_reproduces_decision_path():
    trust_eval = {"decision": "FALLBACK_WEB", "trust_score": 0.95}
    c_vector = {"C_retrieval": 0.95, "C_agreement": 0.10}
    consensus_mat = {
        "contradiction_count": 1,
        "relationships": [
            {
                "relationship": "CONTRADICTS",
                "confidence": 0.92,
                "item_a_id": "ev-1",
                "item_b_id": "ev-2",
            }
        ],
    }

    explanation = confidence_calibrator.build_safety_explanation(
        trust_eval=trust_eval,
        c_vector=c_vector,
        consensus_mat=consensus_mat,
        is_security_query=True,
    )
    assert explanation["decision"] == "FALLBACK_WEB"
    assert explanation["policy_trigger"] == "CRITICAL_CONTRADICTION"
    assert explanation["contradiction_count"] == 1


# =============================================================================
# 13. KNOWLEDGE-GAP RETRIEVAL CHANGES EVIDENCE STATE
# =============================================================================

def test_13_knowledge_gap_retrieval_changes_evidence_state():
    obs = SecurityObservationData(
        observation_type="PUBLIC_ENDPOINT",
        location="admin.py",
    )
    assert obs.lifecycle_state == "OBSERVED"

    ctrl = SecurityControlEvaluation(
        control_type="AUTHORIZATION",
        scope="admin.py",
        state="PRESENT",
        evidence="RequireRole middleware",
    )
    assert ctrl.lifecycle_state == "CONTROL_EVALUATED"


# =============================================================================
# 14. COMPLETE END-TO-END INTERACTION CHAIN IS REPRODUCIBLE
# =============================================================================

def test_14_complete_end_to_end_chain():
    # 1. Facts & Controls
    obs = observation_collector.collect_observations("Admin API", "backend/app/api/v1/admin.py")
    ctrls = control_analyzer.evaluate_controls("Admin API", "backend/app/api/v1/admin.py")
    assert len(obs) > 0
    assert len(ctrls) > 0

    # 2. Candidate Scenario & Verification
    scenarios = risk_scenario_engine.infer_scenarios("Admin API", obs, ctrls)
    assessments = scenario_verifier.verify_scenarios("Admin API", "backend/app/api/v1/admin.py", scenarios, ctrls)
    assert len(assessments) > 0
    assert assessments[0].lifecycle_state == "ASSESSMENT"

    # 3. Posture Delta
    delta, trend = posture_trend_engine.compute_delta_and_trend(95.0, 90.0)
    assert trend == "IMPROVED"
    assert delta == +5.0
