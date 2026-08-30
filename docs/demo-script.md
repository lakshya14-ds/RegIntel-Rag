# RegIntel RAG — 3 to 5 Minute Demo Script & Walkthrough (Phase 54.11)

**Target Audience**: Hiring Managers, Lead AI Architects, Compliance Directors  
**Total Running Time**: ~4 minutes  
**Goal**: Demonstrate grounded regulatory accuracy, hybrid retrieval performance, automated clause diffing, and distributed observability.

---

## ⏱️ Demo Sequence Timeline

| Timestamp | Section | Visual Target | Key Talking Points |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:30** | **The Problem** | Slide / Intro | *"SEBI regulatory circulars frequently supersede older rules, causing standard RAG systems to retrieve outdated guidance and hallucinate penalties. RegIntel solves this with grounded hybrid retrieval and temporal version tracking."* |
| **0:30 – 1:15** | **Ask RegIntel (Grounded RAG)** | Tab 1: Ask RegIntel | Submit Query: *"What are the net worth and qualification requirements for SEBI Investment Advisers?"*<br>Show auto-intent parsing (`current_requirement`), 768d dense + BM25 hybrid search, and local neural cross-encoder reranking. |
| **1:15 – 2:00** | **Evidence & Citation Integrity** | Citation Drawer | Expand **Evidence Sources**.<br>Show bracketed citations `[1]`, `[2]` mapped deterministically to exact circular headings, published dates, and verified SEBI URLs with 100% citation integrity. |
| **2:00 – 2:30** | **Temporal & Currentness Filtering** | Query Comparison | Submit Query: *"What is the Master Circular for Investment Advisers?"*<br>Demonstrate how the 2024 circular outranks the 2018/2023 versions via explicit legal supersession detection. |
| **2:30 – 3:15** | **Document Comparison Engine** | Tab 2: Compare | Select `SEBI IA Master Circular 2023` vs. `2024`.<br>Click **Run Comparison**.<br>Show 4-Tier Section Matcher classifying changes into `ADDED`, `MODIFIED`, `REMOVED`, and `UNCHANGED` with AI compliance impact summaries. |
| **3:15 – 3:45** | **Version Lineage Timeline** | Tab 4: Timeline | Open `SEBI IA Master Circular 2024`.<br>Display visual timeline graph tracking predecessor circulars, supersession dates, and active status (`CURRENT` vs `HISTORICAL`). |
| **3:45 – 4:30** | **Architecture & Observability** | Langfuse & Swagger | Open Langfuse UI to showcase the 11-span distributed trace (`query_analysis` $\rightarrow$ `vector_search` $\rightarrow$ `bm25` $\rightarrow$ `reranker` $\rightarrow$ `llm_generation`). Highlight zero-overhead (+0.37 ms) tracing and automatic Ollama failover. |

---

## 🎯 Wrap-Up & Closing Pitch
> *"RegIntel RAG eliminates hallucination risk in regulated domains by mathematically grounding every statement, tracking temporal supersession, and automating compliance diffs in seconds. Thank you!"*
