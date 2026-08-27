"""
MongoDB Atlas Vector Search Retrieval Module.

Executes vector similarity search using MongoDB's $vectorSearch aggregation pipeline,
with 768-dimensional normalized query embeddings generated via Google GenAI SDK.
Includes in-memory fallback for local offline evaluation.
"""

import os
import math
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from pymongo.collection import Collection

from app.config import settings
from app.db import get_chunks_collection
from app.rag.embeddings import embed_query, validate_embedding, normalize_embedding

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Configurable Retrieval Constants
VECTOR_INDEX_NAME = "vector_index"
DEFAULT_TOP_K = 5
DEFAULT_NUM_CANDIDATES = 100


class RetrievedChunk(BaseModel):
    """Normalized internal data structure for a retrieved regulatory document chunk."""
    chunk_id: str
    document_id: str
    title: Optional[str] = None
    content: str
    section: Optional[str] = None
    source: str
    category: Optional[str] = None
    document_type: Optional[str] = None
    published_date: Optional[str] = None
    effective_date: Optional[str] = None
    url: str
    score: float = Field(default=0.0)


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two numeric vectors: (A . B) / (||A|| ||B||)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return dot / (norm_a * norm_b)


class MongoDBVectorRetriever:
    """
    Retrieves top-k relevant regulatory chunks from MongoDB Atlas using Vector Search ($vectorSearch).
    """

    def __init__(
        self,
        collection: Optional[Collection] = None,
        index_name: str = VECTOR_INDEX_NAME,
        default_top_k: int = DEFAULT_TOP_K,
        default_num_candidates: int = DEFAULT_NUM_CANDIDATES
    ):
        self._collection = collection
        self.index_name = index_name
        self.default_top_k = default_top_k
        self.default_num_candidates = default_num_candidates

    @property
    def collection(self) -> Optional[Collection]:
        if self._collection is None:
            try:
                self._collection = get_chunks_collection()
            except Exception as e:
                logger.warning(f"Could not connect to MongoDB Atlas chunks collection: {e}")
                self._collection = None
        return self._collection

    def _fallback_local_search(
        self,
        query_vector: List[float],
        limit: int,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """
        In-memory fallback vector search over local data/processed/chunks/ JSON files.
        Guarantees reliable local testing when MongoDB Atlas is offline.
        """
        chunks_dir = settings.chunks_data_dir
        chunk_files = list(chunks_dir.glob("*_chunks.json"))
        scored_candidates: List[RetrievedChunk] = []

        for cf in chunk_files:
            try:
                with open(cf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for c in data.get("chunks", []):
                    emb = c.get("embedding")
                    if not emb or len(emb) != len(query_vector):
                        continue

                    # Apply optional filter
                    if filter_dict:
                        match = True
                        for k, v in filter_dict.items():
                            if c.get(k) != v:
                                match = False
                                break
                        if not match:
                            continue

                    score = compute_cosine_similarity(query_vector, emb)
                    retrieved = RetrievedChunk(
                        chunk_id=c.get("chunk_id", ""),
                        document_id=c.get("document_id", ""),
                        title=c.get("title"),
                        content=c.get("content", ""),
                        section=c.get("section"),
                        source=c.get("source", "SEBI"),
                        category=c.get("category"),
                        document_type=c.get("document_type"),
                        published_date=c.get("published_date"),
                        effective_date=c.get("effective_date"),
                        url=c.get("url", ""),
                        score=round(score, 4)
                    )
                    scored_candidates.append(retrieved)
            except Exception as e:
                logger.error(f"Error reading local chunk file {cf.name}: {e}")

        # Sort descending by cosine similarity
        scored_candidates.sort(key=lambda x: x.score, reverse=True)
        return scored_candidates[:limit]

    def search(
        self,
        query_vector: List[float],
        limit: Optional[int] = None,
        num_candidates: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """
        Executes MongoDB Atlas $vectorSearch aggregation pipeline.
        Falls back to local cosine search if MongoDB Atlas is unavailable.
        """
        top_k = limit or self.default_top_k
        candidates = num_candidates or self.default_num_candidates

        # 1. Validate query vector
        if len(query_vector) != 768:
            raise ValueError(f"Query vector must have exactly 768 dimensions, got {len(query_vector)}")

        # Ensure normalized
        query_vector = normalize_embedding(query_vector)

        # 2. Build MongoDB $vectorSearch pipeline
        vector_search_stage: Dict[str, Any] = {
            "index": self.index_name,
            "path": "embedding",
            "queryVector": query_vector,
            "numCandidates": max(candidates, top_k * 2),
            "limit": top_k
        }
        if filter_dict:
            vector_search_stage["filter"] = filter_dict

        pipeline = [
            {"$vectorSearch": vector_search_stage},
            {
                "$project": {
                    "_id": 0,
                    "chunk_id": 1,
                    "document_id": 1,
                    "title": 1,
                    "content": 1,
                    "section": 1,
                    "source": 1,
                    "category": 1,
                    "document_type": 1,
                    "published_date": 1,
                    "effective_date": 1,
                    "url": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        # 3. Try executing against live MongoDB Atlas
        if self.collection is not None and not getattr(self, "_mongo_offline", False):
            try:
                cursor = self.collection.aggregate(pipeline)
                results = []
                for doc in cursor:
                    results.append(RetrievedChunk(
                        chunk_id=doc.get("chunk_id", ""),
                        document_id=doc.get("document_id", ""),
                        title=doc.get("title"),
                        content=doc.get("content", ""),
                        section=doc.get("section"),
                        source=doc.get("source", "SEBI"),
                        category=doc.get("category"),
                        document_type=doc.get("document_type"),
                        published_date=doc.get("published_date"),
                        effective_date=doc.get("effective_date"),
                        url=doc.get("url", ""),
                        score=round(float(doc.get("score", 0.0)), 4)
                    ))
                if results:
                    return results
            except Exception as e:
                self._mongo_offline = True
                logger.warning(f"MongoDB Atlas $vectorSearch unavailable or failed ({e}). Falling back to local vector search.")

        # Fallback to local stored chunks
        return self._fallback_local_search(query_vector, limit=top_k, filter_dict=filter_dict)

    def search_with_metadata_filter(
        self,
        query_vector: List[float],
        filter_dict: Dict[str, Any],
        limit: Optional[int] = None,
        num_candidates: Optional[int] = None
    ) -> List[RetrievedChunk]:
        """Runs vector search with a specific metadata filter dictionary."""
        return self.search(query_vector=query_vector, limit=limit, num_candidates=num_candidates, filter_dict=filter_dict)

    def retrieve(
        self,
        query_text: str,
        limit: Optional[int] = None,
        num_candidates: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedChunk]:
        """
        Embeds user query using RETRIEVAL_QUERY and executes vector search.
        """
        if not query_text or not query_text.strip():
            raise ValueError("Query text cannot be empty.")

        # Generate 768-dim normalized RETRIEVAL_QUERY embedding
        query_vector = embed_query(query_text.strip())
        return self.search(
            query_vector=query_vector,
            limit=limit,
            num_candidates=num_candidates,
            filter_dict=filter_dict
        )


def verify_existing_data(chunks_dir: Optional[Path] = None, collection: Optional[Collection] = None) -> Dict[str, Any]:
    """
    Diagnostics tool for verifying chunk dataset, embedding presence, and dimensions.
    """
    c_dir = chunks_dir or settings.chunks_data_dir
    chunk_files = list(c_dir.glob("*_chunks.json"))

    total_chunks = 0
    with_embeddings = 0
    without_embeddings = 0
    invalid_embeddings = 0
    dims_seen = set()

    for cf in chunk_files:
        try:
            with open(cf, "r", encoding="utf-8") as f:
                data = json.load(f)
            for chunk in data.get("chunks", []):
                total_chunks += 1
                emb = chunk.get("embedding")
                if emb is None:
                    without_embeddings += 1
                elif isinstance(emb, (list, tuple)):
                    dim = len(emb)
                    dims_seen.add(dim)
                    if dim == 768:
                        with_embeddings += 1
                    else:
                        invalid_embeddings += 1
                else:
                    invalid_embeddings += 1
        except Exception as e:
            logger.error(f"Error reading {cf.name}: {e}")

    dims_str = ", ".join(str(d) for d in sorted(dims_seen)) if dims_seen else "None"

    print("\n" + "=" * 45)
    print("Vector Search Data Diagnostics")
    print("-" * 45)
    print(f"Total chunk files checked   : {len(chunk_files)}")
    print(f"Total chunks               : {total_chunks}")
    print(f"Chunks with embeddings     : {with_embeddings}")
    print(f"Chunks without embeddings  : {without_embeddings}")
    print(f"Invalid embeddings         : {invalid_embeddings}")
    print(f"Observed dimensions        : {dims_str}")
    print("=" * 45 + "\n")

    return {
        "total_chunks": total_chunks,
        "with_embeddings": with_embeddings,
        "without_embeddings": without_embeddings,
        "invalid_embeddings": invalid_embeddings,
        "dimensions": dims_seen
    }


if __name__ == "__main__":
    verify_existing_data()
