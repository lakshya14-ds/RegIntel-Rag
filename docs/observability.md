# Observability & Monitoring: MLflow & Langfuse

RegIntel RAG integrates two industry-standard observability stacks:
1. **MLflow (Phase 32)**: Experiment tracking, metric visualization, hyperparameter auditing, and artifact storage for offline and benchmark evaluations.
2. **Langfuse (Phase 33)**: Real-time execution tracing, span hierarchy profiling, and token/cost analytics for live RAG requests.

---

## 1. MLflow Experiment Tracking

### Configuration
In `.env`:
```env
MLFLOW_ENABLED=true
MLFLOW_TRACKING_URI="sqlite:///app/data/mlflow.db"  # or "http://localhost:5000" or local folder
MLFLOW_EXPERIMENT_NAME="regintel-rag-evaluations"
```

### Tracked Metrics & Parameters
- **Retrieval Modalities**: Vector, BM25, Hybrid (RRF), Hybrid + BGE Reranker
- **Metrics**: `Recall@3`, `Recall@5`, `Recall@10`, `MRR`, `Precision@5`, `Failures`
- **Generation Metrics**: `Answer Relevance (1-5)`, `Groundedness (1-5)`, `Citation Correctness (1-5)`, `Citation Integrity (%)`, `Unsupported Query Handling (%)`
- **Logged Artifacts**: `retrieval_report.json`, `retrieval_report.md`, `generation_report.json`, `manual_review.md`

### Launching Local MLflow UI
```bash
mlflow ui --port 5000
```
Open [http://localhost:5000](http://localhost:5000) to view and compare evaluation runs side-by-side.

---

## 2. Langfuse Live Tracing

### Configuration
In `.env`:
```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="https://cloud.langfuse.com"
```

### Span Hierarchy
```
RAG Query Execution (Root Trace)
├── Query Intent Classification (Span)
├── Candidate Retrieval (Span: hybrid/vector/bm25)
├── Cross-Encoder Reranking (Span)
├── Grounded Answer Generation (Generation: prompt, completion, latency)
└── Citation & Evidence Validation (Span)
```
*Note: If Langfuse credentials are not provided or if network connectivity is absent, the tracker automatically operates in zero-overhead no-op mode without throwing errors.*
