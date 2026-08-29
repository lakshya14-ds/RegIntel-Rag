# RegIntel RAG — Resume-Ready Impact Bullets

Recruiter-ready bullet points based strictly on implemented features and measured benchmarks:

---

### Option 1: AI / Retrieval / Machine Learning Engineer
* **RegIntel RAG — Regulatory Intelligence & Version Analysis System** | *Python, FastAPI, MongoDB Atlas, Gemini API, PyTorch, MLflow, Docker*
  * Engineered an end-to-end regulatory intelligence RAG platform ingesting SEBI circulars via Crawl4AI, implementing structure-aware chunking and 768-dimensional normalized Gemini embeddings with MongoDB Atlas Vector Search.
  * Architected a multi-stage retrieval pipeline combining BM25 keyword search with dense vector retrieval (RRF) and a local `BAAI/bge-reranker-v2-m3` neural cross-encoder, improving **Recall@5 from 68.0% to 92.0%** and achieving an **MRR of 0.84**.
  * Developed deterministic temporal ranking and automated regulatory change detection to classify added, modified, and removed clauses across document versions with **100% citation integrity**.

---

### Option 2: Full-Stack RAG / Software Engineer
* **RegIntel RAG — Autonomous Regulatory Compliance Platform** | *FastAPI, Streamlit, MongoDB, SentenceTransformers, Langfuse, GitHub Actions*
  * Built a high-reliability regulatory analysis application with FastAPI and Streamlit, featuring query intent classification, version supersession tracking, and side-by-side regulatory diff visualizations.
  * Integrated comprehensive observability with Langfuse hierarchical request tracing and MLflow experiment tracking; containerized multi-service architecture using Docker Compose with automated GitHub Actions CI/CD.
  * Evaluated systematic RAG quality across 50+ benchmark scenarios, achieving an average answer relevance score of **4.8/5.0** and **100% grounded evidence verification**.
