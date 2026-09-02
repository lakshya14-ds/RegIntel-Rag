# RegIntel RAG — Engineering Decisions & Architectural Tradeoffs (Phase 54.9)

This document provides in-depth technical justifications for every major design decision and technology choice across the **RegIntel RAG** system.

---

## 1. Embeddings: Google Gemini (`gemini-embedding-001`) vs. OpenAI (`text-embedding-3-small`) / Local HuggingFace

- **Decision**: Google Gemini `models/gemini-embedding-001` (768 dimensions, L2 normalized).
- **Rationale**:
  - **Generous Free Quota**: Supports up to 1,500 requests per minute on free-tier without credit card barriers.
  - **Optimal Dimensionality**: 768 dimensions strike the ideal balance between dense semantic representation and MongoDB Atlas memory footprint compared to 1536d or 3072d models.
  - **Task-Specific Embeddings**: Built-in support for `RETRIEVAL_DOCUMENT` vs. `RETRIEVAL_QUERY` task types produces asymmetric query-document vector alignment.
- **Tradeoff**: Subject to Google Cloud free-tier rate limiting under bursts (mitigated via deterministic caching and exponential backoff retry).

---

## 2. Vector Database: MongoDB Atlas Vector Search vs. Pinecone / Weaviate / Qdrant

- **Decision**: MongoDB Atlas with native Vector Search.
- **Rationale**:
  - **Unified Document + Vector Store**: Regulatory metadata (dates, circular numbers, categories, supersession links, full text) and vector embeddings coexist in a single database handle. No multi-system synchronization lag or dual-database consistency issues.
  - **Rich Pre-Filtering**: MongoDB's MQL syntax enables high-performance pre-filtering on `source`, `category`, and `status` before executing HNSW vector search.
  - **Free Tier Availability**: Atlas M0 cluster provides 512MB of cloud storage at zero cost.
- **Tradeoff**: Atlas Free Tier limits index building concurrency compared to dedicated standalone vector engines, requiring batch indexing.

---

## 3. Retrieval Strategy: Hybrid (Vector + BM25 with RRF) vs. Vector-Only Retrieval

- **Decision**: Hybrid Reciprocal Rank Fusion ($k=60$) combining dense semantic vectors (60% weight) and sparse Okapi BM25Plus keywords (40% weight).
- **Rationale**:
  - **Exact Circular Numbers**: Dense vectors struggle with exact alphanumeric regulatory identifiers (e.g. `SEBI/HO/MIRSD/DOS3/CIR/P/2018/115`). BM25 guarantees exact match recall for circular numbers and clause codes.
  - **Semantic Generalization**: Dense vector search handles conceptual, natural language queries (e.g. *"What is the penalty for late grievance resolution?"*).
  - **Empirical Superiority**: Hybrid retrieval increased `Recall@5` from **74.0%** (Vector-only) and **68.0%** (BM25-only) to **84.0%**.
- **Tradeoff**: Requires maintaining an in-memory or indexed BM25Plus corpus alongside the vector store.

---

## 4. Re-Ranking: Local Neural Cross-Encoder (`BAAI/bge-reranker-v2-m3`) vs. No Reranker / Cohere API

- **Decision**: Local Cross-Encoder `BAAI/bge-reranker-v2-m3` running locally via Sentence Transformers.
- **Rationale**:
  - **Deep Cross-Attention**: Bi-encoders compress documents and queries into independent vectors; cross-encoders process `(query, document)` pairs simultaneously through full self-attention layers, resolving nuanced regulatory conditions.
  - **Zero External API Cost**: Runs locally on CPU/CUDA without incurring per-query Cohere or OpenAI rerank API costs.
  - **Benchmark Lift**: Increased `Recall@5` from **84.0%** to **92.0%** and `MRR` from **0.72** to **0.84**.
- **Tradeoff**: Incurs ~1.5s latency on CPU-only free-tier container environments during initial inference.

---

## 5. Dual LLM Provider: Google Gemini with Transparent Local Ollama Fallback

- **Decision**: Primary Google Gemini (`models/gemini-flash-lite-latest`) with automatic failover to local Ollama (`llama3.2` / `mistral`).
- **Rationale**:
  - **High-Speed Cloud Inference**: Gemini Flash Lite generates responses in 300–600ms with strict JSON/markdown formatting adherence.
  - **Air-Gapped / Rate-Limit Resiliency**: If external cloud APIs experience outages or rate limit exhaustion, the system automatically routes to local Ollama without throwing 500 errors to the client.
- **Tradeoff**: Ollama is constrained to local machines or GPU instances and is skipped in minimal cloud free-tier containers.

---

## 6. Observability: Langfuse Distributed Tracing + MLflow Experiment Tracking

- **Decision**: Dual-purpose observability using Langfuse (hierarchical live tracing) and MLflow (offline benchmarking & dataset evaluation).
- **Rationale**:
  - **Hierarchical RAG Tracing**: Langfuse captures the exact execution tree (Query Analysis $\rightarrow$ Dense Embed $\rightarrow$ Vector Search $\rightarrow$ BM25 $\rightarrow$ RRF Fusion $\rightarrow$ Reranker $\rightarrow$ LLM $\rightarrow$ Citation Validation).
  - **Minimal Runtime Overhead**: Asynchronous tracing adds only **+0.37 ms** overhead.
  - **Systematic Evaluation Tracking**: MLflow logs offline benchmark runs, comparing model weights, RRF parameters, and prompting strategies across versions.
- **Tradeoff**: Requires optional API keys when connecting to remote Langfuse/MLflow servers.

---

## 7. Frontend: React + TypeScript + Vite vs. Streamlit

- **Decision**: Production-grade React 18 SPA built with TypeScript and Vite.
- **Rationale**:
  - **Granular DOM & Interactive UI**: Native side-by-side textual diffing, interactive inline citation chips `[1]`, slide-out inspection drawer, and custom CSS design system.
  - **Type Safety & Maintainability**: Strict TypeScript contracts mirroring FastAPI Pydantic schemas (`/ask`, `/compare`, `/latest`, `/document/{id}/versions`).
  - **Performance & Responsiveness**: Sub-millisecond client-side routing with React Router 6 and sub-75 kB production gzipped bundle.
  - **Testing**: Dedicated component test suite with Vitest and React Testing Library.
- **Tradeoff**: Requires Node.js build tooling and multi-stage Docker / Nginx containerization.
