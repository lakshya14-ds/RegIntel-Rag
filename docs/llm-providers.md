# LLM Providers Architecture & Configuration

This document describes the multi-provider LLM generation architecture introduced in Phases 48 & 49 of **RegIntel RAG**.

---

## 1. Architecture Overview

RegIntel RAG cleanly decouples text generation from retrieval and embeddings:

```
                  Question
                     │
                     ▼
             Query Understanding
                     │
                     ▼
         Gemini Query Embeddings (768-d)
                     │
                     ▼
      MongoDB Atlas Vector Search + BM25
                     │
                     ▼
             Hybrid Merge & Fusion
                     │
                     ▼
         BGE Cross-Encoder Reranker
                     │
                     ▼
            Evidence Context Assembly
                     │
                     ▼
           ┌───────────────────┐
           │   LLM Provider    │ ◀── get_llm_provider()
           └─────────┬─────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  GeminiProvider  │    │  OllamaProvider  │
│ (Cloud, Primary) │    │ (Local Offline)  │
└──────────────────┘    └──────────────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
        Citation Integrity Validation
                     │
                     ▼
               Grounded Answer
```

### Key Design Principles:
1. **Gemini Remains Primary**: Gemini (`models/gemini-flash-lite-latest`) remains the default provider for high-throughput, accurate regulatory answering.
2. **Ollama as Offline Fallback**: Ollama allows 100% local, offline generation without sending prompt tokens over external networks.
3. **Configuration-Driven**: Switching between providers or enabling automatic fallback requires only environment variable changes (`.env`), zero code modifications.
4. **Embeddings Separation**: `EMBEDDING_PROVIDER` (Gemini 768-d) and vector retrieval are strictly independent from `LLM_PROVIDER`. Changing the generation backend to Ollama does **not** alter the embedding model or vector indexing.
5. **Shared Grounding & Citation Validation**: All providers reuse the exact same regulatory grounding prompts, evidence contexts, citation extraction regexes, and validation checks.

---

## 2. Environment Configuration

Add or customize the following variables in your `.env` file:

```ini
# =======================================================
# LLM Generation Provider Settings
# =======================================================
# Supported: "gemini" | "ollama" (Default: "gemini")
LLM_PROVIDER=gemini

# Enable transparent failover if primary provider fails (Default: false)
LLM_FALLBACK_ENABLED=false

# Google Gemini Generation Model
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_GENERATION_MODEL=models/gemini-flash-lite-latest

# Ollama Local Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT_SECONDS=30.0

# =======================================================
# Embedding Provider Settings (Independent of LLM)
# =======================================================
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSION=768
```

---

## 3. Local Ollama Setup Guide

Ollama is an external runtime and must be installed separately on your machine.

### Step 1: Install Ollama
- **Windows**: Download the installer from [ollama.com/download/windows](https://ollama.com/download/windows) and run setup.
- **macOS**: Download from [ollama.com/download/mac](https://ollama.com/download/mac) or install via Homebrew: `brew install ollama`.
- **Linux**: Run `curl -fsSL https://ollama.com/install.sh | sh`.

### Step 2: Start the Ollama Service
Ensure the Ollama background daemon is running. By default, it listens on `http://localhost:11434`.

```bash
ollama serve
```

### Step 3: Pull an Instruction-Following Model
Pull any compatible instruction-tuned model of your choice:

```bash
# Recommended compact models:
ollama pull llama3.2
# or
ollama pull mistral
# or
ollama pull qwen2.5:7b
```

### Step 4: Verify Local Availability
You can check local models with the CLI:

```bash
ollama list
```

Or verify with Python:

```python
from app.llm.ollama_provider import OllamaProvider
prov = OllamaProvider()
print("Ollama Available:", prov.is_available())
print("Installed Models:", prov.get_installed_models())
```

### Step 5: Configure Application
Set the following in `.env`:

```ini
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```

---

## 4. Fallback Routing & Observability

When `LLM_FALLBACK_ENABLED=true`:
- If `LLM_PROVIDER=gemini` and Gemini is temporarily unreachable (e.g. 503, network outage), generation automatically routes to `OllamaProvider`.
- The system annotates response metadata:
  ```json
  {
    "fallback_used": true,
    "primary_provider": "gemini",
    "fallback_provider": "ollama"
  }
  ```
- If both providers fail or Ollama is also offline, a clean `LLMUnavailableError` is raised. The system **never** returns empty, corrupted, or fabricated answers.
- Both **Langfuse** traces and **MLflow** runs record the actual generation provider and model name used.

---

## 5. Provider Comparison Benchmark

To systematically evaluate and compare generation quality between Gemini and Ollama on identical retrieval contexts and queries, run:

```bash
python -m evaluation.compare_llm_providers --limit 10
```

### Comparison Artifacts Generated:
All comparison runs persist artifacts under `evaluation/results/llm_providers/run_<timestamp>/`:
- `config.json`: Evaluated parameters, models, and endpoints.
- `summary.json`: Aggregated metrics (Relevance, Groundedness, Citation Integrity, Latency).
- `summary.md`: Clean GitHub-flavored markdown summary table.
- `per_query.json`: Detailed query-by-query breakdown.
