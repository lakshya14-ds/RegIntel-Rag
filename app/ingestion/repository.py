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
        try:
            return self.collection.count_documents({"document_id": document_id}, limit=1) > 0
        except Exception as e:
            logger.error(f"Error checking document existence for {document_id}: {e}")
            return False

    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a document by its deterministic document_id."""
        try:
            return self.collection.find_one({"document_id": document_id})
        except Exception as e:
            logger.error(f"Error fetching document {document_id}: {e}")
            return None

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
