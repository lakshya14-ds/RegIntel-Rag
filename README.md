# RegIntel RAG

A Hybrid RAG (Retrieval-Augmented Generation) system for Indian Financial Regulatory Intelligence (SEBI, RBI, etc.).

## Project Structure

```text
regintel-rag/
│
├── app/
│   ├── config.py             # App configuration and environment variables
│   ├── db.py                 # MongoDB client & collection handlers
│   │
│   ├── rag/
│   │   ├── embeddings.py     # Embedding generator
│   │   ├── prompts.py        # Prompt templates
│   │   ├── generator.py      # LLM response generation
│   │   └── pipeline.py       # End-to-end RAG pipeline orchestration
│   │
│   ├── retrieval/
│   │   ├── mongodb_vector.py # Dense vector retrieval using MongoDB
│   │   ├── bm25.py           # Sparse keyword retrieval using BM25
│   │   ├── hybrid.py         # Reciprocal Rank Fusion (RRF) hybrid search
│   │   └── reranker.py       # Cohere/Cross-Encoder reranker
│   │
│   └── ingestion/
│       ├── cleaner.py        # Text preprocessing & normalization
│       ├── metadata.py       # Metadata extraction and structuring
│       └── chunker.py        # Semantic/Recursive chunking
│
├── scraper/
│   ├── sebi_scraper.py       # SEBI circulars/orders scraper
│   └── moneycontrol_scraper.py # Financial news scraper
│
├── data/
│   ├── raw/                  # Scraped raw documents
│   └── processed/            # Cleaned and chunked datasets
│
├── evaluation/
│   ├── questions.json        # Evaluation test dataset
│   ├── retrieval_eval.py     # Hit Rate, MRR, NDCG evaluation
│   └── generation_eval.py    # Faithfulness and Answer Relevancy metrics
│
├── frontend/
│   └── streamlit_app.py      # Streamlit user interface
│
├── tests/                    # Unit and integration tests
├── .env                      # Environment variables
├── .env.example              # Example environment configuration
├── .gitignore
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your API keys and MongoDB connection string.

3. **Run Streamlit Frontend**:
   ```bash
   streamlit run frontend/streamlit_app.py
   ```
