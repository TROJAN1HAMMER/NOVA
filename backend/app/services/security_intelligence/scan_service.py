"""
NOVA Security Intelligence — Scan Service
Manages full lifecycle of security scan jobs: ingestion, asset discovery, static analysis,
controls evaluation, scenario inference, results persistence, and history.
"""

import asyncio
import datetime
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.security_intelligence import (
    SecurityIntelScan,
    SecurityIntelAsset,
    SecurityIntelObservation,
    SecurityIntelControl,
    SecurityIntelRiskScenario,
    SecurityIntelAssessment,
    SecurityIntelPostureSnapshot,
)
from app.models.user import User
from app.services.security_intelligence.repository_ingestion import repository_ingestion_service
from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator

logger = structlog.get_logger(__name__)


class SecurityScanService:
    """Manages scan execution, background progression, and database persistence."""

    def __init__(self):
        self._results_cache: Dict[str, Dict[str, Any]] = {}

    async def create_scan_job(
        self,
        db: AsyncSession,
        project_name: str,
        source_type: str,  # GITHUB, ZIP, LOCAL
        source_identifier: str,
        owner_id: Optional[uuid.UUID] = None,
        workspace_path: Optional[str] = None,
    ) -> SecurityIntelScan:
        scan = SecurityIntelScan(
            id=uuid.uuid4(),
            project_name=project_name,
            source_type=source_type,
            source_identifier=source_identifier,
            status="QUEUED",
            progress=0,
            stage="QUEUED",
            workspace_path=workspace_path,
            owner_id=owner_id,
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(scan)
        await db.commit()
        await db.refresh(scan)
        logger.info("security_scan.job_created", scan_id=str(scan.id), project=project_name, source_type=source_type)
        return scan

    async def execute_scan(
        self,
        scan_id: uuid.UUID,
        zip_bytes: Optional[bytes] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes the scan through ingestion and security intelligence pipeline."""
        scan_id_str = str(scan_id)
        logger.info("security_scan.executing", scan_id=scan_id_str)

        async with AsyncSessionLocal() as db:
            scan = await db.get(SecurityIntelScan, scan_id)
            if not scan:
                logger.error("security_scan.not_found", scan_id=scan_id_str)
                return {"status": "FAILED", "error": "Scan not found"}

            try:
                # Stage 1: Ingestion
                scan.status = "INGESTING"
                scan.stage = "Ingesting repository source"
                scan.progress = 10
                await db.commit()

                target_dir: Path
                if scan.source_type == "GITHUB":
                    target_dir = await repository_ingestion_service.ingest_github_repository(
                        scan.source_identifier, scan_id_str, branch=branch
                    )
                elif scan.source_type == "ZIP":
                    if not zip_bytes:
                        raise ValueError("ZIP archive payload missing for ZIP scan.")
                    target_dir = repository_ingestion_service.validate_and_extract_zip(zip_bytes, scan_id_str)
                else:  # LOCAL
                    target_dir = Path(scan.workspace_path or scan.source_identifier).resolve()

                scan.workspace_path = str(target_dir)
                scan.status = "DISCOVERING_ASSETS"
                scan.stage = "Discovering software assets and APIs"
                scan.progress = 25
                await db.commit()

                # Run Full Analysis Pipeline
                def progress_cb(pct: int, stg: str):
                    pass  # internal progression

                results = security_intelligence_orchestrator.run_full_analysis(
                    target_path=str(target_dir),
                    project_name=scan.project_name,
                    scan_id=scan_id_str,
                )

                posture = results["posture"]
                snapshot = results["snapshot"]

                # Update Scan Record
                scan.status = "COMPLETED"
                scan.stage = "Analysis complete"
                scan.progress = 100
                scan.posture_score = posture["posture_score"]
                scan.posture_rating = posture["posture_rating"]
                scan.delta_score = posture.get("delta_score")
                scan.trend_direction = posture.get("security_trend", "UNCHANGED")
                scan.completed_at = datetime.datetime.now(datetime.timezone.utc)
                scan.result_summary = {
                    "total_assets": len(results["assets"]),
                    "total_findings": len(results["assessments"]),
                    "severity_breakdown": posture.get("severity_breakdown", {}),
                    "control_coverage": posture.get("control_coverage", {}),
                    "observations_count": results["observations_count"],
                    "controls_count": results["controls_count"],
                    "risk_scenarios_count": results["risk_scenarios_count"],
                }

                # Persist DB Snapshot
                posture_snap = SecurityIntelPostureSnapshot(
                    id=uuid.uuid4(),
                    analysis_run_id=scan_id_str,
                    target_scope=scan.project_name,
                    posture_score=posture["posture_score"],
                    posture_rating=posture["posture_rating"],
                    control_coverage_pct=posture.get("control_coverage", {}).get("coverage_percentage", 0.0),
                    total_assets_count=len(results["assets"]),
                    unresolved_risks_count=posture.get("unresolved_risks_count", len(results["assessments"])),
                    critical_risks_count=posture.get("severity_breakdown", {}).get("critical", 0),
                    high_risks_count=posture.get("severity_breakdown", {}).get("high", 0),
                    medium_risks_count=posture.get("severity_breakdown", {}).get("medium", 0),
                    low_risks_count=posture.get("severity_breakdown", {}).get("low", 0),
                    delta_score=posture.get("delta_score"),
                    trend_direction=posture.get("security_trend", "UNCHANGED"),
                    risk_evolution_summary=snapshot.get("risk_evolution_summary"),
                )
                db.add(posture_snap)

                await db.commit()
                await db.refresh(scan)

                self._results_cache[scan_id_str] = results
                logger.info("security_scan.completed_successfully", scan_id=scan_id_str, score=scan.posture_score)
                return results

            except Exception as exc:
                logger.exception("security_scan.execution_failed", scan_id=scan_id_str, error=str(exc))
                scan.status = "FAILED"
                scan.stage = "Scan execution failed"
                scan.error_message = str(exc)
                scan.completed_at = datetime.datetime.now(datetime.timezone.utc)
                await db.commit()
                return {"status": "FAILED", "error": str(exc)}

    async def get_scan(self, db: AsyncSession, scan_id: uuid.UUID) -> Optional[SecurityIntelScan]:
        return await db.get(SecurityIntelScan, scan_id)

    async def get_scan_results(self, db: AsyncSession, scan_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        scan_id_str = str(scan_id)
        if scan_id_str in self._results_cache:
            return self._results_cache[scan_id_str]

        scan = await db.get(SecurityIntelScan, scan_id)
        if not scan:
            return None

        if scan.status == "COMPLETED" and scan.workspace_path:
            # Re-generate results from workspace
            results = security_intelligence_orchestrator.run_full_analysis(
                target_path=scan.workspace_path,
                project_name=scan.project_name,
                scan_id=scan_id_str,
                force_refresh=True,
            )
            if results and "posture" in results:
                scan.posture_score = results["posture"]["posture_score"]
                scan.posture_rating = results["posture"]["posture_rating"]
                await db.commit()
            self._results_cache[scan_id_str] = results
            return results


        return None

    async def list_scans(
        self,
        db: AsyncSession,
        user: Optional[User] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SecurityIntelScan]:
        query = select(SecurityIntelScan).order_by(desc(SecurityIntelScan.created_at)).limit(limit).offset(offset)
        result = await db.execute(query)
        return list(result.scalars().all())


security_scan_service = SecurityScanService()
