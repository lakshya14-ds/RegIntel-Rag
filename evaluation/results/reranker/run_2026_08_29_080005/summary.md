# Neural Cross-Encoder Reranker Evaluation Report

**Model**: `BAAI/bge-reranker-v2-m3` | **Device**: `CPU` | **Evaluated Questions**: `50`

---

## 1. Hybrid vs Hybrid + Reranker Performance

| Retrieval Method | Recall@3 | Recall@5 | Recall@10 | MRR | Precision@5 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Hybrid Baseline** | 0.1800 | 0.1800 | 0.1800 | 0.1500 | 0.0960 |
| **Hybrid + BGE Reranker** | **0.2000** | **0.2000** | **0.2000** | **0.1800** | **0.0960** |

- **Candidate Pool Recall@20**: `0.2000`
- **Ranking Shift**: `1` queries improved, `0` worsened, `49` unchanged (Net Gain: **+1**).

---

## 2. Latency Breakdown

| Stage | Average Latency |
| :--- | :---: |
| **Hybrid Candidate Retrieval** | `920.52 ms` |
| **BGE Cross-Encoder Reranking** | `23055.27 ms` |
| **Total Retrieval Pipeline** | `23975.80 ms` (p95: `29564.14 ms`) |

---

## 3. Candidate Pool Size Ablation

| Candidate Pool Size | Recall@5 | Candidate Recall | MRR | Reranker Latency |
| :--- | :---: | :---: | :---: | :---: |
| **10 Candidates** | 0.1800 | 0.1800 | 0.1440 | 11577.22 ms |
| **20 Candidates (Default)** | **0.2000** | **0.2000** | **0.1800** | **23055.27 ms** |
| **30 Candidates** | 0.2800 | 0.2800 | 0.2217 | 35372.92 ms |

---

## 4. Top-K Output Size Ablation

| Top-K Chunks | Recall | MRR | Total Latency |
| :--- | :---: | :---: | :---: |
| **k = 3** | 0.2000 | 0.1800 | 23975.80 ms |
| **k = 5 (Default)** | **0.2000** | **0.1800** | **23975.80 ms** |
| **k = 10** | 0.2000 | 0.1800 | 23975.80 ms |
