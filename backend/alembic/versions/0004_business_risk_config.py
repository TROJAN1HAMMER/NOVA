"""business risk score engine — configurable modules + factor weights

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-17

Creates `business_modules` and `risk_factor_weights` — the database-driven
configuration `app/services/risk/brs_engine.py` reads instead of the
hardcoded `MODULE_WEIGHTS` list the original engine carried in source.
Seed values are the same module/keyword breakdown that list always had,
rescaled onto the new engine's 0-10 sub-score convention; both tables are
freely editable afterward via `app/api/v1/endpoints/risk_config.py` with
no code deploy required.

Also adds `findings.module` (nullable, indexed) — the "historical
incidents" BRS factor needs to query per-module CRITICAL/HIGH counts
across a repository's past scans, which requires the classification to be
persisted, not re-derived from category/file_path on every read.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("keywords", postgresql.JSONB(), nullable=False),
        sa.Column("criticality_weight", sa.Float(), nullable=False, server_default="4.0"),
        sa.Column("asset_value", sa.Float(), nullable=False, server_default="4.0"),
        sa.Column("is_internet_facing_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_business_modules_name", "business_modules", ["name"], unique=True)

    op.create_table(
        "risk_factor_weights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("factor_name", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_risk_factor_weights_factor_name", "risk_factor_weights", ["factor_name"], unique=True)

    op.add_column("findings", sa.Column("module", sa.String(length=64), nullable=True))
    op.create_index("ix_findings_module", "findings", ["module"])

    business_modules = sa.table(
        "business_modules",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("keywords", postgresql.JSONB),
        sa.column("criticality_weight", sa.Float),
        sa.column("asset_value", sa.Float),
        sa.column("is_internet_facing_default", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        business_modules,
        [
            {
                "id": str(uuid.uuid4()),
                "name": "Payments",
                "keywords": [
                    "payment", "pay", "transaction", "transfer", "remittance",
                    "upi", "neft", "imps", "rtgs",
                ],
                "criticality_weight": 10.0,
                "asset_value": 10.0,
                "is_internet_facing_default": True,
                "is_default": False,
                "description": "Payment initiation, transfers, settlement",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Authentication",
                "keywords": [
                    "auth", "login", "jwt", "session", "oauth", "token",
                    "password", "credential", "2fa", "mfa",
                ],
                "criticality_weight": 8.5,
                "asset_value": 8.0,
                "is_internet_facing_default": True,
                "is_default": False,
                "description": "Login, session management, identity",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Customer Data",
                "keywords": [
                    "customer", "kyc", "pii", "personal", "account",
                    "user_data", "profile", "aadhaar", "pan",
                ],
                "criticality_weight": 7.0,
                "asset_value": 9.0,
                "is_internet_facing_default": True,
                "is_default": False,
                "description": "PII, KYC records, customer account data",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Infrastructure",
                "keywords": ["dockerfile", "docker-compose", ".github", "helm", "k8s", "terraform"],
                "criticality_weight": 5.0,
                "asset_value": 6.0,
                "is_internet_facing_default": False,
                "is_default": False,
                "description": "Deployment/container/CI configuration",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Admin",
                "keywords": ["admin", "management", "superuser", "dashboard"],
                "criticality_weight": 5.5,
                "asset_value": 6.0,
                "is_internet_facing_default": False,
                "is_default": False,
                "description": "Administrative/back-office interfaces",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Reporting",
                "keywords": ["report", "audit", "log", "analytics", "statement", "export"],
                "criticality_weight": 3.0,
                "asset_value": 3.0,
                "is_internet_facing_default": False,
                "is_default": False,
                "description": "Reporting, analytics, audit trails",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "General",
                "keywords": [],
                "criticality_weight": 4.0,
                "asset_value": 4.0,
                "is_internet_facing_default": False,
                "is_default": True,
                "description": "Fallback module when no keyword matches",
            },
        ],
    )

    risk_factor_weights = sa.table(
        "risk_factor_weights",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("factor_name", sa.String),
        sa.column("weight", sa.Float),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        risk_factor_weights,
        [
            {"id": str(uuid.uuid4()), "factor_name": "cvss", "weight": 0.30, "description": "Raw CVSS base score"},
            {
                "id": str(uuid.uuid4()),
                "factor_name": "exploitability",
                "weight": 0.15,
                "description": "How directly exploitable the vulnerability class typically is",
            },
            {
                "id": str(uuid.uuid4()),
                "factor_name": "business_criticality",
                "weight": 0.20,
                "description": "BusinessModule.criticality_weight for the finding's module",
            },
            {
                "id": str(uuid.uuid4()),
                "factor_name": "internet_exposure",
                "weight": 0.10,
                "description": "Whether the affected code/module is internet-facing",
            },
            {
                "id": str(uuid.uuid4()),
                "factor_name": "compliance_impact",
                "weight": 0.10,
                "description": "Number of regulatory frameworks (RBI/PCI/SWIFT) implicated",
            },
            {
                "id": str(uuid.uuid4()),
                "factor_name": "asset_value",
                "weight": 0.10,
                "description": "BusinessModule.asset_value for the finding's module",
            },
            {
                "id": str(uuid.uuid4()),
                "factor_name": "historical_incidents",
                "weight": 0.05,
                "description": "Prior CRITICAL/HIGH findings in this module for this repository",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_findings_module", table_name="findings")
    op.drop_column("findings", "module")

    op.drop_index("ix_risk_factor_weights_factor_name", table_name="risk_factor_weights")
    op.drop_table("risk_factor_weights")

    op.drop_index("ix_business_modules_name", table_name="business_modules")
    op.drop_table("business_modules")
