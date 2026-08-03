"""
NOVA — Slack Notification Channel
Posts to a Slack Incoming Webhook URL (https://api.slack.com/messaging/webhooks)
using Block Kit for readable formatting — no Slack SDK dependency needed,
it's a plain JSON POST like every other httpx-based integration in this
codebase.
"""

import httpx
import structlog

from app.config import get_settings
from app.services.notifications.base import NotificationChannel, NotificationPayload

logger = structlog.get_logger(__name__)
settings = get_settings()

_SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "scan_failed": "❌",
    "worker_stalled": "⚠️",
}


class SlackProvider(NotificationChannel):
    name = "slack"

    def is_configured(self) -> bool:
        return bool(settings.slack_webhook_url)

    async def send(self, payload: NotificationPayload) -> bool:
        if not self.is_configured():
            return False

        emoji = _SEVERITY_EMOJI.get(payload.severity, "🔔")
        fields = []
        if payload.repository_name:
            fields.append({"type": "mrkdwn", "text": f"*Repository:*\n{payload.repository_name}"})
        if payload.brs_score is not None:
            fields.append({"type": "mrkdwn", "text": f"*Banking Risk Score:*\n{payload.brs_score:.1f}/100 ({payload.risk_level or 'N/A'})"})
        if payload.scan_job_id:
            fields.append({"type": "mrkdwn", "text": f"*Scan ID:*\n`{payload.scan_job_id}`"})

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {payload.title}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": payload.summary}},
        ]
        if fields:
            blocks.append({"type": "section", "fields": fields})
        if payload.details_url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View Details"},
                            "url": payload.details_url,
                        }
                    ],
                }
            )

        body = {"text": f"{emoji} {payload.title}", "blocks": blocks}  # `text` is the fallback for notifications/screen readers

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(settings.slack_webhook_url, json=body)
                resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("notifications.slack_failed", error=str(exc))
            return False
