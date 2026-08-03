"""
NOVA — Notification Service
The single call site `aggregator_tasks.py`/`maintenance_tasks.py` use to
fire an alert. Dispatches to every *configured* channel independently and
concurrently — one channel failing (a bad SMTP password, a rate-limited
Slack webhook) never blocks another from still delivering the same
alert, matching the fault-isolation philosophy used everywhere else in
this pipeline (one scanner failing doesn't block the other 8).
"""

import asyncio

import structlog

from app.config import get_settings
from app.services.notifications.base import NotificationChannel, NotificationPayload
from app.services.notifications.email_provider import EmailProvider
from app.services.notifications.slack_provider import SlackProvider
from app.services.notifications.webhook_provider import WebhookProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

_SEVERITY_ORDER = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _meets_threshold(severity: str, minimum: str) -> bool:
    try:
        return _SEVERITY_ORDER.index(severity.upper()) >= _SEVERITY_ORDER.index(minimum.upper())
    except ValueError:
        return False  # an unrecognized severity string never meets a real threshold


class NotificationService:
    def __init__(self, channels: list[NotificationChannel] | None = None) -> None:
        self.channels = channels if channels is not None else [SlackProvider(), EmailProvider(), WebhookProvider()]

    async def _dispatch(self, payload: NotificationPayload) -> None:
        if not settings.notifications_enabled:
            return

        configured = [c for c in self.channels if c.is_configured()]
        if not configured:
            logger.info("notifications.no_channel_configured", title=payload.title)
            return

        results = await asyncio.gather(*(c.send(payload) for c in configured), return_exceptions=True)
        for channel, result in zip(configured, results):
            if isinstance(result, Exception):
                logger.warning("notifications.channel_raised", channel=channel.name, error=str(result))
            elif not result:
                logger.warning("notifications.channel_failed", channel=channel.name, title=payload.title)
            else:
                logger.info("notifications.channel_sent", channel=channel.name, title=payload.title)

    async def notify_scan_completed(
        self,
        *,
        scan_job_id: str,
        repository_name: str,
        brs_score: float,
        risk_level: str,
        severity_counts: dict[str, int],
        details_url: str | None = None,
    ) -> None:
        """
        Only actually notifies if the scan produced at least one finding
        at or above `notify_min_severity` — a clean scan (or one with only
        low-severity noise) shouldn't page anyone.
        """
        highest = next(
            (sev for sev in reversed(_SEVERITY_ORDER) if severity_counts.get(sev, 0) > 0),
            None,
        )
        if highest is None or not _meets_threshold(highest, settings.notify_min_severity):
            return

        critical = severity_counts.get("CRITICAL", 0)
        high = severity_counts.get("HIGH", 0)
        await self._dispatch(
            NotificationPayload(
                title=f"Scan completed: {repository_name}",
                summary=(
                    f"Scan of *{repository_name}* found {critical} critical and {high} high severity "
                    f"finding(s). Banking Risk Score: {brs_score:.1f}/100 ({risk_level})."
                ),
                severity=highest,
                scan_job_id=scan_job_id,
                repository_name=repository_name,
                brs_score=brs_score,
                risk_level=risk_level,
                details_url=details_url,
                extra={"severity_counts": severity_counts},
            )
        )

    async def notify_scan_failed(self, *, scan_job_id: str, repository_name: str, error_message: str) -> None:
        await self._dispatch(
            NotificationPayload(
                title=f"Scan failed: {repository_name}",
                summary=f"Scan of *{repository_name}* failed: {error_message}",
                severity="scan_failed",
                scan_job_id=scan_job_id,
                repository_name=repository_name,
            )
        )

    async def notify_worker_stalled(self, *, scan_job_id: str, age_seconds: float) -> None:
        await self._dispatch(
            NotificationPayload(
                title="Scan worker stalled",
                summary=(
                    f"Scan job `{scan_job_id}` had no heartbeat for {age_seconds:.0f}s and was presumed "
                    f"crashed — retried automatically if retries remain, otherwise marked failed."
                ),
                severity="worker_stalled",
                scan_job_id=scan_job_id,
            )
        )


_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
