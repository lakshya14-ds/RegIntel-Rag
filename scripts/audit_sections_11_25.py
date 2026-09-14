"""
Audit Sections 11 to 25 for RegIntel RAG Codebase Audit.
"""

SECTIONS_11_TO_25 = """## SECTION 11 — RETRIEVAL SYSTEM

### 11.1 Dense Vector Retrieval (`app/retrieval/mongodb_vector.py`)
- **Pipeline**: MongoDB `$vectorSearch` stage executing Approximate Nearest Neighbor (ANN) search.
- **Parameters**: `numCandidates=100`, `limit=20`.
- **Similarity Scoring**: Normalized dot product / cosine similarity returning float values in range `[-1.0, 1.0]`.

### 11.2 Sparse Lexical Retrieval (`app/retrieval/bm25.py`)
- **Implementation**: Okapi BM25 (`rank_bm25.BM25Okapi`).
- **Corpus**: Built dynamically from the 404 processed regulatory chunks in `data/processed/chunks/`.
- **Tokenization**: Lowercase regex alphanumeric tokenization removing English stopwords.
- **Latency**: Sub-15ms execution over in-memory corpus.

### 11.3 Hybrid Reciprocal Rank Fusion (RRF) (`app/retrieval/hybrid.py`)
To overcome semantic blindness to exact regulatory numbers (e.g., fee caps, section numbers) and lexical blindness to paraphrased legal concepts, RegIntel merges vector and BM25 candidates using Reciprocal Rank Fusion:

$$RRF(d) = \\sum_{m \\in \\{vector, bm25\\}} \\frac{1}{k + r_m(d)}$$

Where:
- $k = 60$ (smoothing constant preventing top ranks from completely dominating).
- $r_m(d)$ is the 1-based rank position of chunk $d$ in retrieval method $m$.
- Candidate pool: Top-20 merged chunks passed to the reranking stage.

### 11.4 Local Neural Cross-Encoder Reranking (`app/retrieval/reranker.py`)
- **Model**: `BAAI/bge-reranker-v2-m3` (Hugging Face / PyTorch).
- **Execution Device**: Configured to `CPU` with 8-thread multithreading (`torch.set_num_threads(8)`).
- **Input**: List of `(query, chunk_content)` string pairs for top-20 RRF candidates.
- **Scoring**: Full cross-attention across query and chunk tokens producing continuous logit scores.
- **Top-K Cutoff**: Top-5 highest scoring chunks selected as authoritative evidence.

---

## SECTION 12 — QUERY UNDERSTANDING

### 12.1 QueryIntent Data Structure (`app/retrieval/query_analyzer.py`)
The query analyzer deterministically extracts regulatory intent into a typed dataclass:
```python
@dataclass
class QueryIntent:
    intent_type: str        # 'current_requirement', 'historical_comparison', 'general_search'
    temporal_scope: str     # 'latest', 'historical', 'all'
    target_category: Optional[str]   # 'Investment Adviser', 'Mutual Funds', etc.
    exact_terms: List[str]  # e.g., ['fee cap', '2.5%']
    confidence: float       # 0.0 to 1.0
```

### 12.2 Implementation Type: Deterministic Rule-Based
- **Why Rule-Based**: In financial compliance, nondeterministic LLM query routing introduces latency (+500ms) and unpredictability. RegIntel utilizes regex keyword patterns and controlled vocabularies.
- **Example Flow**:
  - Input: *"What are the latest SEBI requirements for investment advisers?"*
  - Extracted: `intent_type="current_requirement"`, `temporal_scope="latest"`, `target_category="Investment Adviser"`, `confidence=0.95`.

---

## SECTION 13 — TEMPORAL / CURRENT / LATEST RETRIEVAL

### 13.1 Temporal Scoring & Precedence
When `temporal_scope == 'latest'`:
- Retrieved candidate chunks are boosted using an exponential decay function based on `published_date`:
  $$Score_{boosted} = Score_{base} \\times (1.0 + w_{temporal} \\times e^{-\\lambda \\times \\Delta_{days}})$$
- Circulars explicitly marked as `superseded_by` in the version graph have their rank penalized or are flagged with historical warnings.

### 13.2 Critical Legal Limitation
> [!IMPORTANT]
> **Legal Limitation**: A newer circular does NOT automatically repeal or supersede an older circular in its entirety unless explicit legal language (e.g., *"This circular supersedes circular No..."*) is identified. RegIntel explicitly models this rule and flags amendments versus total repeals.

---

## SECTION 14 — RAG GENERATION PIPELINE

### 14.1 Grounded Synthesis Flow (`app/rag/pipeline.py`)
1. **Evidence Assembly**: Top-5 reranked chunks are formatted with explicit bracketed reference headers:
   ```text
   --- EVIDENCE BLOCK [1] (Circular: SEBI/HO/IMD/DF1/CIR/P/2020/182, Category: Investment Adviser) ---
   <chunk content>
   ```
2. **Strict System Prompt**: The model is instructed:
   - *"Base your answers EXCLUSIVELY on the provided Evidence Blocks."*
   - *"Every factual assertion must cite its source using [1], [2], etc."*
   - *"If the provided evidence is insufficient, state: 'The provided regulatory evidence does not contain sufficient information to answer this query.'"*
3. **Dual Provider Routing**: Primary execution via `GeminiProvider`. If Gemini fails (HTTP 429, 500, or timeout), execution fails over to `OllamaProvider`.

---

## SECTION 15 — LLM PROVIDER ARCHITECTURE

### 15.1 Provider Abstraction (`app/llm/provider.py`)
Both providers implement a unified abstract base class:
```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str) -> LLMResponse:
        pass
```

### 15.2 Providers Implemented
- **`GeminiProvider` (`app/llm/gemini.py`)**: Calls `models/gemini-flash-lite-latest` via Google GenAI SDK.
- **`OllamaProvider` (`app/llm/ollama.py`)**: Calls local HTTP endpoint (`http://localhost:11434/api/generate`) running `gemma4:latest` or `llama3.2`.
- **`FallbackLLMProvider` (`app/llm/fallback.py`)**: Implements circuit-breaker failover logic.
- **Key Architectural Separation**: The generation provider can be swapped between Gemini and Ollama with **zero changes** to the embedding architecture (`gemini-embedding-001`), ensuring vector search indexes remain valid.

---

## SECTION 16 — CITATION AND GROUNDING

### 16.1 Citation Integrity vs Fact Verification
RegIntel strictly distinguishes three levels of validation:
1. **Citation Integrity (Fully Implemented & Automated)**: Verifies that every bracketed token `[N]` in the generated text maps to a valid evidence index $1 \\le N \\le |Evidence|$. If an LLM hallucinates `[9]` when only 5 chunks were retrieved, validation fails.
2. **Citation Support (Benchmarked in Evaluation)**: Verifies that the cited sentence matches key n-grams and entities in the referenced chunk.
3. **Claim-Level Fact Grounding (Evaluated via LLM Judge)**: Independent evaluation judge (`evaluation/grounding_evaluator.py`) verifies that each atomic proposition is fully entailment-supported by the source text.

---

## SECTION 17 — REGULATORY CHANGE DETECTION

### 17.1 Section-Level Delta Engine (`app/change_detection/document_comparator.py`)
Compares two regulatory circulars (e.g., 2020 Guidelines vs 2024 Master Circular) through a 4-tier matching algorithm:
1. **Tier 1 — Exact Clause Code Matching**: Matches clauses with identical numbering (e.g., `"Clause 2.1"` $\\leftrightarrow$ `"Clause 2.1"`).
2. **Tier 2 — Normalized Header Title Matching**: Matches section titles after stripping punctuation and whitespace (e.g., `"Fee Structure"` $\\leftrightarrow$ `"Fees and Charges"`).
3. **Tier 3 — High-Overlap Semantic Matching**: Matches sections sharing high TF-IDF / lexical jaccard overlap.
4. **Tier 4 — Unmatched Classification**: Identifies completely new or discontinued clauses.

### 17.2 Delta Statuses
- **`ADDED`**: Clause exists in Circular B but has no counterpart in Circular A.
- **`REMOVED`**: Clause exists in Circular A but has been omitted in Circular B.
- **`MODIFIED`**: Clause exists in both versions, but substantive legal wording has changed.
- **`UNCHANGED`**: Clause wording is identical or contains only formatting/whitespace differences.

---

## SECTION 18 — DOCUMENT VERSION TRACKING

### 18.1 Supersession Tracker (`app/ingestion/version_tracker.py`)
- **Detection**: Regex scanning for statutory supersession clauses:
  - Pattern: `(?:supersedes|in supersession of|replaces)\\s+(?:circular|notification)\\s+(?:no\\.?\\s*)?([A-Z0-9/-]+)`
- **Graph Nodes & Edges**: Each document maintains:
  - `supersedes`: List of predecessor document IDs/codes repealed by this circular.
  - `superseded_by`: Predecessor records receive a backlink pointing to the newer circular.
  - `relationship_type`: `"SUPERSEDES"`, `"AMENDS"`, or `"INDEPENDENT"`.
  - `relationship_confidence`: `1.0` for explicit statutory text, `0.7` for heuristic category sequence.

---

## SECTION 19 — DOCUMENT COMPARISON

### 19.1 Workflow & API Endpoint (`POST /compare`)
- **Input**: `CompareRequest(document_id_a="...", document_id_b="...")`.
- **Chronological Sorting**: Automatically detects publication dates to designate Circular A as base and Circular B as amendment.
- **Output Schema (`CompareResponse`)**:
  - `executive_summary`: High-level summary of compliance impact.
  - `changes_summary`: Numerical counts (`added`, `modified`, `removed`, `unchanged`, `total`).
  - `sections`: Granular list of `SectionChangeResponse` objects with side-by-side diff text.

---

## SECTION 20 — FRONTEND (REACT + VITE + TYPESCRIPT)

### 20.1 Migration & Current Architecture
The frontend has been completely migrated from the legacy Streamlit prototype to a production-grade single-page application built on:
- **Framework**: React 18, TypeScript 5.5, Vite 5.4.
- **Styling**: Vanilla CSS design system with CSS custom properties (`index.css`), responsive layouts, card components, and badge tokens.
- **Router**: `react-router-dom` v6 with future flags (`v7_startTransition`, `v7_relativeSplatPath`).
- **Error Boundary**: `ErrorBoundary.tsx` wrapping application routes to catch rendering exceptions gracefully.

### 20.2 Application Routes & Pages
1. `/`: **`Home.tsx`** — Executive overview, key metrics, quick search, and recent circulars.
2. `/ask`: **`Ask.tsx`** — Grounded Q&A interface with interactive citation chips and slide-out `CitationDrawer.tsx`.
3. `/compare`: **`Compare.tsx`** — Regulatory comparison workspace with sample pair loader, delta filters, and JSON report exporter.
4. `/latest`: **`Latest.tsx`** — Filterable regulatory document catalog with authority, category, document type, and limit controls.
5. `/search`: **`Search.tsx`** — Multi-method candidate search across Vector, BM25, and Hybrid modes.
6. `/document/:id`: **`DocumentDetail.tsx`** — Complete metadata, full text reader, and version links.
7. `/document/:id/timeline`: **`Timeline.tsx`** — Interactive chronological version lineage graph.
8. `/about`: **`About.tsx`** — Architecture diagrams, benchmark cards, and live backend health indicators.

### 20.3 Client-Side Security Guarantee
Strict inspection confirms that the React frontend contains **zero direct database connections, zero private keys, and zero model credentials**. The browser communicates solely with the FastAPI backend via `apiClient` (`src/api/client.ts`).

---

## SECTION 21 — FASTAPI BACKEND

### 21.1 Architecture & Middleware
- **Entrypoint**: `app/main.py`
- **Middleware**:
  - `correlation_id_middleware`: Generates or propagates `X-Request-ID` across every request.
  - `CORSMiddleware`: Whitelists `http://localhost:5173`, `http://127.0.0.1:5173`.
  - Exception Handlers: Pydantic `422` error formatting, Starlette `404` preservation, and global `500` error masking to prevent stack trace leaks.

### 21.2 Complete REST API Table

| Endpoint | Method | Purpose | Request Body / Query | Response Model |
| :--- | :---: | :--- | :--- | :--- |
| `/health` | `GET` | System health check & dependency status | None | `HealthResponse` |
| `/` | `GET` | Root service metadata & OpenAPI redirect | None | `dict` |
| `/ask` | `POST` | Grounded regulatory question answering | `AskRequest` | `AskResponse` |
| `/search` | `POST` | Multi-method candidate chunk retrieval | `SearchRequest` | `SearchResponse` |
| `/compare` | `POST` | Direct document comparison & delta report | `CompareRequest` | `CompareResponse` |
| `/latest` | `GET` | List recent circulars sorted by date | `source`, `category`, `limit` | `List[DocumentMetadataResponse]` |
| `/document/{id}` | `GET` | Fetch single circular metadata | `document_id` path param | `DocumentMetadataResponse` |
| `/document/{id}/versions`| `GET` | Fetch circular version lineage graph | `document_id` path param | `DocumentVersionResponse` |

---

## SECTION 22 — EVALUATION SYSTEM

### 22.1 Evaluation Harness & Datasets
Located in `evaluation/`, the benchmark harness evaluates retrieval, generation, grounding, and comparison:
- **`retrieval_questions.json`**: 50 curated queries targeting SEBI regulations across 5 categories.
- **`generation_questions.json`**: 30 queries consisting of 20 answerable, 5 partially answerable, and 5 deliberately unanswerable queries.
- **`comparison_cases.json`**: 10 pairwise circular revision comparison benchmarks.
- **`regression_cases.json`**: 3 regression cases verifying hash deduplication, score monotonicity, and failover routing.

### 22.2 Actual Measured Results vs Documentation Claims

> [!WARNING]
> **Mismatch Audit**: Marketing bullets in `docs/resume.md` claim `Recall@5: 92.0%` and `MRR: 0.84`. The **actual measured benchmark results** recorded in `evaluation/results/final_report.md` are documented below:

| Metric Category | Metric Name | Measured Result (Actual Codebase) | Documentation Resume Claim | Status / Notes |
| :--- | :--- | :---: | :---: | :--- |
| **Retrieval** | **Recall@5** | **70.00%** | *92.0%* | Target / Resume claim not reproduced in final_report.md. |
| **Retrieval** | **Recall@10** | **70.00%** | *N/A* | Verified in final_report.md. |
| **Retrieval** | **MRR** | **0.5000** | *0.84* | Verified in final_report.md. |
| **Generation** | **Answer Relevance** | **3.52 / 5.0** | *4.8 / 5.0* | Measured via LLM Judge in final_report.md. |
| **Generation** | **Answer Completeness**| **2.62 / 5.0** | *N/A* | Measured in final_report.md. |
| **Grounding** | **Groundedness Score** | **5.0 / 5.0** | *5.0 / 5.0* | Verified 100% grounded claim rate. |
| **Citation** | **Citation Integrity** | **100.0%** | *100.0%* | Zero hallucinated bracket indices. |
| **Citation** | **Citation Support** | **100.0%** | *100.0%* | All citations substantiated by source chunks. |
| **Abstention**| **Unanswerable Abstention**| **100.0%** | *100.0%* | Successfully refused FDA/FAA/EPA queries. |

---

## SECTION 23 — MLFLOW INTEGRATION

### 23.1 Implementation (`app/observability/mlflow_tracker.py`)
- **Tracking URI**: `sqlite:///C:/Users/Lakshya Arora/Documents/RegIntel Rag/mlruns/mlflow.db`
- **Experiment Name**: `RegIntel-RAG`
- **Logged Parameters**: `embedding_model`, `reranker_model`, `chunk_size`, `top_k`, `temperature`.
- **Logged Metrics**: `recall_at_5`, `mrr`, `avg_latency_ms`, `groundedness_score`.
- **Artifacts**: Summary evaluation markdown reports saved under `mlruns/`.

---

## SECTION 24 — LANGFUSE DISTRIBUTED TRACING

### 24.1 Implementation (`app/observability/langfuse_tracer.py`)
- **11-Span Tracing Hierarchy**:
  `query_analysis` $\\rightarrow$ `query_embedding` $\\rightarrow$ `vector_search` $\\rightarrow$ `bm25` $\\rightarrow$ `hybrid` $\\rightarrow$ `reranker` $\\rightarrow$ `prompt_construction` $\\rightarrow$ `llm_generation` $\\rightarrow$ `citation_validation`.
- **Tracer Overhead**: Measured at **+0.37 ms** execution overhead per request.
- **Privacy Controls**: Prompts and retrieved content capturing disabled by default (`langfuse_capture_prompts=False`, `langfuse_capture_retrieved_content=False`); API keys scrubbed from metadata.

---

## SECTION 25 — INFRASTRUCTURE AND DEPLOYMENT

### 25.1 Current Deployment Status
- **Status**: **DEPLOYMENT CONFIGURED — LIVE PUBLIC DEPLOYMENT NOT VERIFIED**
- **Configuration Evidence**:
  - `render.yaml`: Blueprint configuration for Render web service deploying FastAPI backend.
  - `Dockerfile` & `docker-compose.yml`: Multi-container configuration for backend and frontend.
  - Local verified execution: FastAPI running on `0.0.0.0:8000`, React running on `localhost:5173`.
"""
print("Sections 11 to 25 loaded.")
