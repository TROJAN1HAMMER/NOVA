"""widen finding compliance clause columns

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-17

The real clause descriptions in app/data/compliance_mappings.json run up
to 141 characters ("RBI IT Framework 2021 — Section 4.2: Access Control &
Identity Management; Annex II: Sensitive Data Protection") — the original
VARCHAR(64) truncated the moment a finding with a full-length mapped
clause was persisted, raising a hard DB error on every real compliance-
mapped scan rather than just a cosmetically-truncated string.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for column in ("rbi_clause", "pci_clause", "swift_clause"):
        op.alter_column(
            "findings",
            column,
            existing_type=sa.String(length=64),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade() -> None:
    # Not reversible without risking data loss: a real clause longer than
    # 64 chars (the common case, not the exception) would silently
    # truncate on downgrade. Widening is one-way.
    raise NotImplementedError(
        "Downgrade would truncate real compliance clause data — not supported."
    )
