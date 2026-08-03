import json
from typing import Iterator

import httpx

from app.config import get_settings
from app.services.ai.base import BaseLLM, LLMProviderError, LLMResponse

settings = get_settings()

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(BaseLLM):
    """
    Calls the Generative Language REST API directly rather than depending
    on the `google-generativeai` SDK, so this provider needs nothing beyond
    the `httpx` dependency every other provider already uses.
    """

    name = "gemini"

    def is_configured(self) -> bool:
        return bool(settings.gemini_api_key) and "your-gemini" not in settings.gemini_api_key.lower()

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        url = f"{_API_BASE}/{settings.gemini_model}:generateContent"
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    url,
                    params={"key": settings.gemini_api_key},
                    json=body,
                )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMProviderError(f"{self.name}: no candidates in response")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            if not text:
                raise LLMProviderError(f"{self.name}: empty response text")
            return LLMResponse(text=text.strip(), provider=self.name, model=settings.gemini_model)
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name}: HTTP error: {exc}") from exc
        except (KeyError, IndexError, ValueError) as exc:
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
        `:streamGenerateContent?alt=sse` returns real SSE (without
        `alt=sse` it instead returns one giant JSON array over a chunked
        response, which isn't incrementally parseable) — each `data:`
        frame is a full candidate-shaped chunk carrying the next fragment
        of text.
        """
        url = f"{_API_BASE}/{settings.gemini_model}:streamGenerateContent"
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                with client.stream(
                    "POST",
                    url,
                    params={"key": settings.gemini_api_key, "alt": "sse"},
                    json=body,
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[len("data:"):].strip()
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        candidates = chunk.get("candidates") or []
                        if not candidates:
                            continue
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)
                        if text:
                            yield text
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name}: streaming HTTP error: {exc}") from exc
