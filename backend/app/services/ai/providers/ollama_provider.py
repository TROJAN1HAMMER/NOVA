import json
from typing import Iterator

import httpx

from app.config import get_settings
from app.services.ai.base import BaseLLM, LLMProviderError, LLMResponse
from app.services.ai.local_models import warn_if_unknown_ollama_model

settings = get_settings()


class OllamaProvider(BaseLLM):
    """
    Talks to a local/self-hosted Ollama server (`ollama serve`) via its
    native /api/chat endpoint. Validated against Llama 3, Mistral, Phi-3,
    and Mixtral (`ollama pull llama3|mistral|phi3|mixtral`); any other
    pulled tag is accepted as-is.
    """

    name = "ollama"

    def __init__(self) -> None:
        if settings.ollama_model:
            warn_if_unknown_ollama_model(settings.ollama_model)

    def is_configured(self) -> bool:
        # Requires an explicit model name — no sensible default to guess
        # for whatever the operator has pulled locally.
        return bool(settings.ollama_model)

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        body = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                    json=body,
                )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            if not text:
                raise LLMProviderError(f"{self.name}: empty response text")
            return LLMResponse(text=text.strip(), provider=self.name, model=settings.ollama_model)
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name}: HTTP error: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise LLMProviderError(f"{self.name}: unexpected response shape: {exc}") from exc

    def stream(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Iterator[str]:
        """
        Ollama's /api/chat streams newline-delimited JSON objects (not SSE)
        when "stream" is true — each line is a complete object with an
        incremental `message.content` fragment, and a final line carrying
        `"done": true`.
        """
        body = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream(
                    "POST",
                    f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                    json=body,
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        content = chunk.get("message", {}).get("content")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name}: streaming HTTP error: {exc}") from exc
