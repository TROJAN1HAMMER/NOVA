"""
NOVA — Notification Channel Interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NotificationPayload:
    """
    Channel-agnostic description of an alert-worthy event — each provider
    renders this into its own wire format (Slack Block Kit, an email
    body, a generic JSON POST).
    """

    title: str
    summary: str
    severity: str  # CRITICAL | HIGH | scan_failed | worker_stalled | ...
    scan_job_id: Optional[str] = None
    repository_name: Optional[str] = None
    brs_score: Optional[float] = None
    risk_level: Optional[str] = None
    details_url: Optional[str] = None
    extra: dict = field(default_factory=dict)


class NotificationChannel(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this channel has what it needs (a URL, SMTP host, ...) to be attempted at all."""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """Returns True on success. Never raises — a channel-specific error is caught and logged by the channel itself."""
