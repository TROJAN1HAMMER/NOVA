"""
NOVA — LLM Gateway

This is the ONLY module in NOVA allowed to import from
`app.services.ai.providers`. Every caller — `ai_engine.py`'s high-level
functions today, anything else in the future — goes through
`get_gateway().complete()` / `.stream()`, never a provider class directly.
That's what makes "the rest of NOVA should never directly call
providers" an enforced structural property rather than a convention
people can forget.

Responsibilities:
  - Provider fallback: try providers in order, skip any that isn't
    configured, move to the next on any `LLMProviderError`. The order
    itself comes from `settings.ai_mode` (see `_resolve_provider_order`):
      "cloud"  -> claude, openai, gemini only
      "local"  -> ollama, vllm only
      "hybrid" -> ollama, vllm, then claude, openai, gemini — "if local
                  available use local, otherwise cloud". A local provider
                  only counts as unavailable once it actually fails (not
                  configured, or a real connection/HTTP error), which is
                  exactly what the try/skip loop below already does.
    `settings.ai_provider_priority` is an escape hatch: set it to
    anything other than "auto" to override this entirely with an explicit
    comma-separated order.
  - Redis response caching (via `cache.py`), keyed on a caller-supplied
    payload so identical requests across findings/workers/restarts are
    only ever sent to a provider once.
  - Streaming (`.stream()`): same provider order and fallback semantics,
    but fallback only applies before the first chunk of a given provider's
    response — see its docstring below for why.

`.complete()` returns `None` (not an exception) when every configured
provider fails or none are configured — callers are expected to have a
deterministic template fallback for that case, same as the rest of
NOVA's design.
"""

from typing import Iterator, Optional

import structlog

from app.config import get_settings
from app.services.ai import cache
from app.services.ai.base import BaseLLM, LLMProviderError, LLMResponse
from app.services.ai.providers.claude_provider import ClaudeProvider
from app.services.ai.providers.gemini_provider import GeminiProvider
from app.services.ai.providers.ollama_provider import OllamaProvider
from app.services.ai.providers.openai_provider import OpenAIProvider
from app.services.ai.providers.vllm_provider import VLLMProvider

logger = structlog.get_logger(__name__)
settings = get_settings()

_PROVIDER_CLASSES: dict[str, type[BaseLLM]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
    "vllm": VLLMProvider,
}

CLOUD_PROVIDER_NAMES = ("claude", "openai", "gemini")
LOCAL_PROVIDER_NAMES = ("ollama", "vllm")


def _resolve_provider_order() -> list[str]:
    override = settings.ai_provider_priority.strip().lower()
    if override and override != "auto":
        return [p.strip() for p in override.split(",") if p.strip()]

    mode = settings.ai_mode.strip().lower()
    if mode == "cloud":
        return list(CLOUD_PROVIDER_NAMES)
    if mode == "local":
        return list(LOCAL_PROVIDER_NAMES)
    if mode != "hybrid":
        logger.warning("ai_gateway.unknown_ai_mode", ai_mode=settings.ai_mode, falling_back_to="hybrid")
    return list(LOCAL_PROVIDER_NAMES) + list(CLOUD_PROVIDER_NAMES)


class LLMGateway:
    def __init__(self) -> None:
        self._providers: list[BaseLLM] = []
        for name in _resolve_provider_order():
            provider_cls = _PROVIDER_CLASSES.get(name)
            if provider_cls is None:
                logger.warning("ai_gateway.unknown_provider_in_priority", provider=name)
                continue
            self._providers.append(provider_cls())

    def complete(
        self,
        *,
        function_name: str,
        system: str,
        prompt: str,
        cache_payload: dict,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        use_cache: bool = True,
    ) -> Optional[LLMResponse]:
        """
        Returns the first successful provider response, or None if no
        provider is configured or all configured providers failed.
        """
        if use_cache:
            cached = cache.get_cached(function_name, cache_payload)
            if cached is not None:
                return LLMResponse(**cached)

        last_error: Optional[Exception] = None
        attempted = False
        for provider in self._providers:
            if not provider.is_configured():
                continue
            attempted = True
            try:
                response = provider.complete(
                    system=system,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except LLMProviderError as exc:
                last_error = exc
                logger.warning(
                    "ai_gateway.provider_failed",
                    provider=provider.name,
                    function=function_name,
                    error=str(exc),
                )
                continue

            if use_cache:
                cache.set_cached(
                    function_name,
                    cache_payload,
                    {"text": response.text, "provider": response.provider, "model": response.model},
                    ttl_seconds=settings.ai_cache_ttl_seconds,
                )
            return response

        if not attempted:
            logger.info("ai_gateway.no_provider_configured", function=function_name)
        else:
            logger.warning(
                "ai_gateway.all_providers_failed",
                function=function_name,
                error=str(last_error) if last_error else "unknown",
            )
        return None

    def stream(
        self,
        *,
        function_name: str,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Optional[Iterator[tuple[str, str]]]:
        """
        Yields (provider_name, chunk_text) pairs from the first provider
        that starts responding. Returns None if no provider is configured
        or every configured provider fails before producing a single chunk.

        Fallback is only possible up to that first chunk: each candidate
        provider's stream is "peeked" (its first chunk is pulled) before
        this method commits to it. A `LLMProviderError` raised by that
        peek — connection refused, auth failure, timeout — moves on to
        the next provider exactly like `.complete()` does. This is what
        makes hybrid mode's "if local available use local, otherwise
        cloud" work for streaming too: an unreachable local Ollama/vLLM
        server fails the peek and falls through to cloud before the
        caller has received any output at all.

        Once a provider's first chunk has been yielded, the remaining
        chunks are handed to the caller directly, uncaught — a failure
        mid-stream cannot be un-sent, so it propagates as-is rather than
        silently switching providers partway through a response.
        """
        last_error: Optional[Exception] = None
        attempted = False

        for provider in self._providers:
            if not provider.is_configured():
                continue
            attempted = True
            try:
                chunk_iter = provider.stream(
                    system=system,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                first_chunk = next(chunk_iter)
            except StopIteration:
                logger.warning("ai_gateway.stream_empty", provider=provider.name, function=function_name)
                continue
            except LLMProviderError as exc:
                last_error = exc
                logger.warning(
                    "ai_gateway.stream_provider_failed",
                    provider=provider.name,
                    function=function_name,
                    error=str(exc),
                )
                continue

            provider_name = provider.name

            def _generator(first=first_chunk, rest=chunk_iter, name=provider_name):
                yield name, first
                for chunk in rest:
                    yield name, chunk

            return _generator()

        if not attempted:
            logger.info("ai_gateway.no_provider_configured", function=function_name)
        else:
            logger.warning(
                "ai_gateway.all_providers_failed_stream",
                function=function_name,
                error=str(last_error) if last_error else "unknown",
            )
        return None


_gateway: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
