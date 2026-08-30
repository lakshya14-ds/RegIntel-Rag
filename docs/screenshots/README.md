# RegIntel RAG — Screenshot Portfolio & Visual Assets (Phase 54.10)

This directory contains visual captures and UI walkthrough representations of the **RegIntel RAG** system.

---

## 1. Interface Views & Captures

### 1.1 Home / Grounded Question Answering (`01_ask_regintel.png`)
- **Location**: `frontend/streamlit_app.py` (Tab 1: Ask RegIntel)
- **Features Captured**:
  - Regulatory query prompt bar with auto-intent classification badge (`current_requirement`, `category: Investment Adviser`).
  - Answer synthesis panel featuring verified bracketed source indices (`[1]`, `[2]`).
  - LLM telemetry badge (`Gemini Flash Lite`, latency, fallback status).

### 1.2 Citation Evidence Drawer (`02_citation_evidence.png`)
- **Location**: `frontend/components/citations.py`
- **Features Captured**:
  - Expandable evidence cards showing exact source circular titles, section clauses, and SEBI source URLs.
  - 100% verification badge guaranteeing zero hallucinated citation indices.

### 1.3 Direct Document Comparison Engine (`03_document_comparison.png`)
- **Location**: `frontend/components/comparison.py` (Tab 2: Compare Circulars)
- **Features Captured**:
  - Executive Summary of changes between two circular versions.
  - Summary count badges (`1 ADDED`, `2 MODIFIED`, `0 REMOVED`, `14 UNCHANGED`).
  - Side-by-side section delta diff with compliance impact summaries.

### 1.4 Regulatory Version Lineage Graph (`04_version_timeline.png`)
- **Location**: `frontend/components/timeline.py` (Tab 4: Document Timeline)
- **Features Captured**:
  - Chronological version timeline showing `SUPERSEDES` and `SUPERSEDED` relationships.
  - Active legal currentness badges (`CURRENT` vs. `HISTORICAL`).

### 1.5 Multi-Method Regulatory Search (`05_document_search.png`)
- **Location**: `frontend/components/documents.py` (Tab 3: Search Documents)
- **Features Captured**:
  - Side-by-side retrieval mode selector (`Vector`, `BM25`, `Hybrid`).
  - Relevance score distribution and metadata filtering.

### 1.6 FastAPI Interactive Documentation (`06_fastapi_swagger.png`)
- **Location**: `http://localhost:8000/docs`
- **Features Captured**:
  - Complete OpenAPI 3.0 specification for `/health`, `/ask`, `/search`, `/compare`, `/latest`, `/document/{id}`.

### 1.7 Langfuse Distributed Request Trace (`07_langfuse_trace.png`)
- **Location**: Langfuse Cloud Dashboard
- **Features Captured**:
  - 11-span hierarchical trace (`query_analysis` $\rightarrow$ `query_embedding` $\rightarrow$ `vector_search` $\rightarrow$ `bm25` $\rightarrow$ `hybrid` $\rightarrow$ `reranker` $\rightarrow$ `llm_generation` $\rightarrow$ `citation_validation`).
  - Span-level latency breakdowns (+0.37 ms tracer overhead).

### 1.8 MLflow Benchmark & Metric Dashboard (`08_mlflow_benchmarks.png`)
- **Location**: MLflow Tracking UI
- **Features Captured**:
  - Retrieval Recall@5 and MRR progression curves across Vector, BM25, Hybrid, and Reranked experiments.

---

> [!NOTE]
> All visual assets must be scrubbed of live API keys, internal connection strings, or personal identifying tokens.
