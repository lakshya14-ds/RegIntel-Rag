# RegIntel RAG — GitHub Repository Summary & Description

### Short Repository Description
> AI-powered regulatory intelligence system for SEBI compliance: Features structure-aware ingestion, Hybrid BM25 + Vector Search, local BGE cross-encoder reranking, regulatory change detection, and 100% grounded citations.

### Repository Topics / Tags
`rag`, `regulatory-compliance`, `sebi`, `fastapi`, `streamlit`, `mongodb-atlas`, `vector-search`, `bm25`, `cross-encoder`, `reranking`, `mlflow`, `langfuse`, `docker`, `gemini-api`

---

### Highlights Section for GitHub
- **Multi-Stage Hybrid Search**: Dense Vector (Gemini 768d) + BM25 keyword retrieval fused via Reciprocal Rank Fusion (RRF).
- **Neural Cross-Encoder Reranking**: Locally executed `BAAI/bge-reranker-v2-m3` optimizing top-5 evidence chunks.
- **Regulatory Change & Version Analysis**: Clause alignment algorithm detecting **ADDED**, **MODIFIED**, **REMOVED**, and **UNCHANGED** clauses across document revisions.
- **Auditable Citation Verification**: 100% citation index grounding guaranteeing zero hallucinated regulatory claims.
- **Production-Ready Observability & CI**: Tracing with Langfuse, experiment tracking with MLflow, multi-service Docker Compose, and GitHub Actions CI.
