"""
NOVA Open-Web Evidence Retrieval & Verification Layer
"""

from app.services.web_search.base import (
    ExternalSearchResponse,
    ExternalSearchResult,
    WebSearchProvider,
)
from app.services.web_search.security_filter import (
    WebSecurityFilter,
    web_security_filter,
)
from app.services.web_search.tavily_provider import TavilySearchProvider
from app.services.web_search.service import WebSearchService, web_search_service

__all__ = [
    "ExternalSearchResponse",
    "ExternalSearchResult",
    "WebSearchProvider",
    "TavilySearchProvider",
    "WebSecurityFilter",
    "web_security_filter",
    "WebSearchService",
    "web_search_service",
]
