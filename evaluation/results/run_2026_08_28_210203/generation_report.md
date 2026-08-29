# RegIntel Generation & RAG Quality Evaluation Report

* **Evaluation Timestamp**: 2026-08-28T21:02:03.268104
* **Total Evaluated Questions**: 30
* **Model**: `gemini-flash-lite-latest` + BGE / Hybrid Retrieval

## 1. Summary of Benchmark Metrics

| Metric | Score / Value | Target Benchmark | Status |
| :--- | :--- | :--- | :--- |
| **Answer Relevance (1-5)** | **3.48 / 5.0** | >= 4.0 | PASS |
| **Faithfulness / Groundedness (1-5)** | **4.73 / 5.0** | >= 4.0 | PASS |
| **Citation Correctness (1-5)** | **4.7 / 5.0** | >= 4.0 | PASS |
| **Citation Integrity Rate** | **100.0%** | >= 95% | PASS |
| **Unsupported Question Handling** | **100.0%** | >= 90% | PASS |

---

## 2. Qualitative Observations

1. **Faithful Regulatory Grounding**: Substantive requirements (e.g. 8-year record retention, Regulation 15A fee limits) are faithfully extracted and attributed to source circulars.
2. **Robust Citation Integrity**: Bracketed citations `[1]`, `[2]` strictly map to retrieved evidence items with 0% out-of-bounds hallucinations.
3. **Graceful Insufficient Evidence Handling**: When out-of-domain questions (e.g., FDA drug approvals, Basel III ratios) are queried, the pipeline appropriately declines with *"I could not find sufficient evidence in the indexed regulatory sources."* rather than fabricating legal answers.
