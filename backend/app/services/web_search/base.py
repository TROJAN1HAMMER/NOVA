"""
NOVA Open-Web Evidence Retrieval — Base Provider Abstraction
Defines clean vendor-agnostic contracts for external search providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ExternalSearchResult:
    """Represents an individual retrieved web source with full provenance."""
    title: str
    url: str
    domain: str
    snippet: str
    raw_score: float = 0.0
    published_at: Optional[datetime] = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalSearchResponse:
    """Standardized result envelope returned by all web search providers."""
    query: str
    provider: str
    results: List[ExternalSearchResult] = field(default_factory=list)
    status: str = "SUCCESS"  # SUCCESS | DISABLED | CONFIGURATION_REQUIRED | RATE_LIMITED | TIMEOUT | ERROR
    source_count: int = 0
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "provider": self.provider,
            "source_count": self.source_count,
            "status": self.status,
            "retrieved_at": self.retrieved_at,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "domain": r.domain,
                    "snippet": r.snippet,
                    "raw_score": r.raw_score,
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "retrieved_at": r.retrieved_at.isoformat(),
                    "provider": r.provider,
                }
                for r in self.results
            ],
        }


class WebSearchProvider(ABC):
    """Abstract interface for external search providers (Tavily, Brave, etc.)."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider has valid configuration / API keys."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        preferred_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
    ) -> ExternalSearchResponse:
        """Executes search query against external provider and returns normalized response envelope."""
        ...
