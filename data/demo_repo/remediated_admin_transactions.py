"""
NOVA Demo Banking API — Remediated Endpoint Fixture
Location: data/demo_repo/remediated_admin_transactions.py

This snippet contains the patched authorization middleware enforcement (RequireRole('admin'))
verified by NOVA's RemediationVerifierService.
"""

from fastapi import APIRouter, Depends, Form, HTTPException
from typing import Dict, Any, List
from app.auth.rbac import RequireRole

router = APIRouter(prefix="/admin", tags=["Admin Transactions"])

# REMEDIATED STATE: Enforces RequireRole('admin') middleware dependency
@router.post("/transactions", dependencies=[Depends(RequireRole("admin"))])
def export_admin_transactions(account_id: str = Form(...), limit: int = Form(100)) -> Dict[str, Any]:
    """
    REMEDIATED STATE:
    POST /admin/transactions requires administrator authorization before returning transaction records.
    """
    return {
        "status": "SUCCESS",
        "account_id": account_id,
        "exported_records": limit,
        "transactions": [
            {"tx_id": "TX-9021", "amount": 45000.00, "currency": "USD", "type": "WIRE_TRANSFER"},
            {"tx_id": "TX-9022", "amount": 12800.50, "currency": "EUR", "type": "SWIFT_SETTLEMENT"}
        ]
    }
