"""
NOVA — ScanResult Repository
Handles asynchronous database access for computed scan outcomes.
"""

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan_result import ScanResult


class ScanResultRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_scan_job(self, scan_job_id: uuid.UUID) -> Optional[ScanResult]:
        """Fetch ScanResult associated with a given ScanJob UUID."""
        result = await self.db.execute(
            select(ScanResult).where(ScanResult.scan_job_id == scan_job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, result_id: uuid.UUID) -> Optional[ScanResult]:
        """Fetch ScanResult by primary key ID."""
        return await self.db.get(ScanResult, result_id)

    async def create_or_update(
        self,
        *,
        scan_job_id: uuid.UUID,
        total_findings: int = 0,
        brs_score: Optional[float] = None,
        brs_risk_level: Optional[str] = None,
        attack_surface_exposure_score: Optional[float] = None,
        attack_surface_exposure_level: Optional[str] = None,
        summary: Optional[dict[str, Any]] = None,
        compliance_summary: Optional[dict[str, Any]] = None,
    ) -> ScanResult:
        """Create or update a ScanResult for a scan job."""
        existing = await self.get_by_scan_job(scan_job_id)
        if existing is None:
            scan_result = ScanResult(
                scan_job_id=scan_job_id,
                total_findings=total_findings,
                brs_score=brs_score,
                brs_risk_level=brs_risk_level,
                attack_surface_exposure_score=attack_surface_exposure_score,
                attack_surface_exposure_level=attack_surface_exposure_level,
                summary=summary,
                compliance_summary=compliance_summary,
            )
            self.db.add(scan_result)
            await self.db.flush()
            return scan_result

        existing.total_findings = total_findings
        existing.brs_score = brs_score
        existing.brs_risk_level = brs_risk_level
        existing.attack_surface_exposure_score = attack_surface_exposure_score
        existing.attack_surface_exposure_level = attack_surface_exposure_level
        existing.summary = summary
        existing.compliance_summary = compliance_summary
        await self.db.flush()
        return existing
