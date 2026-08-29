# RegIntel RAG Release Readiness Checklist (Phase 35.11)

Before tagging a release or deploying containerized images, verify each checklist item:

## 1. Quality & Test Automation
- [x] All unit tests passing (`pytest tests/unit`)
- [x] Integration tests passing or gracefully skipping when offline (`pytest tests/integration`)
- [x] No syntax errors or broken imports (`python -m compileall app/ frontend/ evaluation/ tests/`)
- [x] Automated CI workflow passing on GitHub Actions (`.github/workflows/ci.yml`)

## 2. Configuration & Credentials
- [x] `.env.example` is complete and up-to-date
- [x] Zero real production secrets committed in git history
- [x] `GEMINI_API_KEY` configured and verified
- [x] `MONGODB_URI` pointing to target cluster
- [x] `REGINTEL_VERSION` set and exposed via `GET /health`

## 3. Storage, Ingestion & Vector Index
- [x] Local processed directory populated with SEBI regulatory documents (`data/processed`)
- [x] Chunk collections and embeddings verified (768-dimensional normalized vectors)
- [x] Incremental ingestion pipeline operational with SHA-256 deduplication
- [x] Regulatory version tracking resolving supersession links

## 4. RAG Pipeline & Generation Quality
- [x] Grounded responses with valid bracketed citations (`[1]`, `[2]`)
- [x] Zero hallucinated citation indices verified by CitationManager
- [x] Insufficient evidence handling operational for out-of-domain queries
- [x] BM25Plus, Vector, and BGE cross-encoder reranker tested

## 5. Observability & Monitoring
- [x] MLflow experiment tracking active (`RegIntel-RAG`) with offline SQLite backend
- [x] Evaluation benchmarks logging metrics to MLflow (`python -m evaluation.run_mlflow_experiment`)
- [x] Langfuse live request tracing operational in no-op mode when unconfigured without throwing errors

## 6. Containerization & Services
- [x] `Dockerfile` builds cleanly without warnings (`docker build -t regintel-rag .`)
- [x] `docker-compose.yml` multi-service orchestration ready (`backend` + `frontend`)
- [x] `GET /health` endpoint functional for container healthchecks
- [x] Streamlit dashboard loads cleanly on port 8501
