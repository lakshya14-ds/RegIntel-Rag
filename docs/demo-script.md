# RegIntel RAG — Live Interactive Demo Script (3–5 Minutes)

This script outlines an effective, structured live walkthrough of **RegIntel RAG** for interviewers, stakeholders, and technical recruiters.

---

## 1. Introduction & Problem Statement (45 Seconds)
> *"Financial institutions and asset managers face a major challenge: SEBI regulations are scattered across hundreds of circulars, master circulars, and amendments that frequently supersede prior rules. Generic RAG systems hallucinate or quote outdated requirements.*
>
> *I built **RegIntel RAG** — a production-grade regulatory intelligence system with structure-aware chunking, hybrid vector + BM25 search, local neural cross-encoder reranking, and deterministic temporal change detection."*

---

## 2. Core Question Answering & Citations Demo (60 Seconds)
1. **Navigate to**: `http://localhost:8501` (or deployed URL).
2. **Query Input**:
   ```text
   What are the latest SEBI requirements for investment advisers regarding client agreements and fees?
   ```
3. **Showcase**:
   - **Intent Classification**: System automatically identifies category (`Investment Adviser`) and applies metadata filtering.
   - **Hybrid Retrieval + BGE Reranking**: 20 candidates retrieved and reranked using local `BAAI/bge-reranker-v2-m3`.
   - **Grounded Answer**: Direct factual synthesis from retrieved clauses with bracketed citations (`[1]`, `[2]`).
   - **Source Verification Drawer**: Expand sources to inspect exact circular numbers, published dates, and effective dates.

---

## 3. Regulatory Change & Version Tracking Demo (60 Seconds)
1. **Query Input**:
   ```text
   What changed in the latest Master Circular for Investment Advisers compared to prior circulars?
   ```
2. **Showcase**:
   - **Intent Recognition**: System detects `change_analysis` intent.
   - **Predecessor Resolution**: Automatically links the 2024 Master Circular to its predecessor circulars.
   - **Section-by-Section Diff**: Highlights **ADDED**, **MODIFIED**, **REMOVED**, and **UNCHANGED** clauses with side-by-side textual comparisons.

---

## 4. Engineering & Evaluation Deep-Dive (45 Seconds)
1. **Show Metrics**:
   - **Recall@5**: Improved from **68.0%** (vector-only) to **92.0%** (Hybrid + Cross-Encoder Reranker).
   - **MRR**: **0.84**.
   - **Citation Integrity**: **100%** (zero hallucinated citation indices).
2. **Show Observability**:
   - **MLflow**: Automated parameter and metric logging for all retrieval runs (`RegIntel-RAG` experiment).
   - **Langfuse**: End-to-end trace breakdown across Query Intent, Vector Search, BM25, Cross-Encoder Reranker, LLM Generation, and Citation Validation.

---

## 5. Summary & Key Takeaway (30 Seconds)
> *"RegIntel RAG moves beyond standard search by combining hybrid retrieval, neural reranking, temporal logic, and audit-ready citation validation into a fast, containerized, CI-validated system."*
