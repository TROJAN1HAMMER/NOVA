"""
NOVA — Independent Security Intelligence Test Suite
Tests asset discovery, security observations, context graph, control analysis,
risk scenario inference, verification, remediation verification, explanation, evidence provider, and APIs.
Completely isolated from legacy scanner Finding tests.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.security_intelligence.asset_discovery_service import asset_discovery_service
from app.services.security_intelligence.observation_collector import observation_collector
from app.services.security_intelligence.security_context_graph import security_context_graph
from app.services.security_intelligence.control_analyzer import control_analyzer
from app.services.security_intelligence.risk_scenario_engine import risk_scenario_engine
from app.services.security_intelligence.scenario_verifier import scenario_verifier
from app.services.security_intelligence.remediation_verifier import remediation_verifier
from app.services.security_intelligence.explanation_engine import explanation_engine
from app.services.security_intelligence.evidence_provider import security_evidence_provider
from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator

client = TestClient(app)


def test_asset_discovery():
    assets = asset_discovery_service.discover_assets(".")
    assert len(assets) >= 4
    asset_types = {a.asset_type for a in assets}
    assert "APPLICATION" in asset_types
    assert "API" in asset_types
    assert "DATABASE" in asset_types


@pytest.fixture
def sample_admin_path(tmp_path):
    admin_file = tmp_path / "admin.py"
    admin_file.write_text(
        "import os\n"
        "AWS_KEY = 'AKIA1234567890ABCDEF'\n"
        "from fastapi import APIRouter, Depends\n"
        "router = APIRouter()\n"
        "@router.get('/public')\n"
        "def public_endpoint(): return {'status': 'ok'}\n"
        "@router.post('/role', dependencies=[Depends(RequireRole('admin'))])\n"
        "def update_role(): return {'updated': True}\n"
        "@router.post('/unprotected_role')\n"
        "def unprotect(): return {'leak': True}\n"
    )
    return str(admin_file)



def test_observation_collector(sample_admin_path):
    obs = observation_collector.collect_observations("NOVA Admin Surface", sample_admin_path)
    assert len(obs) >= 3
    obs_types = {o.observation_type for o in obs}
    assert "PUBLIC_ENDPOINT" in obs_types
    assert "AUTHORIZATION_BOUNDARY" in obs_types
    assert "PRIVILEGED_OPERATION" in obs_types


def test_security_context_graph(sample_admin_path):
    obs = observation_collector.collect_observations("NOVA Admin Surface", sample_admin_path)
    ctx = security_context_graph.build_context_graph(obs)
    assert "trust_boundaries" in ctx
    assert "data_flows" in ctx
    assert len(ctx["trust_boundaries"]) >= 3


def test_control_analyzer(sample_admin_path):
    controls = control_analyzer.evaluate_controls("NOVA Admin Surface", sample_admin_path)
    assert len(controls) >= 2
    control_types = {c.control_type: c.state for c in controls}
    assert "AUTHORIZATION" in control_types
    assert control_types["AUTHORIZATION"] == "PRESENT"


def test_risk_scenario_engine(sample_admin_path):
    obs = observation_collector.collect_observations("NOVA Admin Surface", sample_admin_path)
    controls = control_analyzer.evaluate_controls("NOVA Admin Surface", sample_admin_path)
    scenarios = risk_scenario_engine.infer_scenarios("NOVA Admin Surface", obs, controls)
    assert len(scenarios) >= 1
    assert scenarios[0].scenario_type in ["PRIVILEGE_ESCALATION_RISK", "SECRET_EXPOSURE_RISK"]


def test_scenario_verifier(sample_admin_path):
    obs = observation_collector.collect_observations("NOVA Admin Surface", sample_admin_path)
    controls = control_analyzer.evaluate_controls("NOVA Admin Surface", sample_admin_path)
    scenarios = risk_scenario_engine.infer_scenarios("NOVA Admin Surface", obs, controls)
    assessments = scenario_verifier.verify_scenarios("NOVA Admin Surface", sample_admin_path, scenarios, controls)
    assert len(assessments) >= 1
    assert assessments[0].confidence >= 0.85
    assert assessments[0].status == "OPEN"


def test_remediation_verifier():
    snippet_vulnerable = "def update_user_role(role: str): user.role = role"
    result_vuln = remediation_verifier.verify_remediation("test-001", snippet_vulnerable)
    assert result_vuln["fixed"] is False

    snippet_fixed = "@router.post('/role', dependencies=[Depends(RequireRole('admin'))])\ndef update_user_role(role: str): user.role = role"
    result_fixed = remediation_verifier.verify_remediation("test-001", snippet_fixed)
    assert result_fixed["fixed"] is True
    assert result_fixed["status"] == "VERIFIED_FIXED"


def test_explanation_engine():
    assessment = {
        "id": "assess-001",
        "asset_name": "NOVA Admin API",
        "risk_type": "PRIVILEGE_ESCALATION_RISK",
        "affected_scope": "backend/app/api/v1/admin.py",
        "attack_path": ["INTERNET -> PUBLIC_API -> DATABASE"],
        "reasoning": "Endpoint exposes user role update operation without verified authorization middleware.",
        "remediation": "Enforce RequireRole('admin') middleware.",
        "controls_evaluated": [{"control": "AUTHORIZATION", "state": "ABSENT"}]
    }
    exp = explanation_engine.explain_assessment(assessment)
    assert exp["title"] == "Security Assessment: PRIVILEGE_ESCALATION_RISK"
    assert "why_identified" in exp
    assert "remediation_guidance" in exp


def test_security_evidence_provider():
    evidence = security_evidence_provider.get_security_evidence("privilege escalation admin authorization", top_k=5)
    assert len(evidence) >= 1
    assert evidence[0]["source_type"] == "security_finding"
    assert "PRIVILEGE_ESCALATION_RISK" in evidence[0]["content"] or "admin" in evidence[0]["content"]


def test_intelligence_orchestrator(tmp_path):
    (tmp_path / "app.py").write_text("import subprocess\ndef run(c):\n    subprocess.run(c, shell=True)\n")
    (tmp_path / "db.py").write_text("def query(db, id):\n    return db.execute(f'SELECT * FROM t WHERE id={id}')\n")
    (tmp_path / "routes.py").write_text("from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/data')\ndef get_data(): return {}\n")
    result = security_intelligence_orchestrator.run_full_analysis(str(tmp_path), force_refresh=True)
    assert result["status"] == "COMPLETED"
    assert len(result["assets"]) >= 1
    assert result["posture"]["posture_score"] > 0
    assert len(result["assessments"]) >= 2



def test_security_intelligence_rest_apis():
    prev = security_intelligence_orchestrator._last_results.get(".")
    try:
        security_intelligence_orchestrator._last_results["."] = {
            "status": "COMPLETED",
            "posture": {"posture_score": 85.0, "posture_rating": "STRONG", "control_coverage": 100.0, "unresolved_risks_count": 0},
            "assets": [{"asset_name": "API", "asset_type": "API", "location": ".", "trust_boundary": "TB-2"}],
            "assessments": [],
            "context_graph": {"discovered_nodes": [], "discovered_edges": []},
        }
        res_posture = client.get("/api/v1/security-intelligence/posture")
        assert res_posture.status_code == 200
        assert "posture" in res_posture.json()

        res_assets = client.get("/api/v1/security-intelligence/assets")
        assert res_assets.status_code == 200
        assert "assets" in res_assets.json()

        res_assessments = client.get("/api/v1/security-intelligence/assessments")
        assert res_assessments.status_code == 200
        assert "assessments" in res_assessments.json()

        res_verify = client.post("/api/v1/security-intelligence/verify-remediation", json={
            "assessment_id": "assess-001",
            "code_snippet": "dependencies=[Depends(RequireRole('admin'))]"
        })
        assert res_verify.status_code == 200
        assert res_verify.json()["fixed"] is True
    finally:
        if prev is not None:
            security_intelligence_orchestrator._last_results["."] = prev
        else:
            security_intelligence_orchestrator._last_results.pop(".", None)


def test_path_traversal_prevention():
    res = client.post("/api/v1/security-intelligence/analyze", json={"target_path": "../../../etc/passwd"})
    assert res.status_code == 400
    assert "Directory traversal prohibited" in res.json()["detail"]
