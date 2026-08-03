"""
Shared request/response handling for any provider that speaks OpenAI's
`/v1/chat/completions` wire format — that's OpenAI itself, and also vLLM's
OpenAI-compatible server mode. Kept as a plain function (not a base class)
since the only thing that differs between the two callers is base_url,
auth header, and default model.
"""

import json
from typing import Iterator

import httpx

from app.services.ai.base import LLMProviderError, LLMResponse


def call_chat_completions(
    *,
    base_url: str,
    model: str,
    provider_name: str,
    system: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    api_key: str = "",
    timeout_seconds: float = 30.0,
) -> LLMResponse:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json=body,
            )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        if not text:
            raise LLMProviderError(f"{provider_name}: empty response text")
        return LLMResponse(text=text.strip(), provider=provider_name, model=model)
    except httpx.HTTPError as exc:
        raise LLMProviderError(f"{provider_name}: HTTP error: {exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMProviderError(f"{provider_name}: unexpected response shape: {exc}") from exc


def stream_chat_completions(
    *,
    base_url: str,
    model: str,
    provider_name: str,
    system: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    api_key: str = "",
    timeout_seconds: float = 60.0,
) -> Iterator[str]:
    """
    Yields content deltas from an SSE `text/event-stream` response
    (`data: {...}` lines, terminated by `data: [DONE]`). Nothing in this
    generator's body runs until the caller's first `next()` — so a
    connection/auth failure surfaces as LLMProviderError on that first
    call, before any text has been yielded, which is what lets
    `gateway.py`'s `stream()` still fall back to another provider.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/v1/chat/completions",
                headers=headers,
                json=body,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or [{}]
                    content = choices[0].get("delta", {}).get("content")
                    if content:
                        yield content
    except httpx.HTTPError as exc:
        raise LLMProviderError(f"{provider_name}: streaming HTTP error: {exc}") from exc
