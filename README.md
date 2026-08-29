# RegIntel RAG — Regulatory Intelligence & Change Analysis System

A production-grade, grounded Hybrid RAG and Regulatory Change Detection platform for Indian Financial Regulations (SEBI, RBI, etc.) with end-to-end experiment tracking, real-time observability, Docker containerization, and automated CI/CD pipelines.

---

## 1. System Architecture

```text
                      USER / COMPLIANCE OFFICER
                                │
                                ▼
                       Streamlit Frontend (:8501)
                                │
                                ▼
                        FastAPI Backend (:8000)
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
        ▼                       ▼                        ▼
     POST /ask            POST /compare             GET /latest
        │                       │                        │
        └───────────────────────┼────────────────────────┘
                                ▼
                      Application Services
                                │
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
  Hybrid Retrieval      Change Detection          Version Tracker
  (Dense + BM25)        & Section Diff            & Lineage Graph
        │                       │                        │
        ├── Gemini Embeddings   ├── Heading Normalizer   ├── Supersession Regex
        ├── BM25Plus Lexical    ├── Delta Classifier     └── Lineage Ranking
        └── BGE Neural Rerank   └── Impact Summarizer
                                │
                                ▼
                   Observability & Storage Layer
                                │
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
  MongoDB Atlas          MLflow Experiments       Langfuse Tracing
  & Processed Chunks     & Benchmark Metrics      & Span Monitoring
```

---

## 2. Key Capabilities by Phase

- **Phases 7–15**: MongoDB Atlas integration, Pydantic data modeling, Crawl4AI scraping, section-aware chunking, Gemini 768-dim embeddings, and cosine vector retrieval.
- **Phases 16–22**: Multi-mode retrieval (BM25Plus + Vector + BGE Cross-Encoder Reranking), grounded generation with citation validation, query intent classification, and temporal ranking.
- **Phases 23–27**: Structural regulatory change detection, direct document comparison (`/compare`), and rigorous benchmark evaluation datasets (retrieval + generation).
- **Phases 28–31**: High-performance FastAPI REST API, modern 4-tab Streamlit dashboard, automated idempotent document ingestion with chunk caching, and regulatory supersession version tracking.
- **Phases 32–35**:
  - **Phase 32 (MLflow)**: Metric auditing, parameter tracking, and artifact logging for benchmark evaluations.
  - **Phase 33 (Langfuse)**: Real-time execution tracing and span profiling for live RAG requests.
  - **Phase 34 (Docker)**: Multi-service container orchestration (`api`, `frontend`, `mongo`, `mlflow`).
  - **Phase 35 (CI/CD)**: GitHub Actions automated workflow and deployment verification diagnostics.

---

## 3. Quick Start

### 1. Environment Configuration
Create a `.env` file in the root directory:
```env
MONGODB_URI="mongodb+srv://..."
MONGODB_DB_NAME="regintel"
MONGODB_COLLECTION_NAME="documents"
MONGODB_CHUNKS_COLLECTION="chunks"
GEMINI_API_KEY="AIzaSy..."

# API & Frontend
FASTAPI_HOST="0.0.0.0"
FASTAPI_PORT=8000
FASTAPI_BASE_URL="http://localhost:8000"
CORS_ORIGINS="http://localhost:8501,http://127.0.0.1:8501"

# Observability
MLFLOW_ENABLED=true
MLFLOW_TRACKING_URI="sqlite:///app/data/mlflow.db"
MLFLOW_EXPERIMENT_NAME="regintel-rag-evaluations"

LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="https://cloud.langfuse.com"
```

### 2. Run with Docker Compose
```bash
docker-compose up --build -d
```
- **Streamlit Web UI**: [http://localhost:8501](http://localhost:8501)
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MLflow Tracking Dashboard**: [http://localhost:5000](http://localhost:5000)

### 3. Run Locally (Development)
```bash
# Start FastAPI backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Streamlit frontend (in a separate terminal)
streamlit run frontend/streamlit_app.py --server.port 8501
```

---

## 4. Ingestion & Version Tracking CLI

### Ingestion Preview (Dry Run)
```bash
python -m app.ingestion.pipeline --source sebi --limit 10 --dry-run
```

### Batch Ingestion Run
```bash
python -m app.ingestion.pipeline --source sebi --limit 20
```

### Inspect Document Version Lineage
```bash
python -m app.ingestion.version_tracker --document 69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8
```

---

## 5. Evaluation & MLflow Tracking
```bash
# Run complete evaluation benchmark and log results to MLflow
python -m evaluation.run_all
```

---

## 6. Deployment Verification & Testing
```bash
# Run deployment readiness verification
python scripts/verify_deployment.py

# Run comprehensive test suite
pytest -v
```
