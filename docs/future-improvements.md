# RegIntel RAG — Future Improvements & Technical Roadmap

Proposed architectural and feature extensions for future iterations:

---

### 1. Multi-Regulator Ingestion & Expansion
- Ingest and index guidelines from the Reserve Bank of India (RBI), Insurance Regulatory and Development Authority of India (IRDAI), and International Financial Services Centres Authority (IFSCA).

### 2. Temporal Regulatory Knowledge Graph
- Transition from linear document predecessor chains to an explicit Neo4j / NetworkX graph of regulatory clauses, enabling multi-hop amendment traversal and point-in-time legal reconstruction.

### 3. Claim-Level Factuality & Citation Verification
- Implement NLI (Natural Language Inference) models to verify claim-to-sentence entailment for every individual sentence in the generated compliance summary.

### 4. GPU-Accelerated Real-Time Neural Serving
- Package `bge-reranker-v2-m3` via Triton Inference Server or ONNX Runtime with INT8 quantization, reducing reranking latency below 30ms on CPU/Edge instances.

### 5. Multilingual Regulatory Support
- Leverage multilingual cross-encoders and embeddings to index vernacular regulatory circulars and regional gazette notifications across Indian languages (Hindi, Marathi, Gujarati, etc.).

### 6. Enterprise Role-Based Access & Audit Logs
- Implement OAuth2 / JWT authentication, role-based access control, and tamper-proof immutable audit logs for compliance department reporting.
