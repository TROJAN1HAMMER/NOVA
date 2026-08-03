"""
NOVA — Email Notification Channel
Plain stdlib `smtplib`/`email.mime` — no extra dependency, run inside
`asyncio.to_thread` since `smtplib` is synchronous. This mirrors the same
"wrap a sync stdlib/third-party API in a thread" pattern already used
elsewhere (reportlab PDF rendering, ldap3's bind/search calls).
"""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.config import get_settings
from app.services.notifications.base import NotificationChannel, NotificationPayload

logger = structlog.get_logger(__name__)
settings = get_settings()


class EmailProvider(NotificationChannel):
    name = "email"

    def is_configured(self) -> bool:
        return bool(settings.email_smtp_host and settings.email_to_addresses)

    async def send(self, payload: NotificationPayload) -> bool:
        if not self.is_configured():
            return False
        try:
            return await asyncio.to_thread(self._send_sync, payload)
        except Exception as exc:
            logger.warning("notifications.email_failed", error=str(exc))
            return False

    def _send_sync(self, payload: NotificationPayload) -> bool:
        message = MIMEMultipart("alternative")
        message["Subject"] = f"[NOVA] {payload.title}"
        message["From"] = settings.email_from_address
        message["To"] = ", ".join(settings.email_to_addresses)

        text_lines = [payload.summary, ""]
        if payload.repository_name:
            text_lines.append(f"Repository: {payload.repository_name}")
        if payload.brs_score is not None:
            text_lines.append(f"Banking Risk Score: {payload.brs_score:.1f}/100 ({payload.risk_level or 'N/A'})")
        if payload.scan_job_id:
            text_lines.append(f"Scan ID: {payload.scan_job_id}")
        if payload.details_url:
            text_lines.append(f"Details: {payload.details_url}")
        message.attach(MIMEText("\n".join(text_lines), "plain"))

        html = f"""
        <html><body>
        <h2>{payload.title}</h2>
        <p>{payload.summary}</p>
        <ul>
          {f'<li><b>Repository:</b> {payload.repository_name}</li>' if payload.repository_name else ''}
          {f'<li><b>Banking Risk Score:</b> {payload.brs_score:.1f}/100 ({payload.risk_level or "N/A"})</li>' if payload.brs_score is not None else ''}
          {f'<li><b>Scan ID:</b> {payload.scan_job_id}</li>' if payload.scan_job_id else ''}
        </ul>
        {f'<p><a href="{payload.details_url}">View Details</a></p>' if payload.details_url else ''}
        </body></html>
        """
        message.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port, timeout=10) as server:
            if settings.email_smtp_use_tls:
                server.starttls()
            if settings.email_smtp_username:
                server.login(settings.email_smtp_username, settings.email_smtp_password)
            server.sendmail(settings.email_from_address, settings.email_to_addresses, message.as_string())
        return True
