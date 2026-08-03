from typing import Iterator

from app.config import get_settings
from app.services.ai.base import BaseLLM, LLMResponse
from app.services.ai.local_models import warn_if_unknown_vllm_model
from app.services.ai.providers._openai_compatible import call_chat_completions, stream_chat_completions

settings = get_settings()


class VLLMProvider(BaseLLM):
    """
    Talks to a self-hosted vLLM server running in OpenAI-compatible mode
    (`vllm serve <model> --api-key ...` or unauthenticated). No API key is
    required by default — vLLM deployments are typically inside a private
    network — but one is sent if configured. Validated against Llama 3,
    Mistral, Phi-3, and Mixtral (see `local_models.py`); any other
    vLLM-servable HF repo is accepted as-is.
    """

    name = "vllm"

    def __init__(self) -> None:
        if settings.vllm_model:
            warn_if_unknown_vllm_model(settings.vllm_model)

    def is_configured(self) -> bool:
        # Requires an explicit served-model name: unlike hosted providers
        # there's no sensible default model to guess for a self-hosted server.
        return bool(settings.vllm_model)

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        return call_chat_completions(
            base_url=settings.vllm_base_url,
            model=settings.vllm_model,
            provider_name=self.name,
            system=system,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key="",
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
            base_url=settings.vllm_base_url,
            model=settings.vllm_model,
            provider_name=self.name,
            system=system,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key="",
        )
