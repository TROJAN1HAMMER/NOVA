"""
NOVA — SQLAlchemy 2 Declarative Base
Every ORM model (Phase 2: Scan, Finding, Report, User, ...) inherits from
`Base`. Alembic's `env.py` imports `Base.metadata` to autogenerate migrations,
so this module must import every model package once models exist.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
