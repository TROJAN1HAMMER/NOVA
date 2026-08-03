"""rename zero-day fields to attack surface exposure

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-07-19

"Zero-Day Risk" implied a predictive claim (probability of zero-day
exploitation) this heuristic model was never actually able to support —
it measures attack-surface/dependency-hygiene exposure factors (dependency
count, CVE density, staleness, risky packages, config risk, code
vulnerability density), not a forecast of undiscovered vulnerabilities.
Renamed to "Attack Surface Exposure" throughout the stack; this migration
carries the two `scan_results` columns along, preserving existing data —
a plain column rename, no type/nullability change.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("scan_results", "zero_day_risk_score", new_column_name="attack_surface_exposure_score")
    op.alter_column("scan_results", "zero_day_risk_level", new_column_name="attack_surface_exposure_level")


def downgrade() -> None:
    op.alter_column("scan_results", "attack_surface_exposure_score", new_column_name="zero_day_risk_score")
    op.alter_column("scan_results", "attack_surface_exposure_level", new_column_name="zero_day_risk_level")
