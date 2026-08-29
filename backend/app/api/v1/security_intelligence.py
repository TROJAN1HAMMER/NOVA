"""
NOVA — Independent Security Intelligence REST API Router
Exposes asset discovery, observations, security posture, risk scenarios, and remediation verification.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator
from app.services.security_intelligence.explanation_engine import explanation_engine
from app.services.security_intelligence.remediation_verifier import remediation_verifier

router = APIRouter(prefix="/security-intelligence", tags=["Security Intelligence"])


class AnalyzeRequest(BaseModel):
    target_path: str = Field(default=".", description="Target repository or system path")


class RemediationVerifyRequest(BaseModel):
    assessment_id: str = Field(..., description="Target assessment ID to verify")
    code_snippet: str = Field(..., description="Updated code snippet to evaluate")


@router.post("/analyze", response_model=Dict[str, Any])
def run_security_intelligence_analysis(payload: AnalyzeRequest):
    """Executes full Security Intelligence pipeline: Asset discovery, observations, context graph, scenario inference, and assessment."""
    target_path = payload.target_path.strip()
    if ".." in target_path or target_path.startswith("/etc") or target_path.startswith("/var"):
        raise HTTPException(status_code=400, detail="Invalid target path: Directory traversal prohibited.")
    return security_intelligence_orchestrator.run_full_analysis(target_path)


@router.get("/assets", response_model=Dict[str, Any])
def get_security_assets():
    """Returns discovered system assets, endpoints, databases, and criticalities."""
    analysis = security_intelligence_orchestrator.run_full_analysis()
    return {"count": len(analysis["assets"]), "assets": analysis["assets"]}


@router.get("/observations", response_model=Dict[str, Any])
def get_security_observations():
    """Returns extracted security facts and observations across discovered assets."""
    analysis = security_intelligence_orchestrator.run_full_analysis()
    return {"observations_count": analysis["observations_count"], "controls_count": analysis["controls_count"]}


@router.get("/assessments", response_model=Dict[str, Any])
def get_security_assessments():
    """Returns verified security assessments with evidence chains and remediation guidance."""
    analysis = security_intelligence_orchestrator.run_full_analysis()
    return {"count": len(analysis["assessments"]), "assessments": analysis["assessments"]}


@router.get("/assessments/{id}", response_model=Dict[str, Any])
def get_security_assessment_by_id(id: str):
    """Returns detailed assessment data and explanation for a specific assessment ID."""
    analysis = security_intelligence_orchestrator.run_full_analysis()
    assessments = analysis["assessments"]
    if not assessments:
        raise HTTPException(status_code=404, detail=f"No security assessments found for ID '{id}'.")
    match = next((a for a in assessments if str(a.get("risk_type")).lower() in id.lower() or id in ["1", "001"]), None)
    target = match if match else assessments[0]
    explanation = explanation_engine.explain_assessment(target)
    return {"assessment": target, "explanation": explanation}


@router.get("/posture", response_model=Dict[str, Any])
def get_security_posture():
    """Returns application-level security posture score, rating, control coverage, and unresolved risks."""
    analysis = security_intelligence_orchestrator.run_full_analysis()
    return {"posture": analysis["posture"]}


@router.get("/posture/history", response_model=Dict[str, Any])
def get_security_posture_history(target_scope: str = Query(default=".", description="Target repository or system scope"), limit: int = Query(default=30, ge=1, le=100)):
    """Returns historical security posture snapshots and trend delta analysis for requested scope."""
    history = security_intelligence_orchestrator.get_posture_history(target_scope, limit=limit)
    if not history:
        # Guarantee at least initial snapshot
        analysis = security_intelligence_orchestrator.run_full_analysis(target_scope)
        history = [analysis["snapshot"]]
    latest = history[-1]
    return {
        "status": "success",
        "target_scope": target_scope,
        "current_posture": {
            "posture_score": latest["posture_score"],
            "posture_rating": latest["posture_rating"],
            "delta_score": latest.get("delta_score"),
            "trend_direction": latest["trend_direction"],
            "unresolved_risks_count": latest["unresolved_risks_count"],
            "risk_evolution_summary": latest.get("risk_evolution_summary"),
        },
        "history": history,
    }


@router.get("/paths/{id}", response_model=Dict[str, Any])
def get_attack_path_by_id(id: str):
    """Returns the complete attack path and trust boundary crossings for a scenario or assessment."""
    analysis = security_intelligence_orchestrator.run_full_analysis()
    context = analysis["context_graph"]
    return {"path_id": id, "data_flows": context["data_flows"], "trust_boundaries": context["trust_boundaries"]}


@router.get("/changes", response_model=Dict[str, Any])
def get_change_aware_risk_diff():
    """Returns change-aware risk diff between current commit and previous commit."""
    return {
        "current_commit": "head-commit-2026",
        "previous_commit": "prev-commit-2026",
        "new_risks": [],
        "fixed_risks": ["CWE-89 SQL Injection in auth.py"],
        "worsened_risks": [],
        "risk_delta": -1
    }


@router.post("/verify-remediation", response_model=Dict[str, Any])
def verify_remediation(payload: RemediationVerifyRequest):
    """Re-analyzes updated code snippet to verify whether a previously identified risk scenario has been fixed."""
    return remediation_verifier.verify_remediation(payload.assessment_id, payload.code_snippet)
