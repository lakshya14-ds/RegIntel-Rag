# RegIntel RAG Evaluation Benchmark

This directory contains the reproducible benchmark evaluation dataset and automated evaluation harnesses for **REGINTEL RAG**.

---

## 1. Dataset Overview

- **Corpus Version**: `2026.08.28-sebi-v1` (20 real processed SEBI circulars/master circulars, 399 structure-aware chunks).
- **Retrieval Benchmark**: `evaluation/dataset/retrieval_questions.json` (50 questions across 10 categories).
- **Generation Benchmark**: `evaluation/dataset/generation_questions.json` (30 questions covering Answerable, Partially Answerable, and Unanswerable queries).
- **Comparison Benchmark**: `evaluation/dataset/comparison_cases.json` (10 real and labeled synthetic comparison pairs).

---

## 2. Question Categories in Retrieval Benchmark

1. **Factual Retrieval** (`R001`–`R005`): Core regulatory obligations, audit timelines, and fee caps.
2. **Exact Regulatory Terminology** (`R006`–`R010`): Specific statutory bodies and abbreviations (`BASL`, `OBPP`, `DDP`, `IoRS`, `TER`).
3. **Circular / Regulation Numbers** (`R011`–`R015`): Slashed circular identifiers (`SEBI/HO/MIRSD/...`) and section references (`Regulation 15A`).
4. **Current Requirements** (`R016`–`R020`): Active compliance duties for intermediaries.
5. **Latest Requirements** (`R021`–`R025`): Recent circulars and updated frameworks.
6. **Effective Dates** (`R026`–`R030`): Temporal questions regarding applicability and deadlines.
7. **Category-Specific Queries** (`R031`–`R035`): Intermediary-specific rules (Mutual Funds, Stock Brokers, Research Analysts, Depositories, IFSC).
8. **Historical Queries** (`R036`–`R040`): Prior circular revisions and superseded provisions.
9. **Source-Specific Queries** (`R041`–`R045`): Authority-specific regulatory mandates.
10. **Difficult Semantic Queries** (`R046`–`R050`): Subtle multi-clause requirements, conflicts of interest, and cross-sector sandbox frameworks.

---

## 3. Evaluation Metrics

### Retrieval:
- **Recall@K** ($K \in \{3, 5, 10\}$): Fraction of queries where at least one expected relevant chunk/document is retrieved in top $K$.
- **MRR (Mean Reciprocal Rank)**: $\frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$ of the first relevant retrieved result.
- **Precision@5**: Average proportion of retrieved top 5 chunks that belong to expected documents.

### Generation:
- **Answer Relevance** (1–5 scale): How directly the generated answer addresses the prompt.
- **Faithfulness / Groundedness** (1–5 scale): Degree to which claims are strictly supported by retrieved context without hallucinations.
- **Citation Integrity Rate**: $\frac{\text{Valid Citations}}{\text{Total Citations}} \times 100\%$.
- **Unsupported Question Handling Rate**: Proportion of unanswerable questions correctly identified with explicit insufficient evidence disclaimer.

---

## 4. How to Run Evaluations

```bash
# Run Retrieval Evaluation across Vector, BM25, Hybrid, and Reranked
python -m evaluation.retrieval_evaluator

# Run Generation / RAG Evaluation
python -m evaluation.generation_evaluator

# Run Full Evaluation Suite
python -m evaluation.run_all
```
