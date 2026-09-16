"""
NOVA Open-Web Evidence Retrieval — Tavily Search Provider
Implements WebSearchProvider interface communicating with Tavily REST API.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import httpx
import structlog

from app.services.web_search.base import (
    ExternalSearchResponse,
    ExternalSearchResult,
    WebSearchProvider,
)
from app.services.web_search.security_filter import web_security_filter

logger = structlog.get_logger(__name__)

TAVILY_API_ENDPOINT = "https://api.tavily.com/search"


class TavilySearchProvider(WebSearchProvider):
    """Production Tavily external search provider using httpx."""

    def __init__(self, api_key: Optional[str] = "", timeout_seconds: float = 8.0):
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "tavily"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        preferred_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None,
    ) -> ExternalSearchResponse:
        start_time = time.monotonic()
        query_str = query.strip()

        if not self.api_key:
            return ExternalSearchResponse(
                query=query_str,
                provider="tavily",
                status="CONFIGURATION_REQUIRED",
                source_count=0,
                error_message="Tavily API key is missing. Set TAVILY_API_KEY to enable open-web evidence retrieval.",
                latency_ms=0.0,
            )

        payload: Dict[str, Any] = {
            "api_key": self.api_key,
            "query": query_str,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": max(1, min(max_results, 10)),
        }

        if preferred_domains:
            payload["include_domains"] = preferred_domains
        if blocked_domains:
            payload["exclude_domains"] = blocked_domains

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    TAVILY_API_ENDPOINT,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            latency = round((time.monotonic() - start_time) * 1000, 1)

            if response.status_code == 429:
                logger.warning("tavily_provider.rate_limited", latency_ms=latency)
                return ExternalSearchResponse(
                    query=query_str,
                    provider="tavily",
                    status="RATE_LIMITED",
                    source_count=0,
                    error_message="Tavily search API rate limit exceeded.",
                    latency_ms=latency,
                )

            if response.status_code != 200:
                logger.error("tavily_provider.http_error", status=response.status_code, body=response.text[:200])
                return ExternalSearchResponse(
                    query=query_str,
                    provider="tavily",
                    status="ERROR",
                    source_count=0,
                    error_message=f"Tavily returned HTTP {response.status_code}",
                    latency_ms=latency,
                )

            data = response.json()
            raw_results = data.get("results", [])
            parsed_results: List[ExternalSearchResult] = []

            for r in raw_results:
                url = str(r.get("url", "")).strip()
                title = str(r.get("title", "")).strip() or "Web Source"
                snippet = str(r.get("content", "")).strip()
                raw_score = float(r.get("score", 0.0) or 0.0)

                # Parse publication date if provided
                pub_date: Optional[datetime] = None
                pub_str = r.get("published_date")
                if pub_str and isinstance(pub_str, str):
                    try:
                        pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    except Exception:
                        pub_date = None

                domain = web_security_filter.extract_domain(url)
                parsed_results.append(
                    ExternalSearchResult(
                        title=title,
                        url=url,
                        domain=domain,
                        snippet=snippet,
                        raw_score=raw_score,
                        published_at=pub_date,
                        retrieved_at=datetime.now(timezone.utc),
                        provider="tavily",
                        metadata=r,
                    )
                )

            logger.info("tavily_provider.search_success", query=query_str, results_count=len(parsed_results), latency_ms=latency)
            return ExternalSearchResponse(
                query=query_str,
                provider="tavily",
                results=parsed_results,
                status="SUCCESS",
                source_count=len(parsed_results),
                latency_ms=latency,
            )

        except httpx.TimeoutException:
            latency = round((time.monotonic() - start_time) * 1000, 1)
            logger.warning("tavily_provider.timeout", timeout=self.timeout_seconds, latency_ms=latency)
            return ExternalSearchResponse(
                query=query_str,
                provider="tavily",
                status="TIMEOUT",
                source_count=0,
                error_message=f"Tavily search request timed out after {self.timeout_seconds}s.",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.monotonic() - start_time) * 1000, 1)
            logger.error("tavily_provider.exception", error=str(exc), latency_ms=latency)
            return ExternalSearchResponse(
                query=query_str,
                provider="tavily",
                status="ERROR",
                source_count=0,
                error_message=f"External search failed: {str(exc)}",
                latency_ms=latency,
            )
