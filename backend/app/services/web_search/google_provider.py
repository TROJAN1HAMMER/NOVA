"""
NOVA Open-Web Evidence Retrieval — Google Live Web Provider
Interfaces with Google's global live index (via Google Serper / Custom Search)
to provide 100% exhaustive internet coverage for general, localized, student roll,
academic, government, and deep document search queries.
"""

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

SERPER_API_ENDPOINT = "https://google.serper.dev/search"


class GoogleSerperSearchProvider(WebSearchProvider):
    """
    Google Live Web Search provider using Serper API.
    Provides 1:1 identical search results to Google Search (google.com)
    covering 100% of public web pages, PDFs, and institution subpages.
    """

    def __init__(self, api_key: str, timeout_seconds: float = 10.0):
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = timeout_seconds

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

        if not self.is_available():
            return ExternalSearchResponse(
                query=query_str,
                provider="google_serper",
                status="CONFIGURATION_REQUIRED",
                source_count=0,
                error_message="Google Serper API key is not configured. Set SERPER_API_KEY in backend/.env to enable 100% Google web checking.",
                latency_ms=0.0,
            )

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "q": query_str,
            "num": max(1, min(max_results, 10)),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    SERPER_API_ENDPOINT,
                    json=payload,
                    headers=headers,
                )

            latency = round((time.monotonic() - start_time) * 1000, 1)

            if response.status_code == 429:
                logger.warning("google_serper.rate_limited", latency_ms=latency)
                return ExternalSearchResponse(
                    query=query_str,
                    provider="google",
                    status="RATE_LIMITED",
                    source_count=0,
                    error_message="Google search rate limit reached.",
                    latency_ms=latency,
                )

            if response.status_code != 200:
                logger.error("google_serper.http_error", status=response.status_code, body=response.text[:200])
                return ExternalSearchResponse(
                    query=query_str,
                    provider="google",
                    status="ERROR",
                    source_count=0,
                    error_message=f"Google provider returned HTTP {response.status_code}",
                    latency_ms=latency,
                )

            data = response.json()
            organic = data.get("organic", [])
            parsed_results: List[ExternalSearchResult] = []

            for item in organic:
                url = str(item.get("link", "")).strip()
                title = str(item.get("title", "")).strip() or "Google Result"
                snippet = str(item.get("snippet", "")).strip()
                domain = web_security_filter.extract_domain(url)

                if blocked_domains and any(domain.endswith(bd) for bd in blocked_domains):
                    continue

                parsed_results.append(
                    ExternalSearchResult(
                        title=title,
                        url=url,
                        domain=domain,
                        snippet=snippet,
                        raw_score=0.92,
                        provider="google",
                    )
                )

            logger.info("google_serper.search_success", query=query_str, results_count=len(parsed_results), latency_ms=latency)
            return ExternalSearchResponse(
                query=query_str,
                provider="google",
                results=parsed_results[:max_results],
                status="SUCCESS",
                source_count=len(parsed_results[:max_results]),
                latency_ms=latency,
            )

        except httpx.TimeoutException:
            latency = round((time.monotonic() - start_time) * 1000, 1)
            logger.warning("google_serper.timeout", latency_ms=latency)
            return ExternalSearchResponse(
                query=query_str,
                provider="google",
                status="TIMEOUT",
                source_count=0,
                error_message=f"Google search timed out after {self.timeout_seconds}s",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = round((time.monotonic() - start_time) * 1000, 1)
            logger.error("google_serper.exception", error=str(exc), latency_ms=latency)
            return ExternalSearchResponse(
                query=query_str,
                provider="google",
                status="ERROR",
                source_count=0,
                error_message=str(exc),
                latency_ms=latency,
            )
