"""
NOVA — Risk Configuration Models
Stores database-driven configurations for the Banking Risk Score (BRS) engine:
business modules (with asset values and keywords) and factor weights.
"""

from typing import Any, List, Optional

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BusinessModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "business_modules"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    keywords: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    criticality_weight: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    asset_value: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    is_internet_facing_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RiskFactorWeight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_factor_weights"

    factor_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
