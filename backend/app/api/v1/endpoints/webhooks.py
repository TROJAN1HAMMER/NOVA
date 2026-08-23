"""
NOVA — GitHub Webhook Endpoint
Receives push events from GitHub, validates HMAC SHA-256 signatures,
resolves/creates Repository entities, and queues scan pipeline jobs.
"""

import hashlib
import hmac
import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.schemas.webhook import WebhookAckResponse
from app.services.scan_intake import submit_repository

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _verify_github_signature(payload: bytes, signature_header: Optional[str], secret: str) -> None:
    """Verify HMAC SHA-256 signature sent by GitHub in X-Hub-Signature-256."""
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook secret is not configured on this server",
        )

    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header",
        )

    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature_header, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )


@router.post("/github", response_model=WebhookAckResponse, summary="GitHub push event receiver")
async def github_webhook_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
) -> WebhookAckResponse:
    """Handle incoming GitHub webhook events with signature verification."""
    body = await request.body()
    current_settings = get_settings()

    # 1. Verify HMAC Signature
    _verify_github_signature(body, x_hub_signature_256, current_settings.github_webhook_secret)

    event = (x_github_event or "push").lower()

    # 2. Ping Event Handler
    if event == "ping":
        logger.info("webhook.github.ping_received")
        return WebhookAckResponse(status="ping_ok", message="Ping event verified successfully")

    # 3. Non-push events are ignored gracefully
    if event != "push":
        logger.info("webhook.github.ignored_event", event=event)
        return WebhookAckResponse(status="ignored", message=f"Event type '{event}' is ignored")

    # 4. Parse push payload
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Malformed JSON: {exc}")

    # Ignore branch deletion events
    if payload.get("deleted") is True:
        logger.info("webhook.github.branch_deleted")
        return WebhookAckResponse(status="ignored", message="Branch deletion event ignored")

    repo_data = payload.get("repository", {})
    clone_url = repo_data.get("clone_url") or repo_data.get("html_url")
    if not clone_url:
        logger.warning("webhook.github.missing_clone_url")
        return WebhookAckResponse(status="ignored", message="Missing repository clone_url")

    raw_ref = payload.get("ref", "refs/heads/main")
    branch = raw_ref.replace("refs/heads/", "")
    default_branch = repo_data.get("default_branch", "main")

    # Branch filtering check
    if not current_settings.github_webhook_scan_all_branches and branch != default_branch:
        logger.info("webhook.github.non_default_branch_ignored", branch=branch, default=default_branch)
        return WebhookAckResponse(status="ignored", message=f"Branch '{branch}' is not the default branch")

    # 5. Queue scan job through central scan intake service
    repo, job = await submit_repository(
        db,
        repo_url=clone_url,
        ref=branch,
        owner_id=None,
    )

    logger.info(
        "webhook.github.scan_queued",
        repository_id=str(repo.id),
        scan_job_id=str(job.id),
        repo_url=clone_url,
        branch=branch,
    )

    return WebhookAckResponse(
        status="scan_queued",
        message="Push event verified and scan job queued",
        scan_job_id=job.id,
        repository_id=repo.id,
    )
