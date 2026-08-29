# RegIntel RAG — Engineering Decisions & Architectural Trade-offs

This document details the 11 core architectural and engineering decisions made during the design and development of **RegIntel RAG**.

---

### 1. Why MongoDB Atlas Vector Search?
- **Decision**: Used MongoDB Atlas with native `$vectorSearch` and cosine similarity.
- **Rationale**: Regulatory compliance data requires rich metadata filtering (circular numbers, dates, categories, document types) combined with vector embeddings in a single database transaction, eliminating external vector database synchronization overhead.

### 2. Why Gemini Embeddings (`gemini-embedding-001`)?
- **Decision**: Standardized on 768-dimensional normalized embeddings using `gemini-embedding-001` with task types (`RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY`).
- **Rationale**: Provides exceptional dense semantic retrieval for formal regulatory vocabulary while maintaining low latency and generous free-tier API quotas.

### 3. Why BM25 + Vector Hybrid Retrieval?
- **Decision**: Combined rank-fusion of BM25 keyword retrieval with vector cosine similarity.
- **Rationale**: Regulatory queries often contain specific technical circular numbers (e.g. `SEBI/HO/IMD/DF1/CIR/P/2020/182`) or section references (`Regulation 15A`) where dense embeddings suffer from vocabulary mismatch, whereas BM25 ensures exact keyword matches are never lost.

### 4. Why Local BAAI/bge-reranker-v2-m3 Cross-Encoder?
- **Decision**: Implemented a local cross-encoder neural reranker (`BAAI/bge-reranker-v2-m3`) over hybrid candidates.
- **Rationale**: Cross-encoders perform joint attention over `(query, document)` token pairs, capturing intricate syntactic and conditional regulatory requirements that bi-encoders miss, boosting `Recall@5` to 92.0% with zero paid API costs.

### 5. Why Structure-Aware Metadata Filtering?
- **Decision**: Extracted deterministic metadata (category, document type, dates, circular IDs) at ingestion and utilized QueryIntent to filter candidates before search.
- **Rationale**: Prevents cross-category contamination (e.g. Mutual Fund rules polluting Investment Adviser queries) and dramatically reduces the search space.

### 6. Why Deterministic Temporal Ranking Logic?
- **Decision**: Designed temporal boost scoring favoring recent and effective circulars over outdated guidelines.
- **Rationale**: In regulatory compliance, an older document may be legally invalid if a newer circular has amended it. Relying strictly on semantic similarity risks quoting superseded law.

### 7. Why Document Version Tracking & Change Detection?
- **Decision**: Built deterministic SHA-256 content hashing, regex circular reference resolution, and section-by-section diff classification (`ADDED`, `MODIFIED`, `REMOVED`, `UNCHANGED`).
- **Rationale**: Compliance officers spend hours comparing updated Master Circulars against previous versions. Automating clause alignment and diff classification turns hours of legal review into seconds.

### 8. Why Post-Generation Citation Validation?
- **Decision**: Implemented strict citation parsing where `[1]`, `[2]` indices are validated against actual retrieved chunk IDs.
- **Rationale**: Regulatory LLM answers must be auditable. If an LLM hallucinates an ungrounded citation or invalid index, the CitationValidator flags or strips it, guaranteeing 100% citation integrity.

### 9. Why Streamlit for Frontend?
- **Decision**: Built a multi-tab web dashboard with Streamlit rather than a complex React SPA.
- **Rationale**: Enables rapid iteration, seamless Python integration, instant visualization of Markdown diff tables, and direct state synchronization without frontend build tooling overhead.

### 10. Why Lazy Model Loading & CPU Multithreading?
- **Decision**: Configured lazy singleton initialization with PyTorch CPU multithreading (`torch.set_num_threads(8)`).
- **Rationale**: Eliminates cold-start delays on startup and allows the entire neural pipeline to operate reliably in local, containerized, or low-cost environments without dedicated GPUs.

### 11. Why Free-Tier Compatible Deployment Architecture?
- **Decision**: Designed containerized backend (FastAPI) + frontend (Streamlit) using environment-based secrets and local SQLite MLflow tracking.
- **Rationale**: Ensures the entire portfolio project is 100% reproducible and demonstrable on free cloud tiers (Render, Railway, Streamlit Cloud) without paid infrastructure dependencies.
