# RegIntel RAG — REST API Reference (Phase 54.12)

The **RegIntel RAG** backend exposes a OpenAPI-compliant FastAPI service on port `8000`.

---

## 1. `GET /health`
- **Description**: Returns operational health status, database connectivity, and environment metadata.
- **Query Parameters**: None

### Response (`200 OK`)
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "production",
  "mongodb": true,
  "embedding_service": true
}
```

---

## 2. `POST /ask`
- **Description**: Executes the complete grounded Regulatory RAG pipeline (Query Analysis $\rightarrow$ Dense & Sparse Retrieval $\rightarrow$ Cross-Encoder Reranking $\rightarrow$ LLM Answer Generation $\rightarrow$ Citation Verification).

### Request Payload
```json
{
  "question": "What are the net worth and qualification requirements for SEBI Investment Advisers?",
  "top_k": 5,
  "retrieval_mode": "hybrid",
  "category": "Investment Adviser"
}
```

### Response (`200 OK`)
```json
{
  "question": "What are the net worth and qualification requirements for SEBI Investment Advisers?",
  "answer": "An individual investment adviser must maintain a minimum net worth of INR 50 Lakhs [1] and possess relevant postgraduate qualifications and NISM certifications [2].",
  "sources": [
    {
      "source_id": 1,
      "chunk_id": "sebi_ia_master_2024_chk_002",
      "document_id": "sebi_ia_master_2024",
      "title": "Master Circular for Investment Advisers",
      "section": "Capital Adequacy and Net Worth Requirements",
      "published_date": "2024-05-24",
      "effective_date": "2024-05-24",
      "url": "https://www.sebi.gov.in/legal/master-circulars/may-2024/ia.html",
      "score": 0.942
    },
    {
      "source_id": 2,
      "chunk_id": "sebi_ia_master_2024_chk_003",
      "document_id": "sebi_ia_master_2024",
      "title": "Master Circular for Investment Advisers",
      "section": "Qualification and Certification Requirements",
      "published_date": "2024-05-24",
      "effective_date": "2024-05-24",
      "url": "https://www.sebi.gov.in/legal/master-circulars/may-2024/ia.html",
      "score": 0.915
    }
  ],
  "query_intent": {
    "query_type": "current_requirement",
    "time_intent": "latest",
    "category": "Investment Adviser",
    "circular_number": null,
    "is_comparison": false
  },
  "sufficient_evidence": true,
  "execution_time_ms": 780.5,
  "llm_provider": "gemini",
  "llm_model": "models/gemini-flash-lite-latest",
  "fallback_used": false
}
```

---

## 3. `POST /search`
- **Description**: Multi-method evidence search across regulatory chunks (Vector, BM25, or Hybrid).

### Request Payload
```json
{
  "query": "SCORES grievance redressal timeline",
  "top_k": 3,
  "retrieval_mode": "hybrid"
}
```

### Response (`200 OK`)
```json
{
  "query": "SCORES grievance redressal timeline",
  "total_results": 3,
  "retrieval_mode": "hybrid",
  "results": [
    {
      "chunk_id": "sebi_scores_cir_2024_chk_001",
      "document_id": "sebi_scores_cir_2024",
      "title": "Master Circular on Online Resolution of Disputes",
      "section": "Grievance Redressal Mechanism",
      "content": "All registered intermediaries shall resolve complaints received via SCORES portal within 21 calendar days.",
      "score": 0.895,
      "published_date": "2024-05-24",
      "url": "https://www.sebi.gov.in/scores.html",
      "source": "SEBI",
      "category": "Market Intermediaries"
    }
  ]
}
```

---

## 4. `POST /compare`
- **Description**: Direct 4-Tier section-by-section comparison between two regulatory documents.

### Request Payload
```json
{
  "document_a_id": "sebi_ia_master_2023",
  "document_b_id": "sebi_ia_master_2024"
}
```

### Response (`200 OK`)
```json
{
  "status": "SUCCESS",
  "older_document": {
    "document_id": "sebi_ia_master_2023",
    "title": "Master Circular for Investment Advisers 2023",
    "published_date": "2023-05-15"
  },
  "newer_document": {
    "document_id": "sebi_ia_master_2024",
    "title": "Master Circular for Investment Advisers 2024",
    "published_date": "2024-05-24"
  },
  "document_order_confidence": "high",
  "version_relationship": "UPDATE",
  "added_count": 1,
  "modified_count": 2,
  "removed_count": 0,
  "unchanged_count": 14,
  "total_changes": 3,
  "executive_summary": "The 2024 Master Circular updates capital adequacy requirements and mandates enhanced cybersecurity compliance.",
  "changes": [
    {
      "section": "Capital Adequacy",
      "heading": "Minimum Net Worth Criteria",
      "change_type": "MODIFIED",
      "substantive_change": true,
      "summary": "Net worth requirement increased from 25 Lakhs to 50 Lakhs for non-individual IAs.",
      "impact": "Mandatory recapitalization required for corporate advisory firms.",
      "old_source": {
        "document_id": "sebi_ia_master_2023",
        "section_id": "sec_cap_2023",
        "heading": "Net Worth Requirements"
      },
      "new_source": {
        "document_id": "sebi_ia_master_2024",
        "section_id": "sec_cap_2024",
        "heading": "Minimum Net Worth Criteria"
      }
    }
  ]
}
```

---

## 5. `GET /latest`
- **Description**: Returns recently published and currently active regulatory documents.
- **Query Parameters**:
  - `limit`: integer (default: `10`, max: `50`)
  - `category`: optional string filter (e.g. `Investment Adviser`)

---

## 6. `GET /document/{id}/versions`
- **Description**: Retrieves full version lineage timeline, predecessors, and legal supersession status for a circular.

### Response (`200 OK`)
```json
{
  "document_id": "sebi_ia_master_2024",
  "title": "Master Circular for Investment Advisers 2024",
  "status": "current",
  "timeline": [
    {
      "document_id": "sebi_ia_master_2018",
      "title": "Master Circular for Investment Advisers 2018",
      "published_date": "2018-07-13",
      "relationship": "SUPERSEDED",
      "is_current": false
    },
    {
      "document_id": "sebi_ia_master_2024",
      "title": "Master Circular for Investment Advisers 2024",
      "published_date": "2024-05-24",
      "relationship": "SUPERSEDES",
      "is_current": true
    }
  ]
}
```
