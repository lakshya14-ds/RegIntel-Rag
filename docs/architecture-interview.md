# RegIntel RAG — 2-Minute Architecture Interview Pitch (Phase 55.11)

**Role**: AI Engineer / Applied RAG Architect  
**Objective**: Deliver a crisp, compelling 2-minute architectural explanation of the **RegIntel RAG** system to hiring managers or technical leads.

---

## 🎙️ The 2-Minute Architecture Script

> *"RegIntel RAG is an end-to-end regulatory intelligence platform engineered to eliminate hallucinations, handle temporal supersession, and automate compliance diffing across financial regulations."*

### 1. Ingestion & Embedding Pipeline (15 Seconds)
> *"We scrape unstructured SEBI regulatory circulars using Crawl4AI, clean boilerplate noise, and perform structure-aware chunking aligned with legal headings. We embed chunks with Google Gemini 768-dimensional normalized embeddings and index them in MongoDB Atlas along with full document metadata."*

### 2. Multi-Stage Hybrid Retrieval & Reranking (30 Seconds)
> *"When a user queries the system, we first classify the query intent. We then execute a two-pronged search: dense semantic vector search via MongoDB Vector Search for conceptual meaning, and sparse BM25Plus keyword search for exact circular codes and penalty clauses. We combine the top 20 candidates using Reciprocal Rank Fusion, apply temporal weighting to prioritize active rules, and pass them to a local Cross-Encoder (`BAAI/bge-reranker-v2-m3`) for deep cross-attention. This multi-stage pipeline elevates `Recall@5` to **92.0%** with an **MRR of 0.84**."*

### 3. Grounded Synthesis & Citation Validation (25 Seconds)
> *"The Top-5 reranked evidence chunks are injected into Gemini Flash Lite with strict grounded prompting. Post-generation, our Citation Manager verifies that every single bracketed citation maps to a real retrieved chunk with 100% integrity, stripping any hallucinated references."*

### 4. Regulatory Change & Temporal Engine (20 Seconds)
> *"Beyond search, our 4-tier section comparison engine automatically aligns clauses between circular revisions, categorizing requirements into ADDED, MODIFIED, REMOVED, and UNCHANGED, saving compliance teams dozens of hours of manual audit work."*

### 5. Resilient Microservices & Observability (20 Seconds)
> *"The system is wrapped in a FastAPI REST backend and Streamlit UI, with automatic fallback from Gemini to local Ollama (`llama3.2`), and full 11-span distributed tracing via Langfuse with only **+0.37 ms** overhead."*
