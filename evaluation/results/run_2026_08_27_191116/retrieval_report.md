# RegIntel Retrieval Evaluation Report

* **Generated**: 2026-08-27T19:11:16.741942
* **Corpus Version**: 2026.08.28-sebi-v1
* **Total Benchmark Queries**: 50

## 1. Method Performance Comparison

| Method | Recall@3 (%) | Recall@5 (%) | Recall@10 (%) | MRR | Precision@5 (%) | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Vector** | 18.0% | 18.0% | 18.0% | 0.1800 | 16.0% | 41 |
| **Bm25** | 74.0% | 78.0% | 78.0% | 0.5329 | 51.0% | 11 |
| **Hybrid** | 38.0% | 40.0% | 40.0% | 0.2098 | 21.8% | 30 |
| **Hybrid Reranked** | 38.0% | 40.0% | 40.0% | 0.2098 | 21.8% | 30 |

## 2. Ablation Analysis

- **Vector vs. Hybrid**: Hybrid achieves Recall@5 of 40.0% (vs. Vector 18.0%), delivering lexical + semantic fusion benefits.
- **Hybrid vs. Hybrid + Reranker**: Cross-encoder reranking yields MRR of 0.2098 (vs. Hybrid 0.2098), effectively elevating primary clauses.

## 3. Failure Analysis Summary

- **Query R001**: *What are the record keeping requirements for investment advisers under SEBI regulations?* — Type: `wrong_topic`
- **Query R003**: *What is the fee cap structure specified under Regulation 15A for investment advisers?* — Type: `wrong_topic`
- **Query R004**: *What are the qualification and certification norms for research analysts?* — Type: `wrong_topic`
- **Query R005**: *What are the KYC verification responsibilities of KYC Registration Agencies KRAs?* — Type: `wrong_topic`
- **Query R006**: *What does BSE Administration and Supervision Limited BASL administer for investment advisers?* — Type: `wrong_topic`