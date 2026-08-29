"""
NOVA API — Canonical Demonstration Router
Mounted at `/api/v1/admin/demo`
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any

from app.auth.permissions import Permission, require_permission
from app.demo.orchestrator import demo_orchestrator

router = APIRouter(prefix="/admin/demo", tags=["Canonical Demo"])


@router.post("/reset")
def reset_demo_environment(user: Any = Depends(require_permission(Permission.ADMIN_WRITE))) -> Dict[str, Any]:
    """Resets the demo environment to clean baseline vulnerable state."""
    return demo_orchestrator.reset_demo_environment()


@router.post("/vulnerable")
def run_vulnerable_analysis(user: Any = Depends(require_permission(Permission.KNOWLEDGE_READ))) -> Dict[str, Any]:
    """Executes Security Intelligence analysis on vulnerable demo repository fixture."""
    return demo_orchestrator.run_vulnerable_analysis()


@router.post("/contradiction")
def trigger_contradiction(user: Any = Depends(require_permission(Permission.KNOWLEDGE_READ))) -> Dict[str, Any]:
    """Triggers contradictory evidence pair and Safety Gate response."""
    return demo_orchestrator.get_contradiction_evidence_pair()


@router.post("/remediate")
def apply_remediation(user: Any = Depends(require_permission(Permission.KNOWLEDGE_WRITE))) -> Dict[str, Any]:
    """Applies patched authorization snippet and verifies remediation via RemediationVerifier."""
    return demo_orchestrator.apply_remediation()


@router.get("/state")
def get_demo_state(user: Any = Depends(require_permission(Permission.KNOWLEDGE_READ))) -> Dict[str, Any]:
    """Returns current demo environment state summary."""
    return demo_orchestrator.get_demo_state_summary()
