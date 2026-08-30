# Comprehensive Testing Strategy & Quality Assurance Guide (Phase 51)

RegIntel RAG features a multi-tiered, hermetic test suite designed to ensure absolute regulatory precision, zero hallucinated citations, robust document alignment, and high-performance retrieval.

---

## 1. Test Architecture & Structure

```
tests/
├── unit/                       # Fast, hermetic unit tests with 100% mocked external dependencies
│   ├── ingestion/              # Ingestion, cleaning, chunking, hash validation, embedding reuse
│   ├── retrieval/              # Query understanding, BM25, vector search, hybrid RRF, reranking
│   ├── rag/                    # Context assembly, prompt construction, citation extraction
│   ├── versioning/             # Predecessor detection, version lineage, timeline sorting
│   ├── comparison/             # 4-tier section matching, delta classification, diff normalization
│   ├── llm/                    # Gemini provider, Ollama provider, Fallback router
│   ├── observability/          # MLflow logging, Langfuse distributed tracing
│   └── api/                    # FastAPI route handlers, status endpoints
│
├── integration/                # Service integrations gated by environment flags
│   ├── test_mongodb_integration.py     (RUN_MONGODB_INTEGRATION=true)
│   ├── test_gemini_integration.py      (RUN_GEMINI_INTEGRATION=true)
│   ├── test_ollama_integration.py      (RUN_OLLAMA_INTEGRATION=true)
│   └── test_langfuse_integration.py    (RUN_LANGFUSE_INTEGRATION=true)
│
├── e2e/                        # End-to-End workflow tests with synthetic corpora
│   ├── test_full_workflow.py           # Question -> Analysis -> Search -> Rerank -> Generation -> Citation
│   ├── test_comparison_workflow.py     # Doc A + Doc B -> Chronology -> Section Diff -> Report
│   └── test_version_workflow.py        # Version Registration -> Predecessor -> Lineage
│
├── regression/                 # Guardrails preventing quality & metric regressions
│   ├── test_ingestion_regression.py    # Idempotency, content hashing, deduplication
│   ├── test_retrieval_regression.py    # Monotonicity & metric calculation
│   ├── test_generation_regression.py   # Answerability & safe abstention
│   ├── test_citation_regression.py     # Citation validation & out-of-bounds rejection
│   ├── test_provider_regression.py     # Gemini vs Ollama vs Failover routing
│   └── test_observability_regression.py# Zero impact when tracing is disabled
│
├── security/                   # Security & Data Governance
│   └── test_security_contracts.py      # Secret redaction, vector masking, stack trace suppression
│
└── performance/                # Latency & Throughput Micro-Benchmarks
    └── test_performance_benchmarks.py  # BM25, Fusion, Reranker, Pipeline latency
```

---

## 2. Test Execution Commands

### Run Unit Tests (Fast & Offline)
```bash
pytest tests/unit
```

### Run Full Regression Suite
```bash
pytest tests/regression
```

### Run End-to-End Workflows
```bash
pytest tests/e2e
```

### Run Full Test Suite with Coverage
```bash
pytest --cov=app --cov-report=term-missing
```

### Run Live Service Integrations (Requires Active Credentials / Daemons)
```bash
# Enable individual live service tests
RUN_MONGODB_INTEGRATION=true pytest tests/integration/test_mongodb_integration.py
RUN_GEMINI_INTEGRATION=true pytest tests/integration/test_gemini_integration.py
RUN_OLLAMA_INTEGRATION=true pytest tests/integration/test_ollama_integration.py
RUN_LANGFUSE_INTEGRATION=true pytest tests/integration/test_langfuse_integration.py
```

---

## 3. Environment Flags Reference

| Flag | Default | Description |
| :--- | :--- | :--- |
| `RUN_MONGODB_INTEGRATION` | `false` | When true, executes live MongoDB queries & ping |
| `RUN_GEMINI_INTEGRATION` | `false` | When true, invokes live Google Gemini API |
| `RUN_OLLAMA_INTEGRATION` | `false` | When true, connects to local Ollama server |
| `RUN_LANGFUSE_INTEGRATION` | `false` | When true, sends live traces to Langfuse backend |

---

## 4. Key Quality Guardrails

1. **Hermetic by Default**: Standard test execution requires zero external API keys, database credentials, or internet access.
2. **Zero Hallucinated Citations**: Citation mapping strictly validates every `[i]` index against actual retrieved chunk IDs.
3. **Deterministic Content Hashing**: Document identity and chunk identity are rooted in SHA-256 hashes, ensuring idempotent re-ingestion.
4. **Fail-Safe Observability**: Disabling MLflow or Langfuse introduces zero errors and negligible overhead (+0.37 ms).
