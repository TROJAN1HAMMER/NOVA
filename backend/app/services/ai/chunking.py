"""
NOVA — Token-Bounded Chunking

Splits a list of items into groups that fit within a token budget, so a
batch AI request (e.g. explaining many findings in one call instead of
one call per finding) never exceeds a provider's context window. Generic
over any renderable item via `render_fn` — currently used for
`SanitizedFinding` batches in ai_engine.py's batch explanation path.
"""

from typing import Callable, TypeVar

from app.services.ai.token_estimator import estimate_tokens

T = TypeVar("T")

DEFAULT_MAX_TOKENS_PER_CHUNK = 3000
PER_ITEM_OVERHEAD_TOKENS = 20  # JSON braces/keys/field labels surrounding each rendered item


def chunk_by_tokens(
    items: list[T],
    render_fn: Callable[[T], str],
    *,
    max_tokens_per_chunk: int = DEFAULT_MAX_TOKENS_PER_CHUNK,
) -> list[list[T]]:
    """
    Greedy bin-packing in input order (not size-optimal, but preserves the
    caller's ordering, which matters for indexing results back to findings).
    A single item that alone exceeds the budget still gets its own chunk
    rather than being dropped.
    """
    if not items:
        return []

    chunks: list[list[T]] = []
    current: list[T] = []
    current_tokens = 0

    for item in items:
        item_tokens = estimate_tokens(render_fn(item)) + PER_ITEM_OVERHEAD_TOKENS
        if current and current_tokens + item_tokens > max_tokens_per_chunk:
            chunks.append(current)
            current, current_tokens = [], 0
        current.append(item)
        current_tokens += item_tokens

    if current:
        chunks.append(current)

    return chunks
