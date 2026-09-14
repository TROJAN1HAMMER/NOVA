"""
NOVA Architecture Intelligence — REST API Router
Exposes component relationships, coupling/cohesion metrics, circular dependencies,
hotspot classification, blast radius, architecture drift, and unified traceability.
Strictly isolates tenants/scans and prevents path traversal.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.architecture import (
    ArchitectureAnalyzeRequest,
    ArchitectureOverviewResponse,
    BlastRadiusResponse,
    ArchitectureDriftResponse,
    RemediationImpactRequest,
    RemediationImpactResponse,
)
from app.services.architecture_intelligence.architecture_orchestrator import (
    architecture_orchestrator,
)

router = APIRouter(prefix="/architecture", tags=["Architecture Intelligence"])


def _validate_safe_path(target_path: str) -> str:
    cleaned = target_path.strip()
    if ".." in cleaned or cleaned.startswith(("/etc", "/var", "/proc", "/sys")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target path: Directory traversal or restricted paths are prohibited.",
        )
    return cleaned


import structlog
logger = structlog.get_logger(__name__)


async def _resolve_scan_analysis(
    scan_id: str,
    target_path: str = ".",
    force_refresh: bool = False,
    db: Optional[AsyncSession] = None,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Resolves architecture intelligence analysis strictly scoped to scan_id."""
    safe_path = _validate_safe_path(target_path)

    # 1. Check if scan analysis is already cached under its scan_id key
    cache_key = architecture_orchestrator.get_cache_key(scan_id)
    if not force_refresh and cache_key in architecture_orchestrator._scan_cache:
        return architecture_orchestrator._scan_cache[cache_key]

    # 2. Handle 'latest' alias
    if scan_id == "latest":
        return architecture_orchestrator.get_latest_analysis(target_path=safe_path)

    # 3. Query scan metadata from database if db session is provided
    if db is not None:
        try:
            import uuid
            from sqlalchemy import select
            from app.models.security_intelligence import SecurityIntelScan

            try:
                scan_uuid = uuid.UUID(scan_id)
                query = select(SecurityIntelScan).where(SecurityIntelScan.id == scan_uuid)
                res = await db.execute(query)
                scan = res.scalar_one_or_none()
                if scan:
                    from pathlib import Path
                    workspace = scan.workspace_path if scan.workspace_path and Path(scan.workspace_path).exists() else safe_path
                    return architecture_orchestrator.get_analysis_for_scan(
                        scan_id=scan_id,
                        target_path=workspace,
                        project_name=scan.project_name,
                        force_refresh=force_refresh,
                    )
            except ValueError:
                pass
        except Exception:
            pass

    # 4. Fallback to scan-scoped analysis on safe_path (handles test fixtures and local repos)
    return architecture_orchestrator.get_analysis_for_scan(
        scan_id=scan_id,
        target_path=safe_path,
        force_refresh=force_refresh,
    )


@router.get("/scans", response_model=List[Dict[str, Any]], summary="List Available Repository Scans for Architecture")
async def list_architecture_scans(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns all completed repository scans available for architectural exploration."""
    try:
        from sqlalchemy import select, desc
        from app.models.security_intelligence import SecurityIntelScan

        query = (
            select(SecurityIntelScan)
            .where(SecurityIntelScan.status == "COMPLETED")
            .order_by(desc(SecurityIntelScan.completed_at), desc(SecurityIntelScan.created_at))
            .limit(50)
        )
        res = await db.execute(query)
        scans = res.scalars().all()
        return [
            {
                "scan_id": str(s.id),
                "project_name": s.project_name,
                "source_type": s.source_type,
                "source_identifier": s.source_identifier,
                "status": s.status,
                "posture_score": s.posture_score,
                "posture_rating": s.posture_rating,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "workspace_path": s.workspace_path,
            }
            for s in scans
        ]
    except Exception:
        return []


@router.post("/analyze", response_model=Dict[str, Any], summary="Run Architecture Intelligence Analysis")
async def analyze_architecture(
    payload: ArchitectureAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Executes static AST component discovery, dependency graph extraction, and metrics calculation."""
    from pathlib import Path
    import uuid
    import datetime
    from app.models.security_intelligence import SecurityIntelScan

    safe_path = _validate_safe_path(payload.target_path)
    target_scan_id = payload.scan_id

    if target_scan_id:
        try:
            scan_uuid = uuid.UUID(target_scan_id)
            scan = await db.get(SecurityIntelScan, scan_uuid)
            if not scan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scan '{target_scan_id}' not found.",
                )

            workspace = scan.workspace_path or scan.source_identifier
            if not workspace or not Path(workspace).exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"AST scan is unavailable for this source ({scan.source_type}): workspace directory '{workspace}' is not accessible on the server.",
                )

            res = architecture_orchestrator.run_architecture_analysis(
                target_path=workspace,
                project_name=scan.project_name,
                scan_id=target_scan_id,
                force_refresh=True,
            )
            res["scan_id"] = target_scan_id
            cache_key = architecture_orchestrator.get_cache_key(target_scan_id)
            architecture_orchestrator._scan_cache[cache_key] = res
            return res
        except HTTPException:
            raise
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scan ID format: '{target_scan_id}'.",
            )

    path_obj = Path(safe_path)
    if not path_obj.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AST scan is unavailable for this source: target directory '{safe_path}' does not exist.",
        )

    new_scan_id = str(uuid.uuid4())
    proj_name = payload.project_name or (path_obj.name if path_obj.name and path_obj.name != "." else "NOVA Core")
    res = architecture_orchestrator.run_architecture_analysis(
        target_path=safe_path,
        project_name=proj_name,
        scan_id=new_scan_id,
        force_refresh=True,
    )
    res["scan_id"] = new_scan_id
    cache_key = architecture_orchestrator.get_cache_key(new_scan_id)
    architecture_orchestrator._scan_cache[cache_key] = res

    # Register into SecurityIntelScan so it appears in scan selector dropdown
    try:
        new_scan = SecurityIntelScan(
            id=uuid.UUID(new_scan_id),
            project_name=proj_name,
            source_type="LOCAL",
            source_identifier=str(path_obj.resolve()),
            status="COMPLETED",
            progress=100,
            stage="COMPLETED",
            workspace_path=str(path_obj.resolve()),
            owner_id=current_user.id if current_user else None,
            started_at=datetime.datetime.now(datetime.timezone.utc),
            completed_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(new_scan)
        await db.commit()
    except Exception as exc:
        logger.warning("failed_to_register_scan_record", error=str(exc))

    return res


@router.get("/latest", response_model=Dict[str, Any], summary="Get Latest Architecture Overview")
def get_latest_architecture(
    target_path: str = Query(default=".", description="Target workspace path"),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns the latest architecture snapshot, summary KPIs, hotspots, and graph structures."""
    safe_path = _validate_safe_path(target_path)
    return architecture_orchestrator.get_latest_analysis(target_path=safe_path)


@router.get("/{scan_id}", response_model=Dict[str, Any], summary="Get Architecture Snapshot by Scan ID")
async def get_architecture_by_scan_id(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    force_refresh: bool = Query(default=False, description="Force refresh scan architecture analysis"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns the full architecture intelligence snapshot strictly scoped to the specified scan ID."""
    return await _resolve_scan_analysis(
        scan_id=scan_id,
        target_path=target_path,
        force_refresh=force_refresh,
        db=db,
        current_user=current_user,
    )


@router.get("/{scan_id}/components", response_model=Dict[str, Any], summary="List Architecture Components")
async def get_components(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns discovered software components with coupling and cohesion metrics for the selected scan."""
    analysis = await _resolve_scan_analysis(scan_id=scan_id, target_path=target_path, db=db, current_user=current_user)
    return {
        "scan_id": scan_id,
        "count": len(analysis["components"]),
        "components": analysis["components"],
    }


@router.get("/{scan_id}/dependencies", response_model=Dict[str, Any], summary="Get Architecture Graph (Nodes & Edges)")
async def get_dependencies(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns graph nodes and typed directed edges strictly scoped to the selected scan."""
    analysis = await _resolve_scan_analysis(scan_id=scan_id, target_path=target_path, db=db, current_user=current_user)
    return {
        "scan_id": scan_id,
        "nodes": analysis["components"],
        "edges": analysis["dependencies"],
        "cycles": analysis.get("cycles_detected", []),
    }


@router.get("/{scan_id}/metrics", response_model=Dict[str, Any], summary="Get Coupling & Cohesion Metrics")
async def get_metrics(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns detailed coupling, instability, LCOM cohesion, and cycle metrics for the selected scan."""
    analysis = await _resolve_scan_analysis(scan_id=scan_id, target_path=target_path, db=db, current_user=current_user)
    return {
        "scan_id": scan_id,
        "summary": analysis["summary"],
        "metrics": analysis["metrics"],
    }


@router.get("/{scan_id}/hotspots", response_model=Dict[str, Any], summary="Get Architecture Hotspots")
async def get_hotspots(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns ranked architecture hotspots with evidence explanations for the selected scan."""
    analysis = await _resolve_scan_analysis(scan_id=scan_id, target_path=target_path, db=db, current_user=current_user)
    return {
        "scan_id": scan_id,
        "count": len(analysis["hotspots"]),
        "hotspots": analysis["hotspots"],
    }


@router.get("/{scan_id}/impact/{component_id:path}", response_model=Dict[str, Any], summary="Compute Blast Radius")
async def get_component_blast_radius(
    scan_id: str,
    component_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Calculates downstream blast radius for a component within the selected scan scope."""
    safe_path = _validate_safe_path(target_path)
    # Ensure scan is loaded
    await _resolve_scan_analysis(scan_id=scan_id, target_path=safe_path, db=db, current_user=current_user)
    report = architecture_orchestrator.compute_blast_radius(component_id=component_id, target_path=safe_path, scan_id=scan_id)
    return {
        "scan_id": scan_id,
        "target_component_id": report.target_component_id,
        "target_component_name": report.target_component_name,
        "direct_dependents_count": report.direct_dependents_count,
        "direct_dependents": report.direct_dependents,
        "transitive_dependents_count": report.transitive_dependents_count,
        "transitive_dependents": report.transitive_dependents,
        "max_impact_depth": report.max_impact_depth,
        "affected_endpoints": report.affected_endpoints,
        "affected_services": report.affected_services,
        "affected_findings": report.affected_findings,
        "affected_controls": report.affected_controls,
        "affected_scenarios": report.affected_scenarios,
        "affected_assets": report.affected_assets,
        "risk_level": report.risk_level,
    }


@router.get("/{scan_id}/drift", response_model=Dict[str, Any], summary="Inspect Architecture Drift")
async def get_architecture_drift(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Compares current architecture snapshot with previous baseline for the selected scan."""
    safe_path = _validate_safe_path(target_path)
    await _resolve_scan_analysis(scan_id=scan_id, target_path=safe_path, db=db, current_user=current_user)
    drift = architecture_orchestrator.get_architecture_drift(target_path=safe_path, scan_id=scan_id)
    return {
        "scan_id": scan_id,
        "baseline_available": drift.baseline_available,
        "message": drift.message,
        "status": drift.status,
        "previous_snapshot_id": drift.previous_snapshot_id,
        "current_snapshot_id": drift.current_snapshot_id,
        "added_dependencies": drift.added_dependencies,
        "removed_dependencies": drift.removed_dependencies,
        "new_circular_cycles": drift.new_circular_cycles,
        "resolved_circular_cycles": drift.resolved_circular_cycles,
        "increased_coupling_components": drift.increased_coupling_components,
        "new_god_candidates": drift.new_god_candidates,
        "boundary_violations": drift.boundary_violations,
        "summary": drift.summary,
    }


@router.get("/{scan_id}/traceability", response_model=Dict[str, Any], summary="Unified Traceability Explorer")
async def get_traceability(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Returns provenance-backed requirement -> chunk -> code -> control -> finding -> risk chains for the scan."""
    analysis = await _resolve_scan_analysis(scan_id=scan_id, target_path=target_path, db=db, current_user=current_user)
    return {
        "scan_id": scan_id,
        "count": len(analysis["traceability"]),
        "traceability": analysis["traceability"],
    }


@router.post("/{scan_id}/remediation-impact", response_model=Dict[str, Any], summary="Estimate Remediation Impact")
async def estimate_remediation_impact(
    scan_id: str,
    payload: RemediationImpactRequest,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Estimates the ripple benefit and posture delta of a proposed fix (labeled strictly as ESTIMATE)."""
    safe_path = _validate_safe_path(target_path)
    await _resolve_scan_analysis(scan_id=scan_id, target_path=safe_path, db=db, current_user=current_user)
    rep = architecture_orchestrator.estimate_remediation_impact(
        component_id=payload.component_id,
        proposed_remediation=payload.proposed_remediation,
        target_path=safe_path,
        scan_id=scan_id,
    )
    return {
        "scan_id": scan_id,
        "target_component_id": rep.target_component_id,
        "target_component_name": rep.target_component_name,
        "proposed_remediation": rep.proposed_remediation,
        "metric_label": rep.metric_label,
        "estimated_posture_delta": rep.estimated_posture_delta,
        "affected_components_count": rep.affected_components_count,
        "affected_components": rep.affected_components,
        "strengthened_controls": rep.strengthened_controls,
        "mitigated_risk_scenarios": rep.mitigated_risk_scenarios,
        "remaining_hotspot_status": rep.remaining_hotspot_status,
        "disclaimer": rep.disclaimer,
        "direct_dependents_count": rep.direct_dependents_count,
        "max_impact_depth": rep.max_impact_depth,
    }


@router.get("/{scan_id}/change-impact", response_model=Dict[str, Any], summary="Analyze Change Impact from Git")
async def get_change_impact(
    scan_id: str,
    target_path: str = Query(default=".", description="Target workspace path"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_active_user),
):
    """Analyzes impact of modified files from git diff across the architecture graph for this scan."""
    safe_path = _validate_safe_path(target_path)
    await _resolve_scan_analysis(scan_id=scan_id, target_path=safe_path, db=db, current_user=current_user)
    ci = architecture_orchestrator.analyze_change_impact(target_path=safe_path, scan_id=scan_id)
    return {
        "scan_id": scan_id,
        "git_available": ci.git_available,
        "commit_ref": ci.commit_ref,
        "changed_files": ci.changed_files,
        "changed_components": ci.changed_components,
        "impacted_components_count": ci.impacted_components_count,
        "impacted_components": ci.impacted_components,
        "affected_endpoints": ci.affected_endpoints,
        "affected_services": ci.affected_services,
        "affected_findings": ci.affected_findings,
        "affected_controls": ci.affected_controls,
        "affected_scenarios": ci.affected_scenarios,
        "message": ci.message,
    }
