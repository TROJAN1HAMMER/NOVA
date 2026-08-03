"""
NOVA — Generic Webhook Notification Channel
Plain JSON POST to an operator-configured URL — the escape hatch for any
system without a dedicated provider here (PagerDuty, Opsgenie, a custom
internal tool, ...). HMAC-SHA256-signs the body when `webhook_secret` is
set, the same verification pattern GitHub/Stripe webhooks use, so the
receiver can confirm a request genuinely came from this NOVA instance
rather than trusting an unauthenticated POST to what might be a
guessable/public URL.
"""

import hashlib
import hmac
import json

import httpx
import structlog

from app.config import get_settings
from app.services.notifications.base import NotificationChannel, NotificationPayload

logger = structlog.get_logger(__name__)
settings = get_settings()


class WebhookProvider(NotificationChannel):
    name = "webhook"

    def is_configured(self) -> bool:
        return bool(settings.webhook_url)

    async def send(self, payload: NotificationPayload) -> bool:
        if not self.is_configured():
            return False

        body = {
            "title": payload.title,
            "summary": payload.summary,
            "severity": payload.severity,
            "scan_job_id": payload.scan_job_id,
            "repository_name": payload.repository_name,
            "brs_score": payload.brs_score,
            "risk_level": payload.risk_level,
            "details_url": payload.details_url,
            "extra": payload.extra,
        }
        raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if settings.webhook_secret:
            signature = hmac.new(settings.webhook_secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
            headers["X-NOVA-Signature"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(settings.webhook_url, content=raw, headers=headers)
                resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("notifications.webhook_failed", error=str(exc))
            return False
