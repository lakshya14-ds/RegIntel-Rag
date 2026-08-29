# Automated Regulatory Document Ingestion

## 1. Pipeline Overview
The RegIntel ingestion pipeline incrementally crawls, canonicalizes, deduplicates, cleans, chunks, embeds, and indexes regulatory documents from authorities like SEBI.

```
Candidate Document
       │
       ▼
Deterministic Document ID & Content Hashing
       │
       ├── Content Hash Matches Existing -> UNCHANGED (Skip processing & embeddings)
       │
       ├── Document Not Found -> NEW (Process -> Chunk -> Embed -> Index -> Version)
       │
       └── Content Changed -> CHANGED (Re-process -> Re-embed affected chunks -> Update version)
```

---

## 2. Ingestion Commands

### Discover & Preview (Dry Run)
```bash
python -m app.ingestion.pipeline --source sebi --limit 10 --dry-run
```

### Controlled Batch Processing
```bash
python -m app.ingestion.pipeline --source sebi --limit 20
```

### Full Ingestion Run
```bash
python -m app.ingestion.pipeline --source sebi
```

---

## 3. Idempotency & Chunk Cache
- **Deterministic Document IDs**: SHA-256 generated from normalized canonical URL.
- **Content Hash**: SHA-256 computed on whitespace-normalized text.
- **Embedding Cache**: If `chunk_id` and `content_hash` match existing records in store, embedding generation is skipped automatically.
