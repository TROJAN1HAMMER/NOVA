"""
Unit tests for NOVA Open-Web Search Providers (Tavily Provider).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.web_search.tavily_provider import TavilySearchProvider
from app.services.web_search.base import ExternalSearchResponse


def test_tavily_provider_availability():
    """Verify provider reports availability based on API key presence."""
    provider_with_key = TavilySearchProvider(api_key="tvly-test-123")
    assert provider_with_key.is_available() is True
    assert provider_with_key.provider_name == "tavily"

    provider_without_key = TavilySearchProvider(api_key="")
    assert provider_without_key.is_available() is False

    provider_none_key = TavilySearchProvider(api_key=None)
    assert provider_none_key.is_available() is False


@pytest.mark.asyncio
async def test_tavily_missing_key_graceful_handling():
    """Missing API key returns CONFIGURATION_REQUIRED status without throwing exceptions."""
    provider = TavilySearchProvider(api_key="")
    response = await provider.search("test query")

    assert response.status in ("CONFIGURATION_REQUIRED", "MISSING_API_KEY")
    assert response.source_count == 0
    assert "missing" in response.error_message.lower() or "not configured" in response.error_message.lower()


@pytest.mark.asyncio
async def test_tavily_search_success_parsing():
    """Successful Tavily JSON response is parsed into normalized ExternalSearchResult objects."""
    provider = TavilySearchProvider(api_key="tvly-test-123")

    mock_tavily_payload = {
        "results": [
            {
                "title": "OWASP API Security Top 10",
                "url": "https://owasp.org/www-project-api-security/",
                "content": "API security guidance and top vulnerabilities including broken object level authorization.",
                "score": 0.88,
                "published_date": "2023-11-15T12:00:00Z"
            },
            {
                "title": "NIST SP 800-53 Rev 5",
                "url": "https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final",
                "content": "Security and privacy controls for information systems and organizations.",
                "score": 0.94,
                "published_date": None
            }
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_tavily_payload

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        res = await provider.search("OWASP API security")

        assert res.status == "SUCCESS"
        assert res.source_count == 2
        assert len(res.results) == 2
        assert res.results[0].title == "OWASP API Security Top 10"
        assert res.results[0].domain == "owasp.org"
        assert res.results[0].raw_score == 0.88
        assert res.results[0].published_at is not None
        assert res.results[1].domain == "csrc.nist.gov"
        assert res.results[1].published_at is None


@pytest.mark.asyncio
async def test_tavily_rate_limiting_429():
    """Rate limit 429 returns RATE_LIMITED status with informative message."""
    provider = TavilySearchProvider(api_key="tvly-test-123")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        res = await provider.search("rate limited query")

        assert res.status == "RATE_LIMITED"
        assert res.source_count == 0
        assert "rate limit" in res.error_message.lower()


@pytest.mark.asyncio
async def test_tavily_timeout_handling():
    """Timeout during HTTP request is caught and reported as TIMEOUT."""
    provider = TavilySearchProvider(api_key="tvly-test-123", timeout_seconds=1.0)

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Connection timed out")):
        res = await provider.search("slow query")

        assert res.status == "TIMEOUT"
        assert res.source_count == 0
        assert "timed out" in res.error_message.lower()


@pytest.mark.asyncio
async def test_tavily_domain_filtering_parameters():
    """Domain allowlists and blocklists are correctly serialized in request payload."""
    provider = TavilySearchProvider(api_key="tvly-test-123")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await provider.search(
            "security standard",
            max_results=3,
            preferred_domains=["owasp.org", "nist.gov"],
            blocked_domains=["spam.com"]
        )

        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        sent_json = call_kwargs["json"]
        assert sent_json["max_results"] == 3
        assert "owasp.org" in sent_json["include_domains"]
        assert "spam.com" in sent_json["exclude_domains"]
