# Regulatory Document Version Tracking

## 1. Lineage & Predecessor Resolution
RegIntel tracks explicit legal supersession and historical relationships between regulatory circulars without unwarranted legal claims.

### Explicit Supersession Patterns
Scans document text for clauses such as:
- `in supersession of circular...`
- `shall replace circular no...`
- `rescinds circular...`
- `amends earlier circular...`

### Candidate Predecessor Ranking
When explicit clauses are absent, predecessor candidates are ranked using:
1. Authority & Source alignment (`SEBI`)
2. Regulatory Category match (`Investment Adviser`)
3. Title token overlap & Jaccard similarity
4. Chronological order (`published_date <= target_date`)

---

## 2. Version CLI Diagnostics
```bash
python -m app.ingestion.version_tracker --document 69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8
```
