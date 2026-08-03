# NOVA Frontend — Enterprise React Single-Page Application

The frontend user interface for **NOVA (Neural Orchestrated Vector Assistant)**, built with React 19, TypeScript, TailwindCSS v4, and Vite.

## Architectural Overview

The UI provides a modern, dark-themed, glassmorphic experience for interacting with the **AEKOF (Adaptive Enterprise Knowledge Operating Framework)**:

- **Adaptive AI Assistant (`/assistant`)**: Dynamic streaming chat panel with citation links, consensus confidence scores, and explainable evidence maps.
- **Source Studio (`/source-studio`)**: Multi-source knowledge ingestion (PDF, DOCX, TXT, Markdown, Git repos, Web crawling, local folders, ZIPs).
- **Knowledge Base (`/knowledge`)**: Corpus management, chunk viewer, indexing status monitoring, and tag-based metadata filtering.
- **Graph Explorer (`/graph-explorer`)**: Interactive entity-relationship visualization powered by GraphRAG metadata.
- **Memory Engine (`/memory`)**: Enterprise context memory management, session recall, and user preference state inspection.
- **Knowledge Evolution (`/knowledge-evolution`)**: Dynamic consensus tracking, automated contradiction detection, and decay policy controls.
- **Benchmark Engine (`/benchmarks`)**: Empirical evaluation suite comparing retrieval strategies (Vanilla RAG, Dense, Sparse, Hybrid, GraphRAG, Adaptive, HyDE, MemoRAG, LongRAG, LightRAG).
- **Executive Intelligence (`/executive`)**: High-level portfolio confidence metrics, document volume trends, and automated executive report generation.
- **RAG Studio (`/rag-operations`)**: Fine-grained configuration for chunking sizes, embedding models, vector distance metrics, and hybrid search weighting.

## Development Setup

```bash
# 1. Install dependencies
npm install

# 2. Start the Vite development server
npm run dev

# 3. Build production bundle
npm run build
```

## Environment Variables

Configuration is handled via `.env` (or inherited from Vite env defaults):

| Variable | Description | Default |
| --- | --- | --- |
| `VITE_API_URL` | Base URL of the backend API endpoints | `http://localhost:8000/api/v1` |
