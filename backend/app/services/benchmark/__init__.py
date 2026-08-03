"""
NOVA — RAG Benchmark (Milestone 5)
Unrelated to the pre-existing "5-tier benchmark suite"
(docs/benchmark_suite_spec.md, app/utils/payload_generator.py) — that's
synthetic-repo fixtures for scanner-accuracy regression testing. This is
a live RAG-performance smoke test: embed/search/rerank/(LLM) timings
against the knowledge base as it exists right now, triggered on demand
rather than scheduled — see benchmark_service.py.
"""
