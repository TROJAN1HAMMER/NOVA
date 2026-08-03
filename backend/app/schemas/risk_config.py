"""
NOVA — Risk Configuration Pydantic Schemas
DTOs for the BRS engine's database-driven configuration: business
modules and per-factor weights (app/services/risk/brs_engine.py), plus
the request/response shape for the score-preview endpoint.
"""

import uuid
from typing import Optional

from pydantic import BaseModel, Field


# ── Business Modules ───────────────────────────────────────────────────────────

class BusinessModuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    keywords: list[str] = Field(default_factory=list)
    criticality_weight: float = Field(..., ge=0, le=10)
    asset_value: float = Field(..., ge=0, le=10)
    is_internet_facing_default: bool = False
    is_default: bool = False
    description: Optional[str] = None


class BusinessModuleUpdateRequest(BaseModel):
    keywords: Optional[list[str]] = None
    criticality_weight: Optional[float] = Field(default=None, ge=0, le=10)
    asset_value: Optional[float] = Field(default=None, ge=0, le=10)
    is_internet_facing_default: Optional[bool] = None
    description: Optional[str] = None


class BusinessModuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    keywords: list[str]
    criticality_weight: float
    asset_value: float
    is_internet_facing_default: bool
    is_default: bool
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Risk Factor Weights ─────────────────────────────────────────────────────────

class RiskFactorWeightUpsertRequest(BaseModel):
    weight: float = Field(..., ge=0)
    description: Optional[str] = None


class RiskFactorWeightResponse(BaseModel):
    id: uuid.UUID
    factor_name: str
    weight: float
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Score Preview ───────────────────────────────────────────────────────────────

class ScorePreviewRequest(BaseModel):
    """A synthetic finding to run through the current DB-configured
    formula — lets an operator see exactly how a weight/module change
    would affect scoring before a real scan hits it."""

    title: str = "Preview finding"
    severity: str = Field(default="HIGH", pattern="^(CRITICAL|HIGH|MEDIUM|LOW|INFO)$")
    category: str = "sql_injection"
    cvss: float = Field(default=7.5, ge=0, le=10)
    file_path: Optional[str] = None
    description: str = ""
    cve: Optional[str] = None
    compliance_framework_count: int = Field(default=0, ge=0, le=3)
    historical_incident_count: int = Field(default=0, ge=0)


class ScorePreviewResponse(BaseModel):
    brs: float
    module: str
    sub_scores: dict[str, float]
    factor_weights: dict[str, float]
