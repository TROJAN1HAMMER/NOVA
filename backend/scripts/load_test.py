"""
NOVA — RAG Load Test Script (Milestone 5)

Fires concurrent requests at a chosen RAG endpoint and reports latency
percentiles + error/rate-limit counts. Standalone tooling, not a
persistent feature — see docs/production_hardening.md for how to run
this and how to interpret the numbers it prints.

Usage (from inside the api container, or anywhere with network access to
the API and httpx installed):

    python scripts/load_test.py --endpoint search --concurrency 10 --total 100
    python scripts/load_test.py --endpoint chat --concurrency 5 --total 20
    python scripts/load_test.py --endpoint search --single-user --total 50   # exercises the per-user rate limiter

Round-robins across a fixed pool of demo accounts by default so
concurrent load isn't artificially throttled by the per-user rate
limiter (app/middleware/rate_limit.py's `require_rate_limit`) before the
underlying pipeline's real capacity is even reached — pass --single-user
to deliberately test the limiter itself instead.
"""

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field

import httpx

DEFAULT_BASE_URL = "http://localhost:8000/api/v1"

# Any already-provisioned demo account works — see the NOVA RAG
# milestone walkthroughs for how these were created.
DEMO_ACCOUNTS = [
    ("demo-analyst@NOVA.example", "NOVADemo123!"),
    ("demo-manager@NOVA.example", "NOVADemo123!"),
    ("demo-executive@NOVA.example", "NOVADemo123!"),
]

ENDPOINTS = {
    "search": {
        "method": "POST",
        "path": "/knowledge/search",
        "body": lambda i: {"query": f"password rotation policy {i}", "top_k": 5},
    },
    "chat": {
        "method": "POST",
        "path": "/assistant/chat",
        "body": lambda i: {"message": f"What are our biggest risks? (run {i})", "history": []},
        "streaming": True,
    },
    "executive_ask": {
        "method": "POST",
        "path": "/executive-intelligence/ask",
        "body": lambda i: {"question": f"What changed this week? (run {i})", "history": []},
        "streaming": True,
    },
}


@dataclass
class RunResult:
    latencies_ms: list[float] = field(default_factory=list)
    status_counts: dict[int, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


async def _login(client: httpx.AsyncClient, base_url: str, email: str, password: str) -> str:
    response = await client.post(f"{base_url}/auth/login", data={"username": email, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


async def _one_request(
    client: httpx.AsyncClient, base_url: str, token: str, endpoint: dict, index: int, result: RunResult
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    body = endpoint["body"](index)
    start = time.monotonic()
    try:
        if endpoint.get("streaming"):
            async with client.stream(
                endpoint["method"], f"{base_url}{endpoint['path']}", json=body, headers=headers, timeout=60
            ) as response:
                async for _ in response.aiter_bytes():
                    pass
                status = response.status_code
        else:
            response = await client.request(
                endpoint["method"], f"{base_url}{endpoint['path']}", json=body, headers=headers, timeout=30
            )
            status = response.status_code
    except Exception as exc:
        result.errors.append(str(exc))
        return
    elapsed_ms = (time.monotonic() - start) * 1000
    result.latencies_ms.append(elapsed_ms)
    result.status_counts[status] = result.status_counts.get(status, 0) + 1


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(len(ordered) * pct), len(ordered) - 1)
    return ordered[index]


async def main() -> None:
    parser = argparse.ArgumentParser(description="NOVA RAG load test")
    parser.add_argument("--endpoint", choices=ENDPOINTS.keys(), default="search")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--total", type=int, default=50)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--single-user", action="store_true", help="Use one account for every request (tests rate limiting)")
    args = parser.parse_args()

    endpoint = ENDPOINTS[args.endpoint]
    result = RunResult()

    async with httpx.AsyncClient() as client:
        accounts = [DEMO_ACCOUNTS[0]] if args.single_user else DEMO_ACCOUNTS
        tokens = [await _login(client, args.base_url, email, password) for email, password in accounts]

        semaphore = asyncio.Semaphore(args.concurrency)

        async def _bounded(i: int) -> None:
            async with semaphore:
                token = tokens[i % len(tokens)]
                await _one_request(client, args.base_url, token, endpoint, i, result)

        overall_start = time.monotonic()
        await asyncio.gather(*(_bounded(i) for i in range(args.total)))
        overall_elapsed = time.monotonic() - overall_start

    print(f"\n=== NOVA RAG Load Test: {args.endpoint} ===")
    print(f"Total requests: {args.total}, concurrency: {args.concurrency}, accounts used: {len(tokens)}")
    print(f"Wall-clock time: {overall_elapsed:.2f}s ({args.total / overall_elapsed:.1f} req/s)")
    print(f"Status counts: {result.status_counts}")
    if result.errors:
        print(f"Errors ({len(result.errors)}): {result.errors[:3]}{'...' if len(result.errors) > 3 else ''}")
    if result.latencies_ms:
        print(
            f"Latency (successful requests, ms): "
            f"min={min(result.latencies_ms):.0f} "
            f"p50={_percentile(result.latencies_ms, 0.5):.0f} "
            f"p95={_percentile(result.latencies_ms, 0.95):.0f} "
            f"p99={_percentile(result.latencies_ms, 0.99):.0f} "
            f"max={max(result.latencies_ms):.0f} "
            f"mean={statistics.mean(result.latencies_ms):.0f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
