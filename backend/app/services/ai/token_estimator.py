"""
NOVA — Token Estimation

A deterministic, dependency-free heuristic (~4 characters per token, the
commonly-cited average for English prose across GPT/Claude/Gemini
tokenizers) rather than a real tokenizer. Exact counts differ per
provider and per model; this is intentionally an estimate used only for
two purposes where an exact count isn't needed:
  - deciding when a batch of findings needs to be split into multiple
    provider calls (chunking.py)
  - rejecting a pathologically oversized prompt before it's sent
    (middleware.py's token budget guard)

If precise accounting ever matters (e.g. for cost billing), swap this for
a real tokenizer at the two call sites below — nothing else depends on
the heuristic being exact.
"""

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_request_tokens(system: str, prompt: str) -> int:
    return estimate_tokens(system) + estimate_tokens(prompt)


def exceeds_budget(system: str, prompt: str, *, max_tokens: int) -> bool:
    return estimate_request_tokens(system, prompt) > max_tokens
