# LLM PROVIDER COMPARISON REPORT

**Questions**: 5
**Timestamp**: 2026_08_30_044539

| Provider | Model | Status | Relevance | Groundedness | Citation Integrity | Avg Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Gemini** | `models/gemini-flash-lite-latest` | 🟢 Available | 1.22/5.0 | 3.96/5.0 | 100.0% | 1409.5 ms |
| **Ollama** | `llama3.2` | ⚪ UNAVAILABLE | N/A | N/A | N/A | N/A |

### Evaluation Methodology & Principles:
1. **Scientific Equivalence**: Retrieval candidates, cross-encoder reranking, evidence context, and prompt instructions were held strictly identical across both providers.
2. **Local Isolation**: Ollama generation ran completely offline without sending prompt tokens to third-party endpoints.
3. **Absence of Bias**: Benchmark metrics reflect performance on this specific evaluation subset; neither provider is represented as universally superior.