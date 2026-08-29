"""
NOVA Demo Banking API — Vulnerable Endpoint Fixture
Location: data/demo_repo/admin_transactions.py

This endpoint exposes administrative transaction data without authorization middleware,
creating a verifiable AUTHORIZATION deficit for NOVA's Security Intelligence Subsystem.
"""

from fastapi import APIRouter, Form, HTTPException
from typing import Dict, Any, List

router = APIRouter(prefix="/admin", tags=["Admin Transactions"])

# Vulnerable Endpoint: Missing authorization dependency RequireRole('admin')
@router.post("/transactions")
def export_admin_transactions(account_id: str = Form(...), limit: int = Form(100)) -> Dict[str, Any]:
    """
    VULNERABLE STATE:
    POST /admin/transactions does not verify administrator authorization
    before returning customer transaction records.
    """
    # Flaw: Missing authorization verification step
    return {
        "status": "SUCCESS",
        "account_id": account_id,
        "exported_records": limit,
        "transactions": [
            {"tx_id": "TX-9021", "amount": 45000.00, "currency": "USD", "type": "WIRE_TRANSFER"},
            {"tx_id": "TX-9022", "amount": 12800.50, "currency": "EUR", "type": "SWIFT_SETTLEMENT"}
        ]
    }
