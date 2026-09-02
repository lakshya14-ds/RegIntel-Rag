# RegIntel RAG — Production Deployment & Troubleshooting Guide (Phase 53)

This guide documents the production deployment architecture, step-by-step cloud deployment workflows, and comprehensive troubleshooting protocols for running **RegIntel RAG** on public hosting environments.

---

## 1. Production Deployment Topology

```text
       ┌───────────────────────────────────────────────────────────┐
       │                       PUBLIC USER                         │
       └─────────────────────────────┬─────────────────────────────┘
                                     │
                                     ▼
       ┌───────────────────────────────────────────────────────────┐
       │     STATIC HOSTING / DOCKER NGINX (React Frontend UI)     │
       │     - VITE_API_BASE_URL: https://<backend-url>            │
       └─────────────────────────────┬─────────────────────────────┘
                                     │ HTTPS REST API
                                     ▼
       ┌───────────────────────────────────────────────────────────┐
       │          RENDER / DOCKER CONTAINER (FastAPI Backend)      │
       │          - Host: 0.0.0.0, Port: $PORT                     │
       │          - CORS_ALLOWED_ORIGINS: https://<frontend-url>   │
       └──────────────┬──────────────┬──────────────┬──────────────┘
                      │              │              │
           Vector API │    LLM API   │  Tracing API │
                      ▼              ▼              ▼
       ┌─────────────────┐ ┌───────────────┐ ┌──────────────┐
       │  MongoDB Atlas  │ │ Google Gemini │ │   Langfuse   │
       │  Vector Search  │ │ API (Flash)   │ │  Cloud Obs   │
       └─────────────────┘ └───────────────┘ └──────────────┘
```

---

## 2. Step-by-Step Free-Tier Deployment Strategy

### A. Database: MongoDB Atlas (Free M0 Cluster)
1. Create a free M0 cluster on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. **Network Access**: Add `0.0.0.0/0` (Allow Access from Anywhere) so cloud container instances can connect dynamically.
3. **Database User**: Create a read/write user and copy the connection string: `mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/`.
4. Ensure the Vector Search index `vector_index_chunk` is created as documented in [`docs/mongodb-vector-index.md`](file:///C:/Users/Lakshya%20Arora/Documents/RegIntel%20Rag/docs/mongodb-vector-index.md).

### B. Backend: FastAPI on Render / Railway / Hugging Face Spaces (Docker)
1. Link your GitHub repository to [Render](https://render.com) or [Railway](https://railway.app).
2. Select **Docker Environment** (uses root [`Dockerfile`](file:///C:/Users/Lakshya%20Arora/Documents/RegIntel%20Rag/Dockerfile)).
3. Configure the following environment variables in the provider dashboard:
   ```bash
   APP_ENV=production
   DEBUG=false
   PORT=8000
   FASTAPI_HOST=0.0.0.0
   GEMINI_API_KEY=AIzaSy...
   MONGODB_URI=mongodb+srv://...
   MONGODB_DB_NAME=regintel_db
   MONGODB_COLLECTION=raw_documents
   MONGODB_CHUNKS_COLLECTION=document_chunks
   CORS_ALLOWED_ORIGINS=https://<your-frontend-domain>.com
   LLM_PROVIDER=gemini
   LLM_FALLBACK_ENABLED=false
   ENABLE_RERANKER=true
   RERANKER_DEVICE=cpu
   LANGFUSE_ENABLED=false
   MLFLOW_ENABLED=false
   ```
4. Deploy the service and verify health at `https://<your-backend>.onrender.com/health`.

### C. Frontend: Static Hosting (Vercel, Netlify, Render, or Docker Nginx)
1. Build production static assets:
   ```bash
   cd frontend
   npm run build
   ```
2. Set environment variable during build:
   ```env
   VITE_API_BASE_URL=https://<your-backend>.onrender.com
   ```
3. Deploy the `frontend/dist` directory or use the provided `frontend/Dockerfile` for containerized Nginx serving.
4. Verify all routes: Overview, Ask, Compare, Catalog, Search, Timeline, and About.

---

## 3. Comprehensive Troubleshooting Matrix

| Issue Category | Symptom | Root Cause | Solution |
| :--- | :--- | :--- | :--- |
| **Backend Startup** | Container crashes with `Port binding failed` | Hardcoded port `8000` instead of reading cloud `$PORT` | RegIntel reads `os.getenv("PORT") or os.getenv("FASTAPI_PORT", "8000")`. Ensure Docker CMD binds to `0.0.0.0`. |
| **Frontend Connectivity** | Frontend shows `Backend Unavailable (503 / ConnectionError)` | `VITE_API_BASE_URL` defaults to `localhost:8000` | Set `VITE_API_BASE_URL=https://<backend-domain>` during frontend build. |
| **CORS Block** | Browser console logs `CORS policy: No 'Access-Control-Allow-Origin' header` | Frontend origin is missing from backend `CORS_ALLOWED_ORIGINS` | Add the exact frontend origin URL (e.g. `http://localhost:5173` or `https://regintel.app`) to backend `CORS_ALLOWED_ORIGINS`. |
| **MongoDB Atlas** | `MongoDBConnectionError: connection timeout` | Atlas IP whitelist blocks cloud container IP | Add `0.0.0.0/0` in Atlas **Network Access $\rightarrow$ IP Access List**. |
| **Gemini Quota** | HTTP 429 `Resource Exhausted` | Free-tier rate limits reached during high-concurrency requests | RegIntel includes exponential backoff retry. For local deployments, enable `LLM_FALLBACK_ENABLED=true` to route to local Ollama. |
| **Free-Tier Sleep / Cold Start** | First request takes 30–50s | Free-tier platforms (Render/Koyeb) spin down containers after 15 min idle | Normal behavior on free tier. Document cold start transparently; subsequent queries complete in <1.5s. |
| **Out-of-Memory (OOM)** | Container killed during model load | CPU neural reranker (`bge-reranker-v2-m3`) exceeds 512MB RAM | RegIntel uses lazy single-instance initialization. On minimal 512MB RAM tiers, set `ENABLE_RERANKER=false` to use fast vector+BM25 RRF fusion. |
| **Accidental Ingestion Exposure** | High cloud resource consumption from scrapers | Ingestion pipeline exposed publicly | Ingestion is restricted to CLI scripts ([`scraper/`](file:///C:/Users/Lakshya%20Arora/Documents/RegIntel%20Rag/scraper) & [`app/ingestion/pipeline.py`](file:///C:/Users/Lakshya%20Arora/Documents/RegIntel%20Rag/app/ingestion/pipeline.py)) and is not exposed as a public API route. |

---

## 4. Free-Tier Resource & Security Protections

1. **Query Length Bounds**: FastAPI rejects questions exceeding 1,000 characters with HTTP 422.
2. **Retrieval Candidate Capping**: `top_k` parameter is strictly bounded between 1 and 20.
3. **Citation Validation Gate**: Prevents hallucinated numbers without re-querying external APIs.
4. **Secret Scrubbing**: All API error responses suppress stack traces and scrub API keys and database URIs.
5. **Deterministic Ingestion Hashing**: Pre-computes SHA-256 hashes to prevent redundant embedding generation and write cycles.
