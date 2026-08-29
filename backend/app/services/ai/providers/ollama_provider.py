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

    def _get_model_name(self) -> str:
        s = get_settings()
        if s.ollama_model:
            return s.ollama_model
        return "llama3.2:3b"

    def is_configured(self) -> bool:
        s = get_settings()
        if s.ollama_model:
            return True
        # Probe local Ollama service availability as fallback
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{s.ollama_base_url.rstrip('/')}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        s = get_settings()
        model_name = self._get_model_name()
        body = {
            "model": model_name,
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
                    f"{s.ollama_base_url.rstrip('/')}/api/chat",
                    json=body,
                )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            if not text:
                raise LLMProviderError(f"{self.name}: empty response text")
            return LLMResponse(text=text.strip(), provider=self.name, model=model_name)
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
        s = get_settings()
        model_name = self._get_model_name()
        body = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        tokens = []
        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream(
                    "POST",
                    f"{s.ollama_base_url.rstrip('/')}/api/chat",
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
                            tokens.append(content)
                            yield content
                        if chunk.get("done"):
                            break
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self.name}: streaming HTTP error: {exc}") from exc

        full_streamed = "".join(tokens).strip()
        if len(full_streamed) <= 5:
            try:
                res = self.complete(system=system, prompt=prompt, max_tokens=max_tokens, temperature=temperature)
                if res.text and len(res.text) > len(full_streamed):
                    yield "\n" + res.text
            except Exception:
                pass
