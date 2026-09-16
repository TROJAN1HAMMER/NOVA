"""
NOVA Open-Web Evidence Retrieval & Verification — Service Facade
Manages search providers, executes external evidence retrieval, sanitizes content,
and normalizes results into UnifiedEvidenceItem objects for the RAG pipeline.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import structlog

from app.config import get_settings
from app.services.assistant.evidence_fusion import UnifiedEvidenceItem
from app.services.web_search.base import (
    ExternalSearchResponse,
    ExternalSearchResult,
    WebSearchProvider,
)
from app.services.web_search.google_provider import GoogleSerperSearchProvider
from app.services.web_search.security_filter import web_security_filter
from app.services.web_search.tavily_provider import TavilySearchProvider

logger = structlog.get_logger(__name__)


class WebSearchService:
    """Central service managing external web search providers and evidence normalization."""

    def __init__(self):
        self._provider_override: Optional[WebSearchProvider] = None

    def get_provider(self) -> WebSearchProvider:
        """Returns the configured WebSearchProvider instance."""
        if self._provider_override is not None:
            return self._provider_override

        settings = get_settings()
        provider_name = (settings.web_search_provider or "auto").lower().strip()

        if provider_name in ("google", "serper"):
            return GoogleSerperSearchProvider(
                api_key=settings.serper_api_key,
                timeout_seconds=settings.web_search_timeout_seconds,
            )

        if provider_name == "auto":
            # If Google Serper is configured, prefer Google for 100% full web coverage
            if settings.serper_api_key and settings.serper_api_key.strip():
                return GoogleSerperSearchProvider(
                    api_key=settings.serper_api_key,
                    timeout_seconds=settings.web_search_timeout_seconds,
                )
            return TavilySearchProvider(
                api_key=settings.tavily_api_key,
                timeout_seconds=settings.web_search_timeout_seconds,
            )

        if provider_name == "tavily":
            return TavilySearchProvider(
                api_key=settings.tavily_api_key,
                timeout_seconds=settings.web_search_timeout_seconds,
            )

        # Fallback / default
        return TavilySearchProvider(
            api_key=settings.tavily_api_key,
            timeout_seconds=settings.web_search_timeout_seconds,
        )

    def set_provider_override(self, provider: Optional[WebSearchProvider]) -> None:
        """Allows test suites to inject mock providers without network calls."""
        self._provider_override = provider

    def is_available(self) -> bool:
        """Checks if web search is enabled and a provider is properly configured."""
        settings = get_settings()
        if not settings.web_search_enabled:
            return False
        return self.get_provider().is_available()

    async def search(
        self,
        query: str,
        *,
        max_results: Optional[int] = None,
    ) -> ExternalSearchResponse:
        """Executes search through configured provider with settings defaults."""
        settings = get_settings()

        if not settings.web_search_enabled:
            return ExternalSearchResponse(
                query=query,
                provider=settings.web_search_provider,
                status="DISABLED",
                source_count=0,
                error_message="Open-web evidence retrieval is disabled in system configuration.",
            )

        provider = self.get_provider()
        limit = max_results or settings.web_search_max_results
        preferred = settings.web_search_preferred_domains

        response = await provider.search(
            query=query,
            max_results=limit,
            preferred_domains=preferred,
            blocked_domains=settings.web_search_blocked_domains,
        )

        # If preferred security domains returned no results, fallback to unrestricted open-web search
        if response.status == "SUCCESS" and not response.results and preferred:
            logger.info("web_search.unrestricted_fallback", query=query)
            response = await provider.search(
                query=query,
                max_results=limit,
                preferred_domains=None,
                blocked_domains=settings.web_search_blocked_domains,
            )

        return response

    async def retrieve_and_normalize_evidence(
        self,
        query: str,
        *,
        max_results: Optional[int] = None,
    ) -> Tuple_Results:
        """
        Executes external web search, applies security sanitization, and normalizes
        findings into UnifiedEvidenceItem objects compatible with NOVA's fusion engine.
        """
        response = await self.search(query, max_results=max_results)
        evidence_items: List[UnifiedEvidenceItem] = []

        if response.status != "SUCCESS" or not response.results:
            logger.info("web_search.no_external_evidence", status=response.status, query=query)
            return evidence_items, response

        for result in response.results:
            # 1. Sanitize text and neutralize prompt-injection attempts
            sanitized_snippet, flags = web_security_filter.sanitize_content(result.snippet)
            if not sanitized_snippet:
                continue

            # 2. Extract and classify source domain reliability
            domain = result.domain or web_security_filter.extract_domain(result.url)
            reliability_weight = web_security_filter.classify_source_reliability(domain)

            # 3. Formulate provenance metadata
            provenance = {
                "source_type": "EXTERNAL_WEB",
                "provider": result.provider,
                "url": result.url,
                "domain": domain,
                "title": result.title,
                "raw_score": result.raw_score,
                "published_at": result.published_at.isoformat() if result.published_at else None,
                "retrieved_at": result.retrieved_at.isoformat(),
                "injection_flags": flags,
            }

            item_id = f"ext-web-{uuid.uuid4().hex[:12]}"
            evidence_items.append(
                UnifiedEvidenceItem(
                    source_type="EXTERNAL_WEB",
                    source_id=item_id,
                    title=f"[Web] {result.title} ({domain})",
                    content=sanitized_snippet,
                    similarity_score=round(max(result.raw_score, 0.70), 4),
                    rerank_score=round(max(result.raw_score, 0.70), 4),
                    reliability_weight=reliability_weight,
                    timestamp=result.published_at or result.retrieved_at,
                    file_path=result.url,
                    provenance=provenance,
                    temporal_validity="ACTIVE" if result.published_at else "UNKNOWN",
                )
            )

        logger.info(
            "web_search.evidence_normalized",
            query=query,
            raw_count=len(response.results),
            accepted_count=len(evidence_items),
        )
        return evidence_items, response


# Return type alias for retrieve_and_normalize_evidence
Tuple_Results = tuple[List[UnifiedEvidenceItem], ExternalSearchResponse]

web_search_service = WebSearchService()
