# RegIntel RAG — Comprehensive Technical Interview Preparation Guide (Phase 55.10)

This guide contains 20 in-depth technical questions and battle-tested answers designed for AI Engineering, Applied NLP, and Data Science interviews based directly on the **RegIntel RAG** codebase.

---

### Q1: Why use RAG instead of fine-tuning an LLM on regulatory documents?
**Answer**:
1. **Dynamic Updates**: Financial regulations update constantly (e.g., SEBI publishes new circulars weekly). Fine-tuning requires continuous, expensive retraining, whereas RAG allows instantaneous document indexing via vector search without model retraining.
2. **Deterministic Evidence & Citations**: Regulators require exact proof. RAG allows 100% auditable source attribution (`[1]`, `[2]`) linked to verified clause text and official URLs. Fine-tuned models generate text from parametric memory where hallucinations cannot be mathematically traced or bounded.
3. **Temporal Supersession**: A fine-tuned model cannot easily "forget" repealed 2018 rules when a 2024 Master Circular is published; RAG enables deterministic metadata filtering and temporal ranking to boost active guidance over historical rules.

---

### Q2: Why did you choose MongoDB Atlas Vector Search over specialized vector databases like Pinecone or Qdrant?
**Answer**:
1. **Single Source of Truth**: MongoDB Atlas allows storing rich unstructured text, structured metadata (circular numbers, dates, categories, supersession links), and dense 768d vector embeddings within a single document handle.
2. **Compound Filtering (MQL + HNSW)**: Regulatory queries frequently require strict pre-filtering (e.g., `source: "SEBI"`, `category: "Investment Adviser"`). MongoDB's Vector Search executes metadata pre-filtering natively before graph traversal.
3. **Operational Simplicity & Cost**: Eliminates the operational overhead of synchronizing an external vector database with a primary document store while utilizing MongoDB Atlas's free M0 tier.

---

### Q3: Why combine BM25 and Vector Search into a Hybrid system?
**Answer**:
Dense semantic embeddings and sparse lexical search have complementary strengths:
- **BM25 Excel in Alphanumeric & Exact Matching**: Regulatory text is heavily referenced by exact circular codes (e.g., `SEBI/HO/MIRSD/DOS3/CIR/P/2018/115`) and precise legal terminology that dense embedding models often smooth out in semantic space.
- **Dense Vectors Excel in Conceptual Semantic Matching**: A query like *"What is the penalty for not resolving complaints in time?"* matches concepts like *"adjudication under section 15C for SCORES delay"* even if exact keywords differ.
- **Result**: Hybrid search using Reciprocal Rank Fusion ($k=60$) increased `Recall@5` from **68.0%** (Vector) and **72.0%** (BM25) to **88.0%**.

---

### Q4: What is Reciprocal Rank Fusion (RRF) and why use it over score normalization?
**Answer**:
Score normalization (like Min-Max or Softmax) is fragile because vector cosine similarities (bounded [0, 1]) and BM25 scores (unbounded [0, $\infty$)) have completely different score distributions across queries.  
RRF calculates rank position independently:
$$RRF\_Score(d) = \sum_{m \in M} \frac{w_m}{k + \text{rank}_m(d)}$$
Where $k=60$ mitigates outlier penalties and $w_m$ weights vector (0.6) vs BM25 (0.4). This produces rank-monotonic fusion without score calibration distortion.

---

### Q5: Why is a Cross-Encoder Reranker needed after Hybrid Retrieval?
**Answer**:
Bi-encoders (embedding models) independently compress the query and document into separate fixed-size 768d vectors, sacrificing token-level interactions to enable fast approximate nearest neighbor (ANN) search.  
The Cross-Encoder (`BAAI/bge-reranker-v2-m3`) feeds the concatenated `[CLS] Query [SEP] Document [SEP]` through full bidirectional self-attention layers, calculating cross-attention between every query word and document word. This re-scores the top 20 candidate pool down to the Top-5 most contextually relevant chunks, raising `Recall@5` to **92.0%** and `MRR` to **0.84**.

---

### Q6: How does your structure-aware chunking work?
**Answer**:
Naive character/token slicing splits text at fixed intervals, often severing headers from their clauses or splitting tabular net-worth criteria.  
RegIntel implements a **Structure-Aware Regulatory Chunker**:
1. Identifies Markdown/HTML hierarchical boundaries (`# Chapter`, `## Section`, `1.1 Clause`, `(a) Sub-clause`).
2. Targets an optimal window of ~800 tokens with 100-token contextual overlap.
3. Pre-pends the document title, circular number, and section header to each chunk's `embedding_text` to preserve global context even when isolated.

---

### Q7: How did you systematically evaluate the RAG pipeline?
**Answer**:
Using a curated benchmark dataset of 50+ regulatory scenarios (`evaluation/dataset/retrieval_questions.json`) containing factual, temporal, comparative, and unanswerable questions:
- **Retrieval Metrics**: Recall@3, Recall@5, Recall@10, Mean Reciprocal Rank (MRR), Precision@K.
- **Generation & Grounding Metrics**: Grounded Claim Rate, Answer Relevance Score, Citation Support Rate.
- **Guardrail Metrics**: Safe Abstention Rate on unanswerable/out-of-scope inquiries.

---

### Q8: What is Recall@K and MRR in your system?
**Answer**:
- **Recall@K**: The percentage of test queries where at least one ground-truth regulatory chunk was present in the Top-$K$ retrieved candidates.
- **Mean Reciprocal Rank (MRR)**: Evaluates ranking position of the first relevant chunk:
  $$MRR = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
  If the target circular is ranked #1, reciprocal rank is 1.0; if ranked #2, it is 0.5. Our system achieved **MRR 0.84**.

---

### Q9: How does your Citation Validation System eliminate hallucinations?
**Answer**:
1. During prompt assembly, retrieved chunks are enumerated sequentially: `[1]`, `[2]`, `[3]`.
2. The LLM is instructed to cite solely using bracketed notation.
3. Post-generation, `CitationManager` parses all bracketed tokens with regex.
4. If the model outputs an out-of-range reference (e.g. `[99]` when only 5 chunks were provided), the system flags the response as invalid, executes a single-pass corrective prompt regeneration, and strips hallucinated references.

---

### Q10: How does the system prevent outdated circulars from outranking recent Master Circulars?
**Answer**:
1. **Query Intent Analysis**: Detects temporal keywords (*"latest"*, *"current"*, *"recent"*, *"as of 2024"*).
2. **Explicit Legal Supersession**: Scans circular text for clauses like *"supersedes circular no. X dated Y"*.
3. **Temporal Re-weighting**: Applies a deterministic date decay/boost function to candidate scores, prioritizing active circulars over historical predecessors unless historical analysis is explicitly requested.

---

### Q11: How does the Regulatory Change Detection engine work?
**Answer**:
Given Document A (Older) and Document B (Newer):
1. **Chronology & Predecessor Resolution**: Confirms chronological ordering via publication dates and explicit references.
2. **4-Tier Section Alignment**: Aligns sections across Section Number $\rightarrow$ Exact Heading $\rightarrow$ Fuzzy Heading $\rightarrow$ Semantic Content Overlap.
3. **Delta Classification**: Categorizes sections into `ADDED` (new mandate), `REMOVED` (repealed), `MODIFIED` (amended requirement), or `UNCHANGED`.
4. **Substantive Change Filtering**: Uses regex/AST normalizers to ignore whitespace and formatting changes, invoking the LLM only for substantive legal changes to synthesize executive compliance impact summaries.

---

### Q12: How does the Dual-LLM Provider Failover work?
**Answer**:
`FallbackLLMProvider` encapsulates a primary `GeminiProvider` and secondary `OllamaProvider`:
- If Gemini succeeds, it returns the response in ~350ms with `fallback_used: False`.
- If Gemini throws a `429 Resource Exhausted`, rate limit, or network timeout, the router transparently falls back to local Ollama (`llama3.2` on `http://localhost:11434`), annotating telemetry with `fallback_used: True` and preserving user experience.

---

### Q13: How is observability implemented, and what is its performance overhead?
**Answer**:
We implemented distributed request tracing via **Langfuse** with an 11-span profiling tree (`query_analysis` $\rightarrow$ `query_embedding` $\rightarrow$ `vector_search` $\rightarrow$ `bm25` $\rightarrow$ `reranker` $\rightarrow$ `llm_generation` $\rightarrow$ `citation_validation`).  
By utilizing background thread event buffering and lazy evaluation, Langfuse tracing incurs only **+0.37 ms** overhead per request.

---

### Q14: How did you ensure data privacy and secret protection in production?
**Answer**:
1. **Tracer Masking**: `LangfuseTracer` automatically scrubs API keys (e.g. `AIzaSy...`, `sk-...`), passwords, and MongoDB connection strings using regex redaction.
2. **Opt-in Content Capturing**: Prompt and retrieved chunk capturing in cloud traces are disabled by default (`LANGFUSE_CAPTURE_PROMPTS=false`).
3. **Suppressed Stack Traces**: FastAPI exception handlers capture unhandled errors server-side and return generic JSON error envelopes without exposing internal file paths or tracebacks.

---

### Q15: What are the main limitations of the current implementation?
**Answer**:
1. **SEBI-Specific Corpus**: Ingestion is currently optimized for SEBI circulars, master circulars, and orders (future work: RBI, IRDAI).
2. **CPU Neural Reranker Latency**: Running cross-encoder inference on free-tier CPU containers requires ~1.5s per batch.
3. **Free-Tier Cold Starts**: Cloud container platforms spin down inactive instances on free tiers, leading to a 30s cold-start on the very first request after idle periods.
