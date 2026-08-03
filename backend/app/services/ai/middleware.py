"""
NOVA — Intelligent AI Request Middleware

The single enforced choke point between `ai_engine.py` (the service layer
that builds prompts) and `gateway.py` (provider fallback). Nothing else in
NOVA is expected to call `gateway.get_gateway().complete()` directly —
mirroring how `gateway.py` is the only module allowed to import a provider.

Responsibilities, in order, each one independently optional-to-skip via
its own failure mode (never blocks the pipeline on AI infrastructure):

  1. Policy enforcement — "AI only for explanation, remediation, and
     summaries; everything else deterministic". `function_name` must be
     in `ALLOWED_FUNCTIONS`; anything else is a programming error, not a
     runtime condition, so it raises rather than silently proceeding.
  2. Token budget guard — defense in depth on top of the sanitizer:
     truncates a pathologically large prompt rather than sending it.
  3. Semantic cache lookup (coarse — category/severity/CVE signature).
  4. Duplicate-request detection — if a concurrent caller already holds
     the claim for this exact signature, poll briefly for its result
     (response reuse) instead of firing a second identical provider call.
  5. Dispatch via `LLMGateway.complete()`, which itself applies the exact-
     match prompt cache and the provider fallback chain (ending in local
     Ollama/vLLM before giving up — "local LLM fallback" is this chain's
     default ordering, see `app/config.py`'s `ai_provider_priority`).
  6. Populate the semantic cache on success; always release the claim.

Returns `None` on total failure, same contract as `LLMGateway.complete()` —
callers keep their existing deterministic-template fallback.
"""

from typing import Iterator, Optional

import structlog

from app.config import get_settings
from app.services.ai import request_lock, semantic_cache
from app.services.ai.base import LLMResponse
from app.services.ai.gateway import get_gateway
from app.services.ai.token_estimator import estimate_request_tokens

logger = structlog.get_logger(__name__)
settings = get_settings()

ALLOWED_FUNCTIONS = frozenset(
    {
        "explain_vulnerability",
        "explain_vulnerability_stream",
        "explain_vulnerabilities_batch",
        "suggest_remediation",
        "generate_executive_summary",
        "generate_risk_explanation",
    }
)

MAX_PROMPT_TOKENS = 6000


def _truncate_to_budget(prompt: str, system: str, *, max_tokens: int) -> str:
    from app.services.ai.token_estimator import CHARS_PER_TOKEN

    budget_chars = max(0, (max_tokens - estimate_request_tokens(system, "")) * CHARS_PER_TOKEN)
    if len(prompt) <= budget_chars:
        return prompt
    logger.warning(
        "ai_middleware.prompt_truncated",
        original_chars=len(prompt),
        budget_chars=budget_chars,
    )
    return prompt[:budget_chars]


class AIRequestMiddleware:
    def dispatch(
        self,
        *,
        function_name: str,
        system: str,
        prompt: str,
        semantic_tokens: Optional[tuple[str, ...]] = None,
        cache_payload: Optional[dict] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Optional[LLMResponse]:
        if function_name not in ALLOWED_FUNCTIONS:
            raise ValueError(
                f"ai_middleware: '{function_name}' is not an allowed AI function. "
                f"AI is only used for explanation, remediation, and summaries — "
                f"everything else in NOVA must be deterministic."
            )

        prompt = _truncate_to_budget(prompt, system, max_tokens=MAX_PROMPT_TOKENS)

        sem_key = None
        if semantic_tokens is not None:
            sem_key = semantic_cache.semantic_key(function_name, semantic_tokens)
            cached = semantic_cache.get_cached(sem_key)
            if cached is not None:
                logger.debug("ai_middleware.semantic_cache_hit", function=function_name)
                return LLMResponse(**cached)

        acquired_lock = False
        if sem_key is not None:
            acquired_lock = request_lock.try_acquire(sem_key)
            if not acquired_lock:
                reused = request_lock.wait_for_result(lambda: semantic_cache.get_cached(sem_key))
                if reused is not None:
                    logger.debug("ai_middleware.reused_concurrent_response", function=function_name)
                    return LLMResponse(**reused)
                # Lock holder hasn't produced a result within the poll window —
                # proceed with our own call rather than blocking further.

        try:
            response = get_gateway().complete(
                function_name=function_name,
                system=system,
                prompt=prompt,
                cache_payload=cache_payload or {"semantic_tokens": semantic_tokens},
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if response is not None and sem_key is not None:
                semantic_cache.set_cached(
                    sem_key,
                    {"text": response.text, "provider": response.provider, "model": response.model},
                    ttl_seconds=settings.ai_cache_ttl_seconds,
                )
            return response
        finally:
            if acquired_lock:
                request_lock.release(sem_key)

    def dispatch_stream(
        self,
        *,
        function_name: str,
        system: str,
        prompt: str,
        semantic_tokens: Optional[tuple[str, ...]] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Optional[Iterator[str]]:
        """
        Streaming counterpart to `dispatch()`. Same policy allow-list,
        token guard, and semantic cache as `dispatch()`, with two
        deliberate simplifications for streaming's different shape:

          - A semantic cache hit is replayed as a single chunk rather than
            incrementally — there's nothing to stream, the answer is
            already fully known. Still satisfies "streaming interface",
            just not "streaming latency" for a cache hit, which is exactly
            the point of caching.
          - No duplicate-request lock: streaming calls are expected to be
            one-per-interactive-request (e.g. a single browser tab
            watching one finding), not the high-fan-out Celery batch
            pipeline `explain_vulnerabilities_batch` exists for — so the
            concurrent-duplicate problem the lock solves barely arises
            here, and skipping it keeps first-byte latency lower.

        The full assembled response is cached under the *same* semantic
        key on completion, so a later non-streaming call for the same
        signature (or a later streaming call) can reuse it.
        """
        if function_name not in ALLOWED_FUNCTIONS:
            raise ValueError(
                f"ai_middleware: '{function_name}' is not an allowed AI function. "
                f"AI is only used for explanation, remediation, and summaries — "
                f"everything else in NOVA must be deterministic."
            )

        prompt = _truncate_to_budget(prompt, system, max_tokens=MAX_PROMPT_TOKENS)

        sem_key = None
        if semantic_tokens is not None:
            sem_key = semantic_cache.semantic_key(function_name, semantic_tokens)
            cached = semantic_cache.get_cached(sem_key)
            if cached is not None:
                logger.debug("ai_middleware.stream_semantic_cache_hit", function=function_name)
                return iter([cached["text"]])

        gw_stream = get_gateway().stream(
            function_name=function_name,
            system=system,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if gw_stream is None:
            return None

        def _accumulate_and_cache() -> Iterator[str]:
            parts: list[str] = []
            provider_name = "unknown"
            for name, chunk in gw_stream:
                provider_name = name
                parts.append(chunk)
                yield chunk
            if sem_key is not None and parts:
                semantic_cache.set_cached(
                    sem_key,
                    # No per-chunk model identifier is tracked by
                    # gateway.stream() — "model" is left blank rather than
                    # guessed; LLMResponse(**cached) tolerates an empty
                    # string fine if a non-streaming caller later reads
                    # this same entry back.
                    {"text": "".join(parts), "provider": provider_name, "model": ""},
                    ttl_seconds=settings.ai_cache_ttl_seconds,
                )

        return _accumulate_and_cache()


_middleware: Optional[AIRequestMiddleware] = None


def get_middleware() -> AIRequestMiddleware:
    global _middleware
    if _middleware is None:
        _middleware = AIRequestMiddleware()
    return _middleware
