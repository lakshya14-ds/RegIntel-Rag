# Observability & Distributed Tracing: Langfuse & MLflow

RegIntel RAG features enterprise-grade observability and distributed tracing across two specialized observability systems:
1. **Langfuse (Phase 50 & 33)**: Real-time, low-overhead distributed request tracing, hierarchical span breakdown, LLM generation and fallback monitoring, token accounting, error classification, and latency profiling.
2. **MLflow (Phase 32)**: Experiment tracking, metric benchmarking, hyperparameter comparison, and artifact logging for offline evaluations.

---

## 1. Langfuse Request Tracing (Phase 50)

Langfuse provides fine-grained visibility into every step of a regulatory intelligence request:

```
regintel.ask (Root Trace)
├── query_analysis (Tool Span: intent, time intent, category, comparison flag)
├── hybrid_retrieval (Retriever Span: fusion weights, candidate pool)
│   ├── query_embedding (Embedding Span: provider, model, 768 dimensions)
│   ├── vector_search (Retriever Span: MongoDB Vector search)
│   └── bm25_search (Retriever Span: BM25 lexical search)
├── temporal_resolution (Tool Span: date/version boosting)
├── reranker (Tool Span: BGE Cross-Encoder scoring)
├── context_builder (Tool Span: evidence chunks, token estimates)
├── llm_generation (Generation Span: Gemini / Ollama, tokens, latency, fallback status)
└── citation_validation (Tool Span: citations found, validity, integrity score)
```

For change analysis queries:
```
regintel.ask (Root Trace)
├── query_analysis
└── change_detection (Tool Span: version comparison, added/removed/modified counts)
```

For direct candidate search & document comparison:
- `regintel.search`: Candidate search across vector, BM25, hybrid, and reranked modalities.
- `regintel.compare`: Document comparison with structural alignment and delta summaries.

---

## 2. Configuration Reference

All settings can be configured via environment variables in `.env`:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `LANGFUSE_ENABLED` | boolean | `false` | Enable/disable Langfuse live tracing |
| `LANGFUSE_PUBLIC_KEY` | string | `None` | Langfuse Project Public Key (`pk-lf-...`) |
| `LANGFUSE_SECRET_KEY` | string | `None` | Langfuse Project Secret Key (`sk-lf-...`) |
| `LANGFUSE_HOST` | string | `https://cloud.langfuse.com` | Langfuse Server Host (Cloud or Self-Hosted) |
| `LANGFUSE_SAMPLE_RATE` | float | `1.0` | Sampling rate (`0.0` to `1.0`) |
| `LANGFUSE_CAPTURE_PROMPTS` | boolean | `false` | Whether to send raw LLM prompts to Langfuse |
| `LANGFUSE_CAPTURE_RETRIEVED_CONTENT` | boolean | `false` | Whether to send full document text chunks |
| `LANGFUSE_MAX_CONTENT_LENGTH` | integer | `5000` | Max character length for truncated strings |
| `ENVIRONMENT` | string | `production` | Deployment environment tag (`production`, `staging`, `dev`) |

---

## 3. Privacy, Security & Sanitization

RegIntel RAG implements strict automated data governance for all telemetry sent to Langfuse:
1. **Secret & Key Redaction**: API keys (Gemini, OpenAI, Langfuse), MongoDB URIs with passwords, and authorization tokens are automatically sanitized (`[REDACTED]`).
2. **Raw Vector Protection**: Embeddings are never transmitted as raw vector arrays; only metadata (dimensions=768, provider, model) is logged.
3. **Opt-in Content Capturing**: Full document chunk contents and LLM prompt templates are withheld by default (`LANGFUSE_CAPTURE_PROMPTS=false`, `LANGFUSE_CAPTURE_RETRIEVED_CONTENT=false`).
4. **Length Bounding**: Strings exceeding `LANGFUSE_MAX_CONTENT_LENGTH` are safely truncated.

---

## 4. Standardized Error Taxonomy

All exceptions are categorized and recorded with standard error taxonomies:
- `CONFIGURATION_ERROR`: Missing or invalid environment configurations.
- `MONGODB_ERROR`: MongoDB connection, query, or Atlas Vector search failures.
- `EMBEDDING_ERROR`: Gemini embedding generation failures.
- `RETRIEVAL_ERROR`: Hybrid or BM25 retrieval errors.
- `RERANKER_ERROR`: BGE cross-encoder reranking failures.
- `LLM_ERROR`: Gemini / Ollama generation or timeout errors.
- `CITATION_ERROR`: Citation mapping or integrity failures.
- `COMPARISON_ERROR`: Structural document alignment failures.
- `TIMEOUT`: Network or LLM generation timeouts.
- `UNKNOWN_ERROR`: Unhandled system exceptions.

---

## 5. Performance Overhead & Benchmarking

Tracing operates with minimal overhead:
- **Baseline Average Latency (Tracing Disabled)**: ~0.60 ms
- **Traced Average Latency (Tracing Enabled)**: ~0.97 ms
- **Observability Overhead**: **+0.37 ms**

Events are buffered in memory and flushed asynchronously in background worker threads without blocking request processing.

---

## 6. Fail-Safe Guarantee

If Langfuse is disabled, credentials are missing, or the Langfuse server is unreachable, the tracer silently operates in zero-overhead no-op mode (`DummyTrace`, `DummySpan`). Application logic continues unaffected without exceptions.
