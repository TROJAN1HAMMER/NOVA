"""
NOVA — LLM Provider Interface

`BaseLLM` is the only contract a provider may implement. Nothing outside
`app/services/ai/providers/` and `app/services/ai/gateway.py` should ever
import a provider class directly — see `gateway.py` for the enforced single
call site the rest of NOVA is expected to use instead.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


class LLMProviderError(Exception):
    """
    Raised by a provider for any failure — network, auth, rate limit,
    unexpected response shape. Always caught by LLMGateway, which moves on
    to the next provider in the fallback chain; never expected to reach a
    caller outside `app/services/ai/`.
    """


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str


class BaseLLM(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Whether this provider has what it needs to be worth attempting at
        all (an API key, or a served-model name for self-hosted backends).
        Checked before every call so an unconfigured provider is skipped
        for free rather than attempted and failed.
        """

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Raises LLMProviderError on any failure. Never returns partial/empty text silently."""

    @abstractmethod
    def stream(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Iterator[str]:
        """
        Yields text chunks as they arrive from the provider.

        Raises LLMProviderError if the request/connection itself fails
        before any chunk has been produced — the gateway relies on this to
        decide whether it's still safe to fall back to the next provider
        (see `gateway.py`'s `stream()`: it forces the first chunk before
        committing to a provider for the rest of the caller's iteration).
        Once at least one chunk has been yielded, a failure on a later
        chunk propagates to the caller as-is; there is no way to "undo" the
        chunks already forwarded, so provider fallback cannot apply mid-stream.
        """
