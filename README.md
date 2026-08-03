# NOVA

> **Neural Orchestrated Vector Assistant**  
> *Powered by **AEKOF** (Adaptive Enterprise Knowledge Operating Framework)*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🌟 Overview

**NOVA** (Neural Orchestrated Vector Assistant) is a next-generation, production-ready enterprise AI knowledge operating platform. Engineered on top of the **AEKOF** framework, NOVA solves the fundamental limitations of traditional Retrieval-Augmented Generation (RAG) systems—such as retrieval hallucinations, static chunking boundaries, loss of global graph context, lack of temporal memory, and uncalibrated model outputs.

NOVA combines state-of-the-art retrieval mechanisms into a unified, self-healing knowledge ecosystem:

- 🧠 **Adaptive RAG**: Dynamic strategy routing tailored to user query intent and complexity.
- 🕸️ **GraphRAG**: Entity-relationship knowledge extraction for multi-hop global context reasoning.
- 💾 **Enterprise Memory**: Context-aware temporal memory across sessions and workspace entities.
- 🔄 **Knowledge Evolution**: Automated contradiction detection, dynamic consensus scoring, and decay policies.
- 🔍 **Explainable AI**: Granular evidence citation trees, retrieval score breakdowns, and transparent context lineage.
- 🎯 **Confidence Calibration**: Sigmoid-calibrated retrieval confidence gates to prevent hallucinated answers.
- 🌐 **Multi-Source Evidence Retrieval**: Multi-modal document ingestion spanning PDFs, DOCX, repositories, web crawling, and databases.
- 🛡️ **Self-Healing Knowledge Base**: Automated gap identification, FAQ rule matching, and fallback orchestration.
- 📊 **Research Benchmarking**: Built-in empirical benchmarking comparing 10+ retrieval paradigms against production workloads.

---

## ✨ Key Features

| Feature Module | Description |
| --- | --- |
| 🎯 **Adaptive Knowledge Planner** | Analyzes query intent, intent classification, and query complexity to select optimal retrieval routes dynamically. |
| 🌐 **Multi-Source Ingestion** | Ingests PDFs, Word docs, raw text, Markdown, Git repositories, ZIP archives, and live URL web crawling. |
| 🕸️ **GraphRAG Engine** | Builds knowledge graph triples (entity-relation-entity) for global conceptual synthesis across documents. |
| 💾 **Enterprise Memory** | Tracks user preferences, persistent session contexts, and entity states across multiple interactions. |
| 📐 **Confidence Calibration** | Employs mathematical calibration models (Platt scaling & cross-encoder alignment) to gate responses reliably. |
| 🔄 **Knowledge Evolution** | Monitors document freshness, resolves conflicting knowledge statements, and enforces decay policies. |
| 🔍 **Explainable Retrieval** | Renders exact chunk lineage, similarity scores, source documents, and cross-encoder rerank evidence. |
| 📈 **Executive Intelligence** | Provides high-level portfolio confidence metrics, aggregate knowledge health, and automated PDF export reports. |
| ⚙️ **RAG Studio** | Interactive playground to tweak vector weights, chunk overlap, top-K params, and reranking parameters live. |
| 🔬 **Benchmark Engine** | Evaluates retrieval strategies against synthetic and empirical benchmark query suites. |
| 🩺 **Knowledge Health** | Continuously audits orphaned vectors, low-confidence document clusters, and unindexed source material. |
| 📂 **Source Studio** | Drag-and-drop ingestion interface with live progress tracking, metadata tagging, and auto-chunking. |
| ⚡ **FastAPI Backend** | Asynchronous Python 3.11 backend with OpenAPI specifications, Pydantic validation, and JWT RBAC. |
| 💻 **React Frontend** | Modern, responsive glassmorphic UI built with React 19, Vite, TailwindCSS, and Lucide icons. |
| ⚙️ **Celery Workers** | Asynchronous background processing queue for long-running document ingestion, graph extraction, and benchmarks. |
| 🐘 **PostgreSQL + pgvector** | Enterprise relational storage coupled with native HNSW vector index acceleration. |

---

## 🏗️ Architecture

The **AEKOF** architecture follows a multi-tier, cascaded retrieval and consensus pipeline designed for maximum accuracy, context preservation, and explainability.

```
                  ┌────────────────────────┐
                  │       User Query       │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │   Knowledge Planner    │
                  └───────────┬────────────┘
                              │
                              ▼
          ┌────────────────────────────────────────┐
          │     Adaptive Retrieval Orchestrator    │
          └─┬──────────┬──────────┬──────────┬─────┘
            │          │          │          │
            ▼          ▼          ▼          ▼
         ┌─────┐   ┌───────┐  ┌───────┐  ┌──────────┐
         │ FAQ │   │ Dense │  │Sparse │  │ GraphRAG │
         └─────┘   └───────┘  └───────┘  └──────────┘
            │          │          │          │
            └──────────┴────┬─────┴──────────┘
                            │
                            ▼
               ┌────────────────────────┐
               │    Consensus Engine    │
               └────────────┬───────────┘
                            │
                            ▼
               ┌────────────────────────┐
               │ Confidence Calibration │
               └────────────┬───────────┘
                            │
                            ▼
               ┌────────────────────────┐
               │   LLM Generation / RAG │
               └────────────┬───────────┘
                            │
                            ▼
               ┌────────────────────────┐
               │  Explainable Response  │
               └────────────┬───────────┘
                            │
                            ▼
               ┌────────────────────────┐
               │  Knowledge Evolution   │
               └────────────────────────┘
```

---

## 🛠️ Technology Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+)
- **ORM & Database**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Async) + [PostgreSQL](https://www.postgresql.org/) with [pgvector](https://github.com/pgvector/pgvector)
- **Task Queue**: [Celery](https://docs.celeryq.dev/) + [Redis 7](https://redis.io/)
- **Embeddings & Reranking**: [FastEmbed](https://github.com/qdrant/fastembed) (`BAAI/bge-small-en-v1.5`), [SentenceTransformers](https://www.sbert.net/) (`Xenova/ms-marco-MiniLM-L-6-v2`)
- **Graph Processing**: Custom AEKOF GraphRAG Entity-Relation Extractor

### Frontend
- **Framework**: [React 19](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- **Build Tool**: [Vite](https://vitejs.dev/)
- **Styling**: [TailwindCSS v4](https://tailwindcss.com/)
- **State & Data Fetching**: [TanStack Query (React Query)](https://tanstack.com/query) + [Axios](https://axios-http.com/)
- **Visualization**: [Recharts](https://recharts.org/), [Lucide React](https://lucide.dev/), [Three.js](https://threejs.org/) / React Three Fiber

### Infrastructure & DevOps
- **Containers**: [Docker](https://www.docker.com/) & Docker Compose
- **Orchestration**: [Helm](https://helm.sh/) / Kubernetes
- **Web Server**: [Nginx](https://www.nginx.com/) (Reverse Proxy & Static SPA host)

---

## 📸 Screenshots

*(Visual documentation of the NOVA Platform Interface)*

- **Landing Page**: *Modern landing view highlighting AEKOF metrics and system capabilities.*
- **Assistant**: *Streaming interactive AI Assistant with live citation badges and evidence drawers.*
- **Knowledge Base**: *Document grid and tabular chunk inspector with vector status indicators.*
- **Source Studio**: *Drag-and-drop multi-source ingestion panel for file and repository indexing.*
- **Graph Explorer**: *Interactive 2D/3D force-directed knowledge graph visualization.*
- **Memory Engine**: *Session memory recall viewer and workspace context manager.*
- **Executive Dashboard**: *High-level portfolio confidence breakdown and system utilization.*
- **RAG Studio**: *Parameter tuning console for embedding models, chunk sizes, and top-K limits.*
- **Benchmarks**: *Performance evaluation suite across 10 RAG research techniques.*
- **Knowledge Evolution**: *Contradiction inbox, knowledge decay rules, and automated consensus tracking.*

---

## 📁 Project Structure

```
.
├── backend/
│   ├── alembic/              # Database migration scripts
│   ├── app/
│   │   ├── api/              # REST API v1 endpoints
│   │   ├── core/             # Security, JWT, config, database sessions
│   │   ├── models/           # SQLAlchemy ORM database schemas
│   │   ├── orchestrator/     # AEKOF adaptive retrieval orchestration
│   │   ├── schemas/          # Pydantic data validation schemas
│   │   ├── services/         # Core business logic (RAG, Graph, Memory, FAQ)
│   │   └── tasks/            # Celery asynchronous worker tasks
│   ├── celery_worker.py      # Celery task queue entrypoint
│   ├── Dockerfile            # Multi-stage production Python container
│   ├── docker-compose.yml    # Backend service stack
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable UI components & feature widgets
│   │   ├── hooks/            # Custom React hooks & query hooks
│   │   ├── lib/              # API clients, utils, RBAC permissions
│   │   ├── pages/            # View components (Assistant, Studio, Graph, etc.)
│   │   └── types/            # TypeScript interfaces & API type contracts
│   ├── Dockerfile            # Multi-stage Nginx container for SPA
│   ├── package.json          # Node dependencies & metadata
│   └── vite.config.ts        # Vite configuration
├── docker-compose.yml        # Top-level full-stack orchestrator
├── helm/                     # Kubernetes Helm deployment charts
├── k8s/                      # Kubernetes manifest templates
├── docs/                     # Platform architecture & API documentation
├── .gitignore                # Production ignore rules
├── CHANGELOG.md              # Project history & release milestones
├── LICENSE                   # MIT License
└── README.md                 # Canonical platform documentation
```

---

## ⚙️ Installation

### Prerequisites
- **Git**
- **Docker** & **Docker Compose** (recommended)
- *Or for manual setup*: **Python 3.11+**, **Node.js 20+**, **PostgreSQL 16** (with `pgvector`), **Redis 7**

### Quickstart with Docker Compose

```bash
# 1. Clone the repository
git clone https://github.com/TROJAN1HAMMER/NOVA.git
cd NOVA

# 2. Launch all services (PostgreSQL, Redis, Backend, Frontend, Celery Workers)
docker-compose up -d --build

# 3. Access the application
# Frontend UI: http://localhost:5173
# OpenAPI Docs: http://localhost:8000/docs
```

### Manual Local Development Setup

#### 1. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start FastAPI dev server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Celery Worker & Redis Setup
```bash
# Ensure Redis is running locally on port 6379
redis-server

# Start Celery worker in backend directory
celery -A celery_worker.celery_app worker --loglevel=info
```

#### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

---

## 🔧 Configuration

All backend settings are governed by Environment Variables (defined in `backend/.env` or `backend/app/config.py`):

| Variable | Default Value | Description |
| --- | --- | --- |
| `PROJECT_NAME` | `NOVA` | Platform application identity |
| `DATABASE_URL` | `postgresql+asyncpg://nova:nova_secret@localhost:5432/nova_db` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis caching & broker URL |
| `SECRET_KEY` | `NOVA_SECRET_KEY_CHANGE_IN_PRODUCTION` | JWT signing secret key |
| `OPENAI_API_KEY` | `""` | Optional LLM provider key |
| `EXA_API_KEY` | `""` | Optional Exa live web search API key |
| `KNOWLEDGE_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | FastEmbed vector embedding model |
| `ASSISTANT_RERANK_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` | Cross-encoder reranking model |

---

## 🚀 Running NOVA

Once installed, the platform components operate synchronously to deliver knowledge intelligence:

1. **Frontend**: Accessible at `http://localhost:5173` (or `http://localhost:8080` in Docker).
2. **Backend API**: Accessible at `http://localhost:8000/api/v1`.
3. **Interactive Swagger Docs**: View full interactive API endpoints at `http://localhost:8000/docs`.
4. **Celery Worker**: Processes background jobs for document parsing, embeddings, and benchmarking.
5. **Flower Task Monitor**: Monitor worker jobs at `http://localhost:5555` (when launched via Docker Compose).

---

## 📖 API Documentation

NOVA automatically generates interactive **OpenAPI / Swagger** documentation. Explore and test all endpoints directly in the browser at:

👉 `http://localhost:8000/docs`

Key API Route Groups:
- `/api/v1/auth`: User authentication, token issuance, and RBAC profile management.
- `/api/v1/assistant`: Streaming RAG Q&A, query planning, and evidence generation.
- `/api/v1/knowledge`: Document uploads, vector index listing, chunk inspection, and deletion.
- `/api/v1/source-studio`: Source ingestion management (files, URLs, repositories).
- `/api/v1/graph`: GraphRAG entity extractions and topology endpoints.
- `/api/v1/memory`: Session memory state recall and workspace contexts.
- `/api/v1/benchmarks`: Benchmark execution, progress tracking, and strategy comparison reports.
- `/api/v1/executive-intelligence`: Executive portfolio metrics and PDF export endpoint.

---

## 🔬 Benchmark Engine

NOVA features a built-in empirical evaluation suite to benchmark **10+ state-of-the-art RAG research strategies** against real-world domain queries:

1. **Vanilla RAG**: Basic top-K similarity search with direct prompt injection.
2. **Dense Retrieval**: Bi-encoder vector similarity matching via FastEmbed.
3. **Sparse Retrieval**: BM25 lexical term-frequency matching for exact keywords.
4. **Hybrid Retrieval**: Convex combination of Dense vector scores + Sparse BM25 scores with Reciprocal Rank Fusion (RRF).
5. **GraphRAG**: Entity-relation graph traversals for global contextual synthesis.
6. **Adaptive RAG**: Dynamic routing based on query classification and confidence estimation.
7. **HyDE (Hypothetical Document Embeddings)**: Generates hypothetical answer documents before embedding for improved semantic alignment.
8. **MemoRAG**: Integrates persistent memory context into document chunk scoring.
9. **LongRAG**: Extended context window chunking for long-form synthesis.
10. **LightRAG**: Lightweight, low-latency graph retrieval tailored for quick responses.

---

## 🛣️ Roadmap

### Near-Term Goals
- [ ] Native support for multimodal image/figure extraction from PDFs.
- [ ] Real-time collaborative document annotation and knowledge tagging.
- [ ] Integration with additional vector databases (Qdrant, Milvus, Weaviate).

### Future Research
- [ ] Fine-grained automated self-healing knowledge graph pruning.
- [ ] Federated cross-tenant knowledge isolation with zero-knowledge verification.
- [ ] On-device local GGUF LLM execution via WebGPU / ONNX runtime.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author & Maintainer

**Repository Owner & Lead Architect**:  
GitHub: [@TROJAN1HAMMER](https://github.com/TROJAN1HAMMER)  
Repository: [https://github.com/TROJAN1HAMMER/NOVA.git](https://github.com/TROJAN1HAMMER/NOVA.git)

---

## 🙏 Acknowledgements

NOVA draws inspiration from contemporary breakthroughs in Retrieval-Augmented Generation, GraphRAG research, and Adaptive AI architectures. We acknowledge the contributions of open-source projects including FastAPI, pgvector, FastEmbed, React, and the broader AI research community.
