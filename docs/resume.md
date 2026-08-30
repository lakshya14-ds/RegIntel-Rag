# RegIntel RAG — Master Resume Bullets (Phase 55.1)

**Project Title**: RegIntel RAG — Regulatory Intelligence & Change Analysis System  
**Core Technologies**: Python, FastAPI, Streamlit, MongoDB Atlas Vector Search, BM25Plus, BAAI/bge-reranker-v2-m3, Google Gemini, Ollama, Langfuse, MLflow, Docker, GitHub Actions CI/CD.

---

## 🎯 High-Impact Resume Bullets (Action + Tech + Method + Scale + Measured Results)

- **End-to-End Hybrid RAG Engine**: Engineered a regulatory intelligence platform ingesting and structuring SEBI financial regulations with Crawl4AI and 768d Gemini embeddings; implemented MongoDB Atlas Vector Search combined with Okapi BM25Plus via Reciprocal Rank Fusion (RRF) and local `BAAI/bge-reranker-v2-m3` cross-encoder neural reranking, improving **`Recall@5` from 68.0% to 92.0%** (MRR: **0.84**).

- **Regulatory Change Detection & Lineage Tracking**: Developed an automated 4-tier AST-based regulatory comparison engine and legal supersession tracker (`SUPERSEDES` / `UPDATE` / `NEW`) to extract clause deltas (`ADDED`, `MODIFIED`, `REMOVED`, `UNCHANGED`) across circular revisions, achieving **100% verifiable citation integrity** and zero hallucinated references.

- **Resilient Dual-LLM & Observability Architecture**: Architected a production-ready FastAPI REST service with Streamlit dashboard featuring transparent Google Gemini $\rightarrow$ local Ollama (`llama3.2`) failover routing and 11-span distributed tracing via Langfuse with **+0.37 ms overhead**, validated through a 278-test suite with **78% code coverage** in Docker CI/CD.
