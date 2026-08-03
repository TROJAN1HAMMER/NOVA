import json
from typing import Iterator

import httpx

from app.config import get_settings
from app.services.ai.base import BaseLLM, LLMProviderError, LLMResponse

settings = get_settings()

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class ClaudeProvider(BaseLLM):
    name = "claude"

    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.anthropic_model,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(_API_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            blocks = data.get("content", [])
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            if not text:
                raise LLMProviderError(f"{self.name}: empty response text")
            return LLMResponse(text=text.strip(), provider=self.name, model=settings.anthropic_model)
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
        Anthropic's streaming format is SSE with typed events
        (`message_start`, `content_block_delta`, `message_stop`, ...); only
        `content_block_delta` events carrying a `text_delta` contain
        content to forward.
        """
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.anthropic_model,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                with client.stream("POST", _API_URL, headers=headers, json=body) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[len("data:"):].strip()
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta" and delta.get("text"):
                                yield delta["text"]
                        elif event.get("type") == "message_stop":
                            break
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name}: streaming HTTP error: {exc}") from exc
