# RegIntel FastAPI Backend Documentation

## 1. Overview
The RegIntel FastAPI backend exposes production-grade regulatory intelligence endpoints for question answering, multi-method search, document comparison, version tracking, and system health checks.

Base URL: `http://localhost:8000`
Interactive Swagger Docs: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`

---

## 2. API Endpoints

### `GET /health`
Performs connection checks against MongoDB Atlas and validates Gemini API key availability.

**Response (200 OK):**
```json
{
  "status": "ok",
  "mongodb": true,
  "embedding_service": true,
  "environment": "production",
  "version": "1.0.0"
}
```

---

### `POST /ask`
Executes end-to-end grounded Regulatory RAG with query understanding, hybrid retrieval, neural reranking, and citation verification.

**Request:**
```json
{
  "question": "What are the record keeping requirements for investment advisers?",
  "top_k": 5,
  "retrieval_mode": "hybrid",
  "category": "Investment Adviser"
}
```

**Response (200 OK):**
```json
{
  "answer": "Under SEBI regulations, every Investment Adviser must maintain records for 8 years [1].",
  "sources": [
    {
      "source_id": 1,
      "chunk_id": "69098d6a..._chunk_003",
      "document_id": "69098d6a...",
      "source": "SEBI",
      "title": "Master Circular for Investment Advisers",
      "section": "Maintenance of Records",
      "published_date": "2024-05-15",
      "effective_date": "2024-05-15",
      "url": "https://www.sebi.gov.in/...",
      "score": 0.8921
    }
  ],
  "query_intent": {
    "query_type": "factual",
    "time_intent": "none",
    "source": "SEBI",
    "category": "Investment Adviser",
    "is_comparison": false
  },
  "sufficient_evidence": true,
  "disclaimer": "Based on indexed regulatory sources. Does not constitute official legal advice."
}
```

---

### `POST /search`
Executes direct retrieval without invoking LLM answer generation.

**Request:**
```json
{
  "query": "Investment Adviser agreement obligations",
  "top_k": 5,
  "retrieval_mode": "hybrid"
}
```

---

### `POST /compare`
Performs structural section-by-section comparison between two regulatory documents.

**Request:**
```json
{
  "document_a_id": "af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab",
  "document_b_id": "69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8"
}
```

---

### `GET /document/{document_id}`
Returns metadata, dates, authority, circular numbers, and version tags for a given document.

---

### `GET /document/{document_id}/versions`
Returns lineage graph metadata (predecessor, successor, candidates, confidence, and status).

---

### `GET /latest`
Lists recent regulatory circulars sorted by publication date. Query parameters: `source`, `category`, `limit`.
