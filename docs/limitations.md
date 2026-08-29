# RegIntel RAG — System Limitations & Boundary Conditions

Transparently documenting technical, operational, and domain limitations of the current implementation:

---

### 1. SEBI-Centric Initial Corpus
- **Limitation**: The initial corpus focuses specifically on SEBI circulars, master circulars, and regulatory updates for Investment Advisers, Mutual Funds, Stock Brokers, and Market Infrastructure.
- **Impact**: Queries regarding other financial regulators (e.g. RBI, IRDAI, PFRDA, SEC, FCA) will return an intentional "Insufficient Evidence" response.

### 2. Free-Tier API Rate Limits
- **Limitation**: Gemini 2.5 Flash / Flash-Lite operates on free-tier RPM/RPD quotas (e.g., 15 requests per minute).
- **Impact**: High-frequency bulk evaluation or concurrent user queries trigger adaptive exponential backoff sleep intervals.

### 3. CPU Cross-Encoder Latency
- **Limitation**: Running `BAAI/bge-reranker-v2-m3` on CPU incurs higher latency (~1.5–2.5s per query over a 20-candidate pool) compared to GPU inference (~80ms).
- **Mitigation**: Implemented candidate caching, batched inference, PyTorch CPU multithreading (8 threads), and maximum sequence length truncation (384 tokens).

### 4. Conservative Predecessor Detection
- **Limitation**: Regulatory supersession detection relies on explicit textual circular citations, title similarity matching, and publication timeline heuristics.
- **Impact**: Indirect amendments or unreferenced regulatory modifications may require manual correlation.

### 5. Legal Advisory Disclaimer
- **Limitation**: While answers are strictly grounded in authoritative regulatory circulars with 100% citation integrity, the system is designed for compliance assistance and does not constitute formal legal counsel.
