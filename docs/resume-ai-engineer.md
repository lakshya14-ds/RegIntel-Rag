# RegIntel RAG — AI Engineer Resume Profile (Phase 55.2)

**Focus**: RAG Architecture, Hybrid Search, Neural Reranking, LLM Provider Failover, Observability, CI/CD, Containerization.

---

## 💼 Project Entry: AI Engineer / LLM Systems Engineer

### **RegIntel RAG — Regulatory Intelligence & Change Analysis System**
*Python | FastAPI | MongoDB Atlas Vector Search | BM25 | PyTorch | Gemini | Ollama | Langfuse | Docker*

- **Hybrid Information Retrieval & Reranking**: Designed and deployed a multi-stage RAG pipeline combining 768d Gemini embeddings (MongoDB Vector Search) with BM25Plus sparse keyword matching via Reciprocal Rank Fusion ($k=60$) and local `BAAI/bge-reranker-v2-m3` neural cross-encoder reranking, elevating **`Recall@5` to 92.0%** (MRR: **0.84**).
- **Multi-Provider LLM Orchestration & Failover**: Architected an abstract LLM provider layer supporting Google Gemini Flash Lite with automated fallback routing to local Ollama (`llama3.2`), preventing service interruptions during cloud rate-limit events with sub-millisecond route switching.
- **Production Tracing & Microservice Backend**: Built a high-performance FastAPI backend with `X-Request-ID` correlation middleware and 11-span hierarchical distributed tracing via Langfuse with minimal runtime overhead (**+0.37 ms**), packaged into a multi-container Docker Compose architecture.
- **Deterministic Citations & Guardrails**: Implemented bracketed citation extraction and validation algorithms enforcing 100% ground-truth traceability and automatic abstention on out-of-scope regulatory queries.
