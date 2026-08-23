"""
NOVA — Risk Configuration Endpoints
Allows dynamic configuration of business modules, factor weights, and real-time
BRS score preview calculation.
"""

from typing import List

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.db.session import get_db
from app.models.risk_config import BusinessModule, RiskFactorWeight
from app.models.user import User
from app.schemas.risk_config import (
    BusinessModuleCreateRequest,
    BusinessModuleResponse,
    BusinessModuleUpdateRequest,
    RiskFactorWeightResponse,
    RiskFactorWeightUpsertRequest,
    ScorePreviewRequest,
    ScorePreviewResponse,
)
from app.services.risk.brs_engine import (
    DEFAULT_FACTOR_WEIGHTS,
    DEFAULT_MODULES,
    FactorWeights,
    classify_module,
    score_finding,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/risk", tags=["Risk Configuration"])


# ── Business Modules Endpoints ────────────────────────────────────────────────


@router.get("/modules", response_model=List[BusinessModuleResponse], summary="List Business Modules")
async def list_business_modules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[BusinessModuleResponse]:
    """List every configured business module in the database."""
    result = await db.execute(select(BusinessModule).order_by(BusinessModule.name.asc()))
    modules = result.scalars().all()
    return [BusinessModuleResponse.model_validate(m) for m in modules]


@router.post(
    "/modules",
    response_model=BusinessModuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Business Module",
)
async def create_business_module(
    body: BusinessModuleCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BusinessModuleResponse:
    """Add a new business module."""
    existing = await db.execute(select(BusinessModule).where(BusinessModule.name == body.name))
    if existing.scalar_one_or_none():
        raise ConflictAppError(f"Business module '{body.name}' already exists")

    module = BusinessModule(
        name=body.name,
        keywords=body.keywords,
        criticality_weight=body.criticality_weight,
        asset_value=body.asset_value,
        is_internet_facing_default=body.is_internet_facing_default,
        is_default=body.is_default,
        description=body.description,
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)

    logger.info("risk_config.module_created", name=module.name)
    return BusinessModuleResponse.model_validate(module)


@router.patch("/modules/{module_name}", response_model=BusinessModuleResponse, summary="Update Business Module")
async def update_business_module(
    module_name: str,
    body: BusinessModuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> BusinessModuleResponse:
    """Adjust a module's weights, keywords, or properties."""
    result = await db.execute(select(BusinessModule).where(BusinessModule.name == module_name))
    module = result.scalar_one_or_none()
    if module is None:
        raise NotFoundError(f"Business module '{module_name}' not found")

    if body.keywords is not None:
        module.keywords = body.keywords
    if body.criticality_weight is not None:
        module.criticality_weight = body.criticality_weight
    if body.asset_value is not None:
        module.asset_value = body.asset_value
    if body.is_internet_facing_default is not None:
        module.is_internet_facing_default = body.is_internet_facing_default
    if body.description is not None:
        module.description = body.description

    await db.commit()
    await db.refresh(module)
    logger.info("risk_config.module_updated", name=module.name)
    return BusinessModuleResponse.model_validate(module)


@router.delete("/modules/{module_name}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Business Module")
async def delete_business_module(
    module_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Remove a custom business module."""
    result = await db.execute(select(BusinessModule).where(BusinessModule.name == module_name))
    module = result.scalar_one_or_none()
    if module is None:
        raise NotFoundError(f"Business module '{module_name}' not found")

    if module.is_default:
        raise ValidationAppError(f"Default fallback module '{module_name}' cannot be deleted")

    await db.delete(module)
    await db.commit()
    logger.info("risk_config.module_deleted", name=module_name)


# ── Risk Factor Weights Endpoints ─────────────────────────────────────────────


@router.get("/factor-weights", response_model=List[RiskFactorWeightResponse], summary="List Risk Factor Weights")
async def list_risk_factor_weights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[RiskFactorWeightResponse]:
    """List every factor's weight in the BRS blend."""
    result = await db.execute(select(RiskFactorWeight).order_by(RiskFactorWeight.factor_name.asc()))
    weights = result.scalars().all()
    return [RiskFactorWeightResponse.model_validate(w) for w in weights]


@router.patch("/factor-weights/{factor_name}", response_model=RiskFactorWeightResponse, summary="Update Risk Factor Weight")
async def update_risk_factor_weight(
    factor_name: str,
    body: RiskFactorWeightUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RiskFactorWeightResponse:
    """Set or upsert a risk factor's weight."""
    result = await db.execute(select(RiskFactorWeight).where(RiskFactorWeight.factor_name == factor_name))
    weight_obj = result.scalar_one_or_none()

    if weight_obj is None:
        weight_obj = RiskFactorWeight(
            factor_name=factor_name,
            weight=body.weight,
            description=body.description,
        )
        db.add(weight_obj)
    else:
        weight_obj.weight = body.weight
        if body.description is not None:
            weight_obj.description = body.description

    await db.commit()
    await db.refresh(weight_obj)
    logger.info("risk_config.factor_weight_updated", factor=factor_name, weight=body.weight)
    return RiskFactorWeightResponse.model_validate(weight_obj)


# ── Score Preview Endpoint ────────────────────────────────────────────────────


@router.post("/preview", response_model=ScorePreviewResponse, summary="Preview Score")
async def preview_score(
    body: ScorePreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScorePreviewResponse:
    """Score a synthetic finding against the current database configuration."""
    weights_res = await db.execute(select(RiskFactorWeight))
    weights = list(weights_res.scalars().all())

    modules_res = await db.execute(select(BusinessModule))
    modules = list(modules_res.scalars().all())

    finding_dict = {
        "title": body.title,
        "severity": body.severity,
        "category": body.category,
        "cvss": body.cvss,
        "file_path": body.file_path,
        "description": body.description,
        "cve": body.cve,
        "compliance_framework_count": body.compliance_framework_count,
        "historical_incident_count": body.historical_incident_count,
    }

    classified_module = classify_module(
        finding=finding_dict,
        modules=modules or DEFAULT_MODULES,
    )

    weights_dict = {w.factor_name: float(w.weight) for w in weights} if weights else {}
    if weights_dict:
        # Construct custom FactorWeights
        valid_kwargs = {k: v for k, v in weights_dict.items() if hasattr(FactorWeights, k)}
        weights_obj = FactorWeights(**valid_kwargs)
    else:
        weights_obj = DEFAULT_FACTOR_WEIGHTS

    scored = score_finding(
        finding=finding_dict,
        module=classified_module,
        factor_weights=weights_obj,
        compliance_framework_count=body.compliance_framework_count,
        historical_incident_count=body.historical_incident_count,
    )

    return ScorePreviewResponse(
        brs=scored.brs,
        module=classified_module.name,
        sub_scores=scored.sub_scores,
        factor_weights=scored.factor_weights,
    )
