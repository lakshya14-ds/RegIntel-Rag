# RegIntel RAG — Final 3-to-5 Minute Demo Script (Phase 52.19)

**Target Audience**: Engineering Leads, Compliance Directors, Hiring Managers  
**Total Duration**: 3 – 5 minutes  
**Tone**: Confident, technical, and compliance-rigorous

---

## 1. Problem Introduction (30 seconds)
> *"Financial regulations published by authorities like SEBI are scattered across hundreds of circulars, frequently supersede older rules, and risk severe penalties if misunderstood. Naive RAG systems fail here because they retrieve outdated circulars, hallucinate penalties, and provide unverified answers. RegIntel RAG is an autonomous regulatory intelligence system engineered for strict compliance rigor."*

---

## 2. Launch & System Overview (30 seconds)
> *"RegIntel features a FastAPI backend, a React + TypeScript + Vite dashboard, a local neural reranker, and dual LLM routing with Gemini and Ollama. Let's open the interface at `http://localhost:5173`."*

---

## 3. Query Answering & Grounded Citations (60 seconds)
1. Navigate to **Ask RegIntel (`/ask`)**.
2. Submit Query:
   > *"What are the latest qualification and record keeping requirements for SEBI Investment Advisers?"*
3. **Showcase**:
   - Query intent parsing (`current_requirement`, `category: Investment Adviser`).
   - Hybrid retrieval (MongoDB Vector + BM25) and local BGE cross-encoder reranking.
   - Grounded answer generated with strict bracketed citations `[1]`, `[2]`.
   - Click on the **Evidence Sources** dropdown to inspect exact matched circular titles, published dates, and section clauses.

---

## 4. Regulatory Version Awareness & Supersession (45 seconds)
1. Submit Query:
   > *"What is the current Master Circular for Investment Advisers?"*
2. **Showcase**:
   - RegIntel's temporal ranking boosts the latest 2024 Master Circular over the superseded 2018/2023 versions.
   - Transparent metadata tag showing `Status: CURRENT` and `Superseded Predecessor detected`.

---

## 5. Automated Regulatory Change Analysis (60 seconds)
1. Navigate to **Tab 2: Compare Circulars**.
2. Select:
   - **Document A**: `SEBI IA Master Circular 2023`
   - **Document B**: `SEBI IA Master Circular 2024`
3. Click **Run Comparison**.
4. **Showcase**:
   - Executive Summary and summary badge counts (e.g. `1 ADDED`, `2 MODIFIED`, `0 REMOVED`, `15 UNCHANGED`).
   - 4-Tier Section Matcher identifying exact clause changes.
   - AI-generated Compliance Impact Summaries for each modified section.

---

## 6. Observability & Quality Architecture (45 seconds)
1. **Showcase Langfuse Trace**:
   - Open Langfuse UI or show the 11-span request trace (`query_analysis` $\rightarrow$ `vector_search` $\rightarrow$ `bm25` $\rightarrow$ `reranker` $\rightarrow$ `llm_generation` $\rightarrow$ `citation_validation`).
   - Mention zero-overhead asynchronous tracing (+0.37 ms).
2. **Showcase Failover Routing**:
   - Point out that if Google Gemini hits rate limits, the system transparently routes to local Ollama (`llama3.2`) without user disruption.

---

## 7. Wrap Up & Summary (15 seconds)
> *"RegIntel RAG turns manual, multi-hour compliance audits into instant, auditable, and mathematically grounded regulatory intelligence. Thank you!"*
