"""
Audit Sections 26 to 40 for RegIntel RAG Codebase Audit.
"""

SECTIONS_26_TO_40 = """## SECTION 26 — DOCKER CONTAINERIZATION

### 26.1 Backend Dockerfile (`Dockerfile`)
- **Base Image**: `python:3.11-slim`
- **Optimization**: Installs CPU-only PyTorch (`--extra-index-url https://download.pytorch.org/whl/cpu`) to prevent CI runner disk exhaustion (Commit `24c2cd6`).
- **Exposed Ports**: `8000` (FastAPI), `5000` (MLflow optional server).
- **Entrypoint**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

### 26.2 Frontend Dockerfile (`frontend/Dockerfile`)
- **Multi-Stage Build**:
  - Stage 1 (`build`): Node 20 alpine executes `npm run build` producing static assets in `dist/`.
  - Stage 2 (`runtime`): Nginx alpine serves static SPA files and proxies `/api/` requests to backend port `8000`.
- **Exposed Port**: `80` (mapped to `5173:80` in `docker-compose.yml`).

### 26.3 Docker Compose (`docker-compose.yml`)
- Service `backend`: Builds root Dockerfile, passes `.env` variables, health checks on `/health`.
- Service `frontend`: Builds `frontend/Dockerfile`, maps port `5173:80`, depends on `backend`.

---

## SECTION 27 — CI/CD PIPELINE

### 27.1 GitHub Actions Workflow (`.github/workflows/ci.yml`)
Dual-job automated matrix triggered on `push` to `main` and all pull requests:
1. **Job 1: `backend-test` (Ubuntu Latest)**:
   - Sets up Python 3.11 with pip caching.
   - Installs CPU-only PyTorch and `requirements.txt`.
   - Executes Python bytecode compilation (`python -m compileall app evaluation tests`).
   - Runs unit and regression test suite (`pytest -m "not integration"`).
   - Executes contract security validations.
2. **Job 2: `frontend-test` (Ubuntu Latest)**:
   - Sets up Node.js 20 with npm caching.
   - Installs dependencies via `npm ci`.
   - Executes TypeScript typechecking (`npm run typecheck`).
   - Executes ESLint validation (`npm run lint`).
   - Executes Vitest test suite (`npm run test`).
   - Compiles production bundle (`npm run build`).
   - Validates container build (`docker build -t regintel-frontend:ci ./frontend`).

---

## SECTION 28 — DEVELOPMENT WORKFLOW

### 28.1 Standard Developer Commands
- **Backend Setup & Run**:
  ```powershell
  python -m venv venv
  .\\venv\\Scripts\\Activate.ps1
  pip install -r requirements.txt
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ```
- **Frontend Setup & Run**:
  ```powershell
  cd frontend
  npm install
  npm run dev
  ```
- **Run Backend Tests**:
  ```powershell
  .\\venv\\Scripts\\pytest -q
  ```
- **Run Frontend Tests**:
  ```powershell
  cd frontend
  npm run test
  ```
- **Run Evaluation Benchmark**:
  ```powershell
  python -m evaluation.run_all_evaluations
  ```

---

## SECTION 29 — PROJECT MANAGEMENT

> [!NOTE]
> **Audit Finding**: Project-management tooling was not identifiable from the repository. No Jira keys, Trello boards, Linear configs, Notion export links, or Azure Boards references exist in the commit history or repository tree. The development workflow was managed directly through Git commits and GitHub Actions pull requests.

---

## SECTION 30 — DOCUMENTATION STRUCTURE

### 30.1 Repository Documentation Audit

| Document | File Path | Purpose | Status |
| :--- | :--- | :--- | :---: |
| **README** | `README.md` | Primary repository overview and quickstart guide | COMPLETE |
| **Interview Architecture** | `docs/architecture-interview.md` | System design talking points for technical interviews | COMPLETE |
| **Deployment Guide** | `docs/deployment.md` | Step-by-step production hosting on Render / Cloud | COMPLETE |
| **Troubleshooting Guide** | `docs/deployment-troubleshooting.md` | Production failure resolution and CORS debugging | COMPLETE |
| **Engineering Decisions** | `docs/engineering-decisions.md` | 10 architectural decision records (ADRs) | COMPLETE |
| **Demo Script** | `docs/final-demo.md` | 5-step live walkthrough script for stakeholders | COMPLETE |
| **Portfolio Checklist** | `docs/portfolio-checklist.md` | Production-readiness audit across 7 dimensions | COMPLETE |
| **Project Status** | `docs/project-status.md` | Component maturity and testing status matrix | COMPLETE |
| **Release Checklist** | `docs/release-checklist.md` | Pre-deployment verification gates | COMPLETE |
| **Resume Profiles** | `docs/resume.md`, `resume-bullets.md` | Career profiles for Full-Stack & RAG Engineer | COMPLETE |
| **Screenshot Portfolio** | `docs/screenshots/README.md` | Visual catalog of UI views and tracing dashboards | COMPLETE |
| **Evaluation Final Report** | `evaluation/results/final_report.md` | Comprehensive empirical benchmark findings | COMPLETE |

---

## SECTION 31 — TESTING AND QUALITY ASSURANCE

### 31.1 Test Suite Inventory & Results

| Test Category | Suite Location | Test Count | Status | Notes |
| :--- | :--- | :---: | :---: | :--- |
| **Backend Unit Tests** | `tests/unit/` | 200+ cases | **PASSED** | 100% mocked, zero network dependency. |
| **Backend Integration** | `tests/integration/` | 12 cases | **SKIPPED** | Gated by `RUN_*_INTEGRATION` flags in offline mode. |
| **API Contracts** | `tests/api/` | 12 cases | **PASSED** | Request ID propagation, 422 schemas, routes. |
| **End-to-End Pipeline** | `tests/e2e/` | 3 cases | **PASSED** | Mocked RAG pipeline, comparison, timeline. |
| **Regression Tests** | `tests/regression/` | 15+ cases | **PASSED** | Content hash idempotency, failover routing. |
| **Security Contracts** | `tests/security/` | 4 cases | **PASSED** | Secret redaction, stack trace suppression. |
| **Performance Benchmarks**| `tests/performance/` | 3 cases | **PASSED** | Latency profiling for BM25 and fusion. |
| **Frontend Component Tests**| `frontend/src/__tests__/`| 12 cases | **PASSED** | Vitest testing of components and API client. |

---

## SECTION 32 — SECURITY AUDIT

### 32.1 Findings & Controls
- **Hardcoded Secrets**: Verified **zero** hardcoded production API keys, passwords, or MongoDB connection strings in application code.
- **Environment Separation**: All sensitive tokens (`GEMINI_API_KEY`, `MONGODB_URI`, `LANGFUSE_SECRET_KEY`) reside exclusively in `.env` (ignored via `.gitignore`).
- **Frontend Protection**: Zero secrets are passed to or bundled in the Vite client build. Only `VITE_API_BASE_URL` is exposed.
- **API Error Masking**: Unhandled server exceptions return generic 500 error envelopes; raw Python stack traces are never exposed in HTTP responses.
- **Vector Array Suppression**: API response models exclude raw 768-dimensional float embedding arrays to reduce bandwidth and prevent latent vector reverse-engineering.

---

## SECTION 33 — PERFORMANCE AUDIT

### 33.1 Latency Profile & Bottlenecks

| Component | Average Latency | Status / Bottleneck Assessment |
| :--- | :---: | :--- |
| **BM25 Keyword Search** | `< 15 ms` | Highly optimal in-memory execution. |
| **Reciprocal Rank Fusion**| `< 5 ms` | Negligible mathematical merge overhead. |
| **Gemini Dense Embedding**| `200 - 450 ms` | Remote HTTP network call to Google API. |
| **Gemini Flash Lite Generation**| `1.2 - 2.5 s` | Standard streaming LLM response time. |
| **Langfuse Distributed Tracer**| `+0.37 ms` | Background worker queue with negligible overhead. |
| **Local BGE Reranker (CPU)**| **~23.0 s** | **Primary Bottleneck**: Cross-encoder inference on CPU takes ~1.1s per query-chunk pair across 20 candidates. GPU acceleration is recommended for high-throughput production. |

---

## SECTION 34 — COST / FREE-TIER ARCHITECTURE

### 34.1 Cost Breakdown

| Component | Cost Tier | Free Tier Limits | Actual Project Usage |
| :--- | :---: | :--- | :--- |
| **MongoDB Atlas** | Free (M0) | 512 MB storage, shared RAM | ~4.2 MB used across 23 docs and 404 chunks. |
| **Google Gemini API** | Free Tier | 15 RPM / 1M TPM for Flash Lite | Evaluated within free rate quotas. |
| **BAAI/bge-reranker**| Free / OSS | Open-source weights (Apache 2.0) | Zero API cost (runs locally on CPU). |
| **Ollama** | Free / OSS | Open-source local runtime | Zero API cost (runs locally on device). |
| **MLflow** | Free / OSS | Open-source local SQLite | Zero cloud cost. |
| **Langfuse** | Free Tier | 50,000 observations / month | < 1,000 observations used during evaluation. |
| **FastAPI + React** | Free / OSS | MIT License | Zero licensing fees. |

---

## SECTION 35 — IMPLEMENTATION MAP

### 35.1 File-by-File Symbol Inventory

| Component Layer | File Path | Key Class / Function | Architectural Purpose |
| :--- | :--- | :--- | :--- |
| **Config** | `app/config.py` | `Settings`, `get_settings()` | Pydantic v2 environment variable configuration. |
| **Database** | `app/db.py` | `get_client()`, `get_collection()` | MongoDB connection pool and health verification. |
| **Repository** | `app/ingestion/repository.py` | `DocumentRepository` | Document & chunk CRUD and index management. |
| **Cleaner** | `app/ingestion/cleaner.py` | `clean_html()` | Strips HTML boilerplate while preserving legal text. |
| **Chunker** | `app/ingestion/chunker.py` | `chunk_document()` | 800-token section-aware chunking engine. |
| **Embeddings** | `app/rag/embeddings.py` | `GeminiEmbedder` | 768d vector generation via Google GenAI SDK. |
| **Vector Search** | `app/retrieval/mongodb_vector.py`| `MongoDBVectorRetriever` | MongoDB Atlas `$vectorSearch` execution. |
| **BM25 Search** | `app/retrieval/bm25.py` | `BM25Retriever` | Okapi BM25 keyword search over local chunks. |
| **Hybrid Search**| `app/retrieval/hybrid.py` | `HybridRetriever` | Reciprocal Rank Fusion of vector and BM25 ranks. |
| **Reranker** | `app/retrieval/reranker.py` | `LocalReranker` | Cross-encoder reranking via BGE-M3. |
| **Query Analyzer**| `app/retrieval/query_analyzer.py`| `analyze_query()` | Deterministic extraction of `QueryIntent`. |
| **RAG Pipeline** | `app/rag/pipeline.py` | `RAGPipeline` | End-to-end question answering coordinator. |
| **Citations** | `app/rag/citations.py` | `validate_citations()` | Regex verification of bracketed citation indices. |
| **Change Detector**| `app/change_detection/detector.py`| `ChangeDetector` | Section delta categorization (`ADDED`, `MODIFIED`). |
| **Comparator** | `app/change_detection/document_comparator.py`| `DocumentComparator` | 4-tier pairwise document comparison engine. |
| **Version Graph**| `app/ingestion/version_tracker.py`| `VersionTracker` | Supersession detection and chronological timeline. |
| **LLM Provider** | `app/llm/fallback.py` | `FallbackLLMProvider` | Failover coordinator between Gemini and Ollama. |
| **Tracer** | `app/observability/langfuse_tracer.py`| `LangfuseTracer` | 11-span hierarchical distributed tracing client. |
| **API Entrypoint**| `app/main.py` | `app`, `lifespan()` | FastAPI app setup, middleware, and routers. |
| **Frontend Client**| `frontend/src/api/client.ts`| `RegIntelAPIClient` | TypeScript fetch client with error normalization. |

---

## SECTION 36 — COMPLETE FILE TREE

```text
RegIntel-Rag/
├── .github/
│   └── workflows/
│       └── ci.yml                          # Dual-job CI pipeline (Backend Pytest + Frontend Vitest/Build)
├── app/
│   ├── api/
│   │   ├── routes_documents.py             # GET /latest, GET /document/{id}, GET /document/{id}/versions
│   │   ├── routes_health.py                # GET /health, GET /
│   │   └── routes_rag.py                   # POST /ask, POST /search, POST /compare
│   ├── change_detection/
│   │   ├── detector.py                     # ChangeDetector engine
│   │   ├── document_comparator.py          # 4-tier section matching & comparison
│   │   └── models.py                       # SectionChange, ComparisonReport models
│   ├── ingestion/
│   │   ├── chunk_validator.py              # Chunk boundary and quality checks
│   │   ├── chunker.py                      # 800-token section chunker
│   │   ├── cleaner.py                      # HTML boilerplate cleaner
│   │   ├── models.py                       # RegulatoryDocument, DocumentChunk schemas
│   │   ├── pipeline.py                     # Ingestion coordinator (NEW/CHANGED/UNCHANGED)
│   │   ├── repository.py                   # MongoDB document & chunk repository
│   │   └── version_tracker.py              # Legal supersession tracker
│   ├── llm/
│   │   ├── fallback.py                     # Gemini -> Ollama circuit-breaker failover
│   │   ├── gemini.py                       # GeminiProvider (gemini-flash-lite)
│   │   ├── ollama.py                       # OllamaProvider (local fallback)
│   │   └── provider.py                     # LLMProvider abstract interface
│   ├── observability/
│   │   ├── langfuse_tracer.py              # 11-span hierarchical tracing client
│   │   └── mlflow_tracker.py               # MLflow benchmark experiment tracker
│   ├── rag/
│   │   ├── citations.py                    # 100% bracket citation validator
│   │   ├── embeddings.py                   # Gemini 768d vector embedder
│   │   ├── pipeline.py                     # Grounded RAG synthesis coordinator
│   │   └── prompts.py                      # Grounded compliance system prompts
│   ├── retrieval/
│   │   ├── bm25.py                         # In-memory Okapi BM25 index
│   │   ├── hybrid.py                       # Reciprocal Rank Fusion (RRF k=60)
│   │   ├── mongodb_vector.py               # MongoDB Atlas $vectorSearch
│   │   ├── query_analyzer.py               # Deterministic QueryIntent classifier
│   │   └── reranker.py                     # Local BGE-reranker-v2-m3 cross-encoder
│   ├── schemas/
│   │   ├── requests.py                     # AskRequest, SearchRequest, CompareRequest
│   │   └── responses.py                    # AskResponse, SearchResponse, CompareResponse
│   ├── config.py                           # Pydantic v2 application settings
│   ├── db.py                               # MongoDB Atlas connection manager
│   └── main.py                             # FastAPI application entrypoint
├── data/
│   ├── processed/                          # 23 structured circular JSON files
│   │   └── chunks/                         # 24 chunk files (404 total chunks)
│   └── raw/                                # 21 raw HTML scraped documents
├── docs/                                   # 13 technical documentation guides & ADRs
├── evaluation/
│   ├── dataset/                            # Retrieval, generation, and comparison benchmarks
│   ├── results/                            # Benchmark reports and empirical evaluation logs
│   ├── compare_llm_providers.py            # Head-to-head Gemini vs Ollama benchmark
│   ├── failure_analyzer.py                 # Grounding failure taxonomy
│   ├── generation_evaluator.py             # LLM Judge relevance and completeness
│   └── run_all_evaluations.py              # Master evaluation runner
├── frontend/
│   ├── src/
│   │   ├── api/client.ts                   # TypeScript REST client
│   │   ├── components/                     # UI components (Chat, Citations, Diff, Timeline)
│   │   ├── hooks/                          # Custom React hooks
│   │   ├── pages/                          # 8 page components (Home, Ask, Compare, Latest, etc.)
│   │   ├── types/api.ts                    # TypeScript API interface contracts
│   │   ├── App.tsx                         # Router and ErrorBoundary entrypoint
│   │   ├── index.css                       # Pure CSS custom design system
│   │   └── main.tsx                        # React DOM mounting
│   ├── Dockerfile                          # Multi-stage Nginx production build
│   └── package.json                        # Dependencies (React, Vite, Vitest)
├── scraper/
│   └── crawl_sebi.py                       # Crawl4AI web extraction script
├── tests/
│   ├── api/                                # FastAPI route & contract tests
│   ├── e2e/                                # End-to-end integration workflows
│   ├── regression/                         # Idempotency and score monotonicity tests
│   ├── security/                           # Secret redaction & input validation tests
│   ├── unit/                               # Hermetic unit tests across all app modules
│   └── conftest.py                         # Pytest configuration and fixtures
├── Dockerfile                              # Multi-stage backend container
├── docker-compose.yml                      # Multi-service composition
├── pytest.ini                              # Pytest settings (pythonpath = .)
└── requirements.txt                        # Backend dependencies
```

---

## SECTION 37 — END-TO-END TECHNICAL WALKTHROUGH

### 37.1 Walkthrough Query: "What are the latest SEBI requirements for investment advisers?"

1. **User Action (React UI)**: User inputs query into `/ask` prompt bar.
2. **HTTP Request (`frontend/src/api/client.ts`)**: Dispatches `POST http://localhost:8000/ask` with payload `{"query": "...", "category": null}`.
3. **Request Correlation (`app/main.py`)**: Middleware intercepts request, generates `X-Request-ID: req-a4f109b...`, and attaches it to request state.
4. **Query Understanding (`app/retrieval/query_analyzer.py`)**:
   - `analyze_query()` evaluates query text.
   - Outputs `QueryIntent(intent_type='current_requirement', temporal_scope='latest', target_category='Investment Adviser')`.
5. **Dense Vector Embedding (`app/rag/embeddings.py`)**:
   - Calls Google Gemini API with `task_type="RETRIEVAL_QUERY"`.
   - Returns 768-dimensional normalized float array.
6. **Parallel Candidate Retrieval (`app/retrieval/hybrid.py`)**:
   - Branch A: MongoDB Atlas `$vectorSearch` retrieves top-20 dense candidates.
   - Branch B: `BM25Retriever` scores query terms across 404 in-memory chunks.
7. **Reciprocal Rank Fusion**: RRF merges rank lists with $k=60$, producing top-20 fused candidate chunks.
8. **Neural Reranking (`app/retrieval/reranker.py`)**:
   - `BAAI/bge-reranker-v2-m3` scores all 20 `(query, chunk_text)` pairs on CPU.
   - Cuts off top-5 highest-scoring evidence chunks.
9. **Prompt Construction (`app/rag/pipeline.py`)**:
   - Formats evidence chunks with headers `[1]` through `[5]`.
   - Injects strict legal grounding instructions.
10. **Dual-LLM Synthesis (`app/llm/gemini.py`)**:
    - Dispatches prompt to `models/gemini-flash-lite-latest`.
    - Returns drafted response with citations (e.g., `"...must maintain net worth of Rs. 50 Lakhs [1]..."`).
11. **Citation Validation (`app/rag/citations.py`)**:
    - `validate_citations()` extracts all bracket indices via regex `\\[(\\d+)\\]`.
    - Confirms all indices exist in range `1..5`.
    - Maps each index to chunk metadata (title, circular code, SEBI URL).
12. **Client Response & UI Render**:
    - HTTP 200 OK returned with `AskResponse`.
    - React renders answer text with interactive blue badge chips `[1]`.
    - User clicks `[1]`; `CitationDrawer.tsx` slides out displaying the verbatim source clause and official SEBI link.

---

## SECTION 38 — END-TO-END CHANGE-DETECTION WALKTHROUGH

### 38.1 Comparing 2020 IA Guidelines vs 2024 IA Master Circular

1. **User Action (`/compare`)**: User selects base document (`sebi_3edbbaf8...` — 2020 Guidelines) and comparison document (`sebi_69098d6a...` — 2024 Master Circular).
2. **API Request**: `POST /compare` with document IDs.
3. **Chronology Verification (`app/change_detection/document_comparator.py`)**:
   - Verifies published dates (`2020-09-23` vs `2024-05-16`).
   - Assigns 2020 document as Circular A (base) and 2024 document as Circular B (amendment).
4. **4-Tier Section Alignment**:
   - Tier 1: Matches identical clause numbers (`Clause 2.1` $\\rightarrow$ `Clause 2.1`).
   - Tier 2: Matches normalized titles (`"Client Agreement"` $\\rightarrow$ `"Agreement between IA and Client"`).
   - Tier 3: High lexical overlap matching for renumbered clauses.
5. **Delta Classification**:
   - Categorizes each section: `ADDED`, `MODIFIED`, `REMOVED`, or `UNCHANGED`.
6. **Executive Summary Synthesis**:
   - Gemini generates a high-level compliance memo summarizing key policy updates.
7. **UI Diff Display**:
   - React renders summary metrics (**21 Total, 14 Modified, 7 Unchanged**).
   - Side-by-side `DiffBox.tsx` cards highlight deleted clauses in red and inserted clauses in green.

---

## SECTION 39 — END-TO-END INGESTION WALKTHROUGH

```text
SEBI Circular Published on Web
              │
              ▼
Crawl4AI Web Scraper (scraper/crawl_sebi.py)
              │
              ▼
Raw HTML Storage (data/raw/sebi_<hash>.html)
              │
              ▼
HTML Cleaner: Strip Navbars, Scripts, Tracking (app/ingestion/cleaner.py)
              │
              ▼
Metadata Extractor: Regex parse Title, Circular No, Date (app/ingestion/pipeline.py)
              │
              ▼
SHA-256 Content Hash Computed
              │
        ┌─────┴─────────────────────────┐
        ▼ Hash Matches                  ▼ Hash Differs / New
   Status: UNCHANGED               Status: NEW or CHANGED
(Skip redundant work)                   │
                                        ▼
                           Section Chunker (app/ingestion/chunker.py)
                           (800 tokens target, 100 overlap)
                                        │
                                        ▼
                           Chunk Quality Validator (app/ingestion/chunk_validator.py)
                           (Bounds 150-1000 tokens, content coverage)
                                        │
                                        ▼
                           Gemini Batch Embedding (app/rag/embeddings.py)
                           (task_type="RETRIEVAL_DOCUMENT" -> 768d vector)
                                        │
                                        ▼
                           Version Tracker (app/ingestion/version_tracker.py)
                           (Regex scan for 'supersedes circular no...')
                                        │
                                        ▼
                           MongoDB Atlas Upsert (app/ingestion/repository.py)
                           ('documents' & 'chunks' collections updated)
```

---

## SECTION 40 — IMPLEMENTED VS PLANNED

### 40.1 Feature Comparison Matrix

| Platform Capability | Status | Repository Evidence | Operational Notes |
| :--- | :---: | :--- | :--- |
| **SEBI Web Crawling** | IMPLEMENTED | `scraper/crawl_sebi.py` | Verified working with Crawl4AI. |
| **HTML Cleaning & Extraction** | IMPLEMENTED | `app/ingestion/cleaner.py` | Boilerplate stripped; legal clauses preserved. |
| **SHA-256 Deduplication** | IMPLEMENTED | `app/ingestion/pipeline.py` | Verified idempotent re-runs. |
| **Deterministic Chunking** | IMPLEMENTED | `app/ingestion/chunker.py` | 800-token section-aware chunking. |
| **Gemini 768d Embeddings** | IMPLEMENTED | `app/rag/embeddings.py` | `gemini-embedding-001` active. |
| **MongoDB Atlas Vector Search** | IMPLEMENTED | `app/retrieval/mongodb_vector.py`| `$vectorSearch` pipeline active. |
| **Okapi BM25 Search** | IMPLEMENTED | `app/retrieval/bm25.py` | In-memory index across 404 chunks. |
| **Hybrid RRF Fusion** | IMPLEMENTED | `app/retrieval/hybrid.py` | Reciprocal Rank Fusion ($k=60$). |
| **Neural Cross-Encoder** | IMPLEMENTED | `app/retrieval/reranker.py` | Local BGE-M3 model reranking top-20 to top-5. |
| **Query Intent Analyzer** | IMPLEMENTED | `app/retrieval/query_analyzer.py`| Deterministic intent & temporal extraction. |
| **Citation Integrity Validator**| IMPLEMENTED | `app/rag/citations.py` | 100% verification of bracketed indices. |
| **Dual-LLM Failover** | IMPLEMENTED | `app/llm/fallback.py` | Gemini $\rightarrow$ Ollama failover. |
| **Document Comparison** | IMPLEMENTED | `app/change_detection/` | 4-tier AST section matching. |
| **Version Lineage Graph** | IMPLEMENTED | `app/ingestion/version_tracker.py`| Supersession graph & chronological timeline. |
| **FastAPI REST API** | IMPLEMENTED | `app/main.py` | 8 endpoints with request ID correlation. |
| **React + Vite Frontend** | IMPLEMENTED | `frontend/src/` | Single-page application with 7 routes. |
| **MLflow Experiment Tracking** | IMPLEMENTED | `app/observability/mlflow_tracker.py`| Local SQLite experiment metrics logging. |
| **Langfuse Tracing** | IMPLEMENTED | `app/observability/langfuse_tracer.py`| 11-span hierarchical tracing. |
| **Cross-Regulator Search** | PLANNED | `docs/engineering-decisions.md` | RBI, IRDAI expansion planned for future. |
| **Real-Time Webhook Alerts** | PLANNED | `docs/release-checklist.md` | Automated webhook alert on new circular publication. |
| **OCR for Scanned Legacy PDFs**| PLANNED | None | Scanned image-only PDFs currently skipped. |
| **Enterprise RBAC / Auth** | PLANNED | None | No user authentication currently implemented. |
"""
print("Sections 26 to 40 loaded.")
