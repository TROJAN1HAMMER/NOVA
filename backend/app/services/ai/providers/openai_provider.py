from typing import Iterator

from app.config import get_settings
from app.services.ai.base import BaseLLM, LLMResponse
from app.services.ai.providers._openai_compatible import call_chat_completions, stream_chat_completions

settings = get_settings()


class OpenAIProvider(BaseLLM):
    name = "openai"

    def is_configured(self) -> bool:
        return bool(settings.openai_api_key)

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        return call_chat_completions(
            base_url="https://api.openai.com",
            model=settings.openai_model,
            provider_name=self.name,
            system=system,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )

    def stream(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Iterator[str]:
        return stream_chat_completions(
            base_url="https://api.openai.com",
            model=settings.openai_model,
            provider_name=self.name,
            system=system,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )
