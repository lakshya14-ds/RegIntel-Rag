# RAG Pipeline Failure Analysis & Root Cause Diagnosis
**Generated**: 2026-08-29T16:42:56.844738

## 1. Failure Taxonomy Breakdown by Pipeline Stage
| Pipeline Stage | Error Count | Percentage |
| :--- | :--- | :--- |
| **Retrieval** | 15 | 100.0% |
| **Reranking** | 0 | 0.0% |
| **Generation** | 0 | 0.0% |
| **Citation** | 0 | 0.0% |
| **Comparison** | 0 | 0.0% |

## 2. Specific Failure Type Frequency
| Failure Type | Count |
| :--- | :--- |
| `missing_relevant_document` | 15 |

## 3. Top 10 High-Value Error Analysis Cases

### Case 1: Query G003 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What is the Beta Version of T+0 Settlement introduced by SEBI?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['20518434fd1c3354786dc7e3b070553c266321c6f89ca971376d0d1ac64d3b4a'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 2: Query G005 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What is the role of BSE Administration and Supervision Limited BASL?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 3: Query G006 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What are the KYC obligations enforced by KYC Registration Agencies KRAs?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['be8461b8d553b86c321ad3affeac24c3acc57a045768ee24caf48d9d2924cb47'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 4: Query G007 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What is the Inter-Operable Regulatory Sandbox IoRS?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources to explain what the Inter-Operable Regulatory Sandbox (IoRS) is, other than the title referencing a "Standard Operating Procedure...
- **Root Cause**: Expected sources ['1ef425b69756aeab54d52eecd7f9e26b0802ad23c04891eb8e32860e576b1c72'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 5: Query G008 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What are the additional disclosure mandates for high risk Foreign Portfolio Investors?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['b50dcc4966fb18892911ab18c9699431ad365ed2b12ba5d86e03d060a771fda5'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 6: Query G010 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What are the financial disincentives imposed for surveillance related lapses?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['6ca36ed21933573c6cfcf46873a202d604d156dc8fc6af55d0c04394961124ff'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 7: Query G011 [RETRIEVAL - `missing_relevant_document`]
- **Question**: Can an Investment Adviser receive distribution commissions from mutual funds for recommended schemes?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 8: Query G012 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What is the overseas investment framework for Indian Mutual Funds?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['03dd333e09b21448a64bf9aac73fd1fde91b137f36937edf51dee1f99d54e7da', '555ddaa81bc0ec0847a73444a40b7ce65ac7f7c9b44ddd3b9cf0d59e7f86b06b'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 9: Query G013 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What safeguards are required against unauthorized electronic fund transfers?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['6dc7cd6f0e1b0643b116f473b616db61cda6d95bfb006f2c29aa1d385db352c4'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.

### Case 10: Query G014 [RETRIEVAL - `missing_relevant_document`]
- **Question**: What are the operating guidelines for Investment Advisers in IFSC GIFT City?
- **Generated Response**: I could not find sufficient evidence in the indexed regulatory sources....
- **Root Cause**: Expected sources ['384edf54c1afbbf95237706cd2f5ca9f6742a0788056126b70baa6efb193c2c1'] were not retrieved with sufficient similarity score.
- **Suggested Fix**: Refine hybrid BM25 weight or enforce strict prompt refusal for out-of-scope regulatory queries.
