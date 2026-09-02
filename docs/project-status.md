# RegIntel RAG — Project Status & Capability Matrix (Phase 52.18)

**Project Stage**: Production-Oriented Regulatory Intelligence & Change Analysis System  
**Release Version**: `0.1.0`

---

## 1. IMPLEMENTED

| Capability | Module / Location | Status |
| :--- | :--- | :--- |
| **SEBI Regulatory Web Ingestion** | `app/ingestion/pipeline.py` | Complete |
| **Content Deduplication & Hashing** | `app/ingestion/cleaner.py`, `models.py` | Complete (SHA-256) |
| **Structure-Aware Chunking** | `app/ingestion/chunker.py` | Complete (800-token target) |
| **Gemini 768d Embeddings** | `app/rag/embeddings.py` | Complete (`gemini-embedding-001`) |
| **MongoDB Atlas Vector Search** | `app/retrieval/mongodb_vector.py` | Complete |
| **BM25 Lexical Keyword Search** | `app/retrieval/bm25.py` | Complete (Okapi BM25) |
| **Hybrid RRF Fusion** | `app/retrieval/hybrid.py` | Complete (Reciprocal Rank Fusion) |
| **Local Neural Cross-Encoder Reranking** | `app/retrieval/reranker.py` | Complete (`bge-reranker-v2-m3`) |
| **Query Intent & Temporal Analysis** | `app/retrieval/query_analyzer.py` | Complete (Deterministic Regex/Vocab) |
| **Document Version Tracking & Lineage** | `app/ingestion/version_tracker.py` | Complete (Supersession Graph) |
| **Direct Document Comparison** | `app/change_detection/` | Complete (4-Tier Section Matcher) |
| **Grounded Answer Synthesis** | `app/rag/pipeline.py` | Complete (Gemini & Ollama) |
| **Deterministic Citation Mapping** | `app/rag/citations.py` | Complete (100% Verifiable) |
| **Multi-LLM Routing & Fallback** | `app/llm/fallback.py` | Complete (Gemini $\rightarrow$ Ollama) |
| **FastAPI REST Service** | `app/main.py`, `app/api/` | Complete (OpenAPI, Request ID) |
| **React + TypeScript + Vite UI** | `frontend/src/` | Complete (Production SPA) |
| **MLflow Experiment Tracking** | `app/observability/mlflow_tracker.py` | Complete (Offline Benchmarks) |
| **Langfuse Distributed Tracing** | `app/observability/langfuse_tracer.py` | Complete (11 Span Hierarchy) |
| **Docker & Docker Compose** | `Dockerfile`, `docker-compose.yml` | Complete |
| **CI/CD Pipeline** | `.github/workflows/ci.yml` | Complete |

---

## 2. TESTED

- **Unit Tests**: Ingestion, cleaning, chunking, retrieval, reranking, RAG, citations, versioning, comparison, LLMs, observability.
- **End-to-End Tests**: Complete `/ask` RAG pipeline, side-by-side document comparison, and version lineage timeline.
- **Regression Tests**: Ingestion idempotency, retrieval score monotonicity, answerability abstention, citation validation, and fallback failover.
- **Security Tests**: Git ignore protection, secret credential redaction, vector array suppression, and error stack trace hiding.
- **Performance Benchmarks**: In-memory BM25, hybrid fusion, and pipeline execution latency profiles.

---

## 3. OPTIONAL (Requires External Services)

- **Live MongoDB Atlas Vector Queries**: Requires active Atlas cluster URI (`RUN_MONGODB_INTEGRATION=true`).
- **Live Google Gemini API**: Requires active API key (`RUN_GEMINI_INTEGRATION=true`).
- **Live Local Ollama Daemon**: Requires local Ollama running on `http://localhost:11434` (`RUN_OLLAMA_INTEGRATION=true`).
- **Live Langfuse Cloud Tracing**: Requires Langfuse public/secret keys (`RUN_LANGFUSE_INTEGRATION=true`).

---

## 4. KNOWN LIMITATIONS

1. **Corpus Scope**: Ingestion is tailored to Indian financial regulations (SEBI circulars, master circulars, orders, and advisories).
2. **CPU Neural Reranker Latency**: Running cross-encoder inference on CPU requires ~1.5s per candidate batch.
3. **Free-Tier API Quotas**: Google Gemini free-tier endpoints impose rate limits (mitigated by exponential backoff and automatic Ollama fallback).

---

## 5. NOT IMPLEMENTED (Future Roadmap)

- Multi-regulator expansion (RBI, IRDAI, IFSCA, PFRDA).
- Native Knowledge Graph database integration (Neo4j).
- ONNX Runtime / INT8 quantization for sub-50ms CPU cross-encoder reranking.
- Claim-level Natural Language Inference (NLI) entailment verification.
