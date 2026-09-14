import logging
from typing import Optional, Dict, Any, List
from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.db import get_collection, get_chunks_collection, MongoDBConnectionError
from app.ingestion.models import RegulatoryDocument, DocumentChunk, to_mongo

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Handles persistence and retrieval of processed regulatory documents and chunks in MongoDB."""

    def __init__(self, collection: Optional[Collection] = None, chunks_collection: Optional[Collection] = None):
        self._collection = collection
        self._chunks_collection = chunks_collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection()
        return self._collection

    @property
    def chunks_collection(self) -> Collection:
        if self._chunks_collection is None:
            self._chunks_collection = get_chunks_collection()
        return self._chunks_collection

    # -------------------------------------------------------------
    # Document Level Methods
    # -------------------------------------------------------------
    def create_metadata_indexes(self) -> List[str]:
        """
        Creates necessary single and compound indexes on metadata fields for fast document retrieval.
        Does NOT create vector search indexes (reserved for Phase 14).
        """
        try:
            coll = self.collection
            created = []
            
            # Unique index on deterministic document_id
            created.append(coll.create_index([("document_id", ASCENDING)], unique=True, name="idx_document_id_unique"))
            
            # Metadata filter indexes
            created.append(coll.create_index([("source", ASCENDING)], name="idx_source"))
            created.append(coll.create_index([("category", ASCENDING)], name="idx_category"))
            created.append(coll.create_index([("document_type", ASCENDING)], name="idx_document_type"))
            created.append(coll.create_index([("published_date", ASCENDING)], name="idx_published_date"))
            created.append(coll.create_index([("effective_date", ASCENDING)], name="idx_effective_date"))
            created.append(coll.create_index([("url", ASCENDING)], name="idx_url"))

            # Compound index for source + category + published_date
            created.append(coll.create_index(
                [("source", ASCENDING), ("category", ASCENDING), ("published_date", ASCENDING)],
                name="idx_source_category_date"
            ))

            logger.info("MongoDB document metadata indexes created successfully")
            return created
        except (PyMongoError, Exception) as e:
            logger.error(f"Failed to create MongoDB document indexes: {e}")
            raise MongoDBConnectionError(f"Error creating metadata indexes: {e}") from e

    def document_exists(self, document_id: str) -> bool:
        """Checks if a document with the given document_id already exists in MongoDB."""
        if getattr(self, "_is_offline", False):
            return False
        try:
            return self.collection.count_documents({"document_id": document_id}, limit=1) > 0
        except Exception as e:
            self._is_offline = True
            logger.warning(f"MongoDB connection offline during document_exists: {e}")
            return False

    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a document by its deterministic document_id."""
        if getattr(self, "_is_offline", False):
            return None
        try:
            return self.collection.find_one({"document_id": document_id})
        except Exception as e:
            self._is_offline = True
            logger.warning(f"MongoDB connection offline during get_document_by_id: {e}")
            return None

    def get_document(self, document_id: str) -> Optional[RegulatoryDocument]:
        """Fetches a RegulatoryDocument model instance by its deterministic document_id."""
        data = self.get_document_by_id(document_id)
        if data:
            from app.ingestion.models import from_mongo
            return from_mongo(RegulatoryDocument, data)
        return None

    def list_documents(
        self,
        source: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Lists documents from MongoDB matching optional metadata filters."""
        if getattr(self, "_is_offline", False):
            return []
        try:
            query: Dict[str, Any] = {}
            if source and source.strip() and source.strip() != "All":
                query["source"] = {"$regex": f"^{source.strip()}$", "$options": "i"}
            if category and category.strip() and category.strip() != "All":
                query["category"] = {"$regex": category.strip(), "$options": "i"}

            return list(self.collection.find(query, {"_id": 0}).limit(limit))
        except Exception as e:
            self._is_offline = True
            logger.warning(f"Error querying documents from MongoDB in list_documents: {e}")
            return []

    def save_document(self, document: RegulatoryDocument) -> str:
        """
        Upserts a processed regulatory document into MongoDB.
        Uses document_id as the unique key to prevent duplicate records.
        """
        doc_dict = to_mongo(document)
        document_id = document.document_id

        try:
            self.collection.update_one(
                {"document_id": document_id},
                {"$set": doc_dict},
                upsert=True
            )
            logger.debug(f"Document {document_id} saved/updated successfully in MongoDB")
            return document_id
        except (PyMongoError, Exception) as e:
            logger.error(f"Failed to save document {document_id} to MongoDB: {e}")
            raise MongoDBConnectionError(f"Failed to save document: {e}") from e

    # -------------------------------------------------------------
    # Chunk Level Methods (Phases 11 & 13)
    # -------------------------------------------------------------
    def create_chunk_indexes(self) -> List[str]:
        """
        Creates indexes on the chunks collection for fast filtering and deduplication.
        Does NOT create a vector search index (reserved for Phase 14).
        """
        try:
            coll = self.chunks_collection
            created = []
            
            # Unique index on chunk_id
            created.append(coll.create_index([("chunk_id", ASCENDING)], unique=True, name="idx_chunk_id_unique"))
            
            # Document and metadata filter indexes
            created.append(coll.create_index([("document_id", ASCENDING)], name="idx_chunk_doc_id"))
            created.append(coll.create_index([("source", ASCENDING)], name="idx_chunk_source"))
            created.append(coll.create_index([("category", ASCENDING)], name="idx_chunk_category"))
            created.append(coll.create_index([("document_type", ASCENDING)], name="idx_chunk_type"))
            created.append(coll.create_index([("published_date", ASCENDING)], name="idx_chunk_published_date"))
            created.append(coll.create_index([("effective_date", ASCENDING)], name="idx_chunk_effective_date"))
            
            # Compound index for document_id + chunk_index
            created.append(coll.create_index(
                [("document_id", ASCENDING), ("chunk_index", ASCENDING)],
                name="idx_chunk_doc_and_index"
            ))

            # Index on content_hash for fast embedding reuse (Phase 55.11)
            created.append(coll.create_index([("content_hash", ASCENDING)], name="idx_chunk_content_hash"))

            logger.info("MongoDB chunk indexes created successfully")
            return created
        except (PyMongoError, Exception) as e:
            logger.error(f"Failed to create MongoDB chunk indexes: {e}")
            raise MongoDBConnectionError(f"Error creating chunk indexes: {e}") from e

    def chunk_exists(self, chunk_id: str) -> bool:
        """Checks if a chunk with the given chunk_id already exists in MongoDB."""
        try:
            return self.chunks_collection.count_documents({"chunk_id": chunk_id}, limit=1) > 0
        except Exception as e:
            logger.error(f"Error checking chunk existence for {chunk_id}: {e}")
            return False

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a chunk by its deterministic chunk_id."""
        try:
            return self.chunks_collection.find_one({"chunk_id": chunk_id})
        except Exception as e:
            logger.error(f"Error fetching chunk {chunk_id}: {e}")
            return None

    def get_chunk_by_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Fetches an existing chunk with valid embedding matching content_hash (Phase 55.11)."""
        if getattr(self, "_is_offline", False):
            return None
        try:
            return self.chunks_collection.find_one({
                "content_hash": content_hash,
                "embedding": {"$exists": True, "$ne": None}
            })
        except Exception as e:
            logger.debug(f"Error fetching chunk by content_hash {content_hash}: {e}")
            return None

    def mark_document_missing(self, document_id: str) -> bool:
        """Safely updates document source_status to SOURCE_MISSING (Phase 55.17). Never deletes."""
        if getattr(self, "_is_offline", False):
            return False
        try:
            res = self.collection.update_one(
                {"document_id": document_id},
                {"$set": {"source_status": "SOURCE_MISSING", "metadata.source_status": "SOURCE_MISSING"}}
            )
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to mark document {document_id} as missing: {e}")
            return False

    def get_chunks_by_document(self, document_id: str) -> List[Dict[str, Any]]:
        """Fetches all chunks belonging to a document ordered by chunk_index."""
        try:
            return list(self.chunks_collection.find({"document_id": document_id}).sort("chunk_index", ASCENDING))
        except Exception as e:
            logger.error(f"Error fetching chunks for document {document_id}: {e}")
            return []

    def save_chunk(self, chunk: DocumentChunk) -> str:
        """
        Upserts a DocumentChunk (with content, metadata, and embeddings) into MongoDB.
        Uses chunk_id as the unique key to prevent duplicate records.
        """
        chunk_dict = to_mongo(chunk)
        chunk_id = chunk.chunk_id

        try:
            self.chunks_collection.update_one(
                {"chunk_id": chunk_id},
                {"$set": chunk_dict},
                upsert=True
            )
            logger.debug(f"Chunk {chunk_id} saved/updated successfully in MongoDB")
            return chunk_id
        except (PyMongoError, Exception) as e:
            logger.error(f"Failed to save chunk {chunk_id} to MongoDB: {e}")
            raise MongoDBConnectionError(f"Failed to save chunk: {e}") from e

    def save_chunks(self, chunks: List[DocumentChunk]) -> int:
        """
        Upserts multiple DocumentChunks into MongoDB.
        """
        if not chunks:
            return 0
        count = 0
        for chunk in chunks:
            self.save_chunk(chunk)
            count += 1
        return count


# Convenience functions
_default_repository = DocumentRepository()

def save_document(document: RegulatoryDocument, collection: Optional[Collection] = None) -> str:
    repo = DocumentRepository(collection=collection) if collection else _default_repository
    return repo.save_document(document)

def get_document_by_id(document_id: str, collection: Optional[Collection] = None) -> Optional[Dict[str, Any]]:
    repo = DocumentRepository(collection=collection) if collection else _default_repository
    return repo.get_document_by_id(document_id)

def document_exists(document_id: str, collection: Optional[Collection] = None) -> bool:
    repo = DocumentRepository(collection=collection) if collection else _default_repository
    return repo.document_exists(document_id)

def create_metadata_indexes(collection: Optional[Collection] = None) -> List[str]:
    repo = DocumentRepository(collection=collection) if collection else _default_repository
    return repo.create_metadata_indexes()

def save_chunk(chunk: DocumentChunk, chunks_collection: Optional[Collection] = None) -> str:
    repo = DocumentRepository(chunks_collection=chunks_collection) if chunks_collection else _default_repository
    return repo.save_chunk(chunk)

def save_chunks(chunks: List[DocumentChunk], chunks_collection: Optional[Collection] = None) -> int:
    repo = DocumentRepository(chunks_collection=chunks_collection) if chunks_collection else _default_repository
    return repo.save_chunks(chunks)

def get_chunk_by_id(chunk_id: str, chunks_collection: Optional[Collection] = None) -> Optional[Dict[str, Any]]:
    repo = DocumentRepository(chunks_collection=chunks_collection) if chunks_collection else _default_repository
    return repo.get_chunk_by_id(chunk_id)

def get_chunks_by_document(document_id: str, chunks_collection: Optional[Collection] = None) -> List[Dict[str, Any]]:
    repo = DocumentRepository(chunks_collection=chunks_collection) if chunks_collection else _default_repository
    return repo.get_chunks_by_document(document_id)

def create_chunk_indexes(chunks_collection: Optional[Collection] = None) -> List[str]:
    repo = DocumentRepository(chunks_collection=chunks_collection) if chunks_collection else _default_repository
    return repo.create_chunk_indexes()

def get_chunk_by_hash(content_hash: str, chunks_collection: Optional[Collection] = None) -> Optional[Dict[str, Any]]:
    repo = DocumentRepository(chunks_collection=chunks_collection) if chunks_collection else _default_repository
    return repo.get_chunk_by_hash(content_hash)

def mark_document_missing(document_id: str, collection: Optional[Collection] = None) -> bool:
    repo = DocumentRepository(collection=collection) if collection else _default_repository
    return repo.mark_document_missing(document_id)
