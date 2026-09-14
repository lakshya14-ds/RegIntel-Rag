import re
import hashlib
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# Supported Sources
SourceType = Literal["SEBI", "Moneycontrol"]

# Document Processing Status (Phase 55.2)
DocumentProcessingStatus = Literal[
    "NEW",
    "UNCHANGED",
    "CHANGED",
    "DUPLICATE",
    "FAILED",
    "UNSUPPORTED",
    "SOURCE_MISSING"
]

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "gclid", "_ga", "ncid"
}


def canonicalize_url(url: str) -> str:
    """
    Produces a normalized, canonical URL representation.
    - Normalizes scheme (lowercase)
    - Normalizes host (lowercase, removes 'www.')
    - Strips default ports
    - Strips fragment/hash
    - Strips tracking parameters
    - Sorts query parameters deterministically
    - Strips redundant trailing slashes
    """
    if not url or not isinstance(url, str):
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    
    netloc = parsed.netloc.lower()
    # Remove 'www.' prefix
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Remove default port
    if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc.rsplit(":", 1)[0]

    # Clean path
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Clean and sort query parameters
    query_params = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_params = sorted([(k, v) for k, v in query_params if k.lower() not in TRACKING_PARAMS])
    query = urlencode(filtered_params)

    # Omit fragments entirely
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def generate_document_id(source: str, url: str) -> str:
    """
    Generates a deterministic SHA-256 hash document ID based on canonical URL and source.
    """
    canonical_url = canonicalize_url(url)
    identity_string = f"{source.strip().upper()}:{canonical_url}"
    return hashlib.sha256(identity_string.encode("utf-8")).hexdigest()


def compute_content_hash(text: str) -> str:
    """Computes deterministic SHA-256 hash of normalized text content (Phase 55.4)."""
    if not text:
        return ""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class RawDocument(BaseModel):
    """Represents a raw scraped web page or document before transformation."""
    document_id: str
    url: str
    title: Optional[str] = None
    content: str
    source: SourceType
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v


class DocumentMetadata(BaseModel):
    """Metadata extracted deterministically from the regulatory document."""
    document_type: Optional[str] = None  # e.g., Circular, Master Circular, Order, Notification, Advisory
    category: Optional[str] = None       # e.g., Investment Adviser, Mutual Funds, Market Intermediaries, Securities Markets
    circular_number: Optional[str] = None
    published_date: Optional[str] = None  # ISO YYYY-MM-DD
    effective_date: Optional[str] = None  # ISO YYYY-MM-DD
    section: Optional[str] = None
    status: Optional[str] = "unknown"     # current, historical, unknown
    source_status: Optional[str] = "SOURCE_CURRENT"  # SOURCE_CURRENT, SOURCE_MISSING (Phase 55.17)
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    predecessor_candidates: Optional[List[str]] = Field(default_factory=list)
    relationship_confidence: Optional[str] = None  # high, medium, low
    content_hash: Optional[str] = None
    document_version: Optional[str] = "1.0"
    relationship_type: Optional[str] = None  # NEW, UPDATE, SUPERSEDES, SUPERSEDED, RELATED, UNKNOWN

    @field_validator("published_date", "effective_date")
    @classmethod
    def validate_iso_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Verify valid YYYY-MM-DD format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"Date must be in ISO YYYY-MM-DD format, got: {v}")
        return v


class RegulatoryDocument(BaseModel):
    """Represents a cleaned, structured regulatory document ready for downstream chunking/indexing."""
    document_id: str
    url: str
    title: Optional[str] = None
    source: SourceType
    document_type: Optional[str] = None
    category: Optional[str] = None
    circular_number: Optional[str] = None
    published_date: Optional[str] = None
    effective_date: Optional[str] = None
    section: Optional[str] = None
    status: Optional[str] = "unknown"
    source_status: Optional[str] = "SOURCE_CURRENT"
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    predecessor_candidates: Optional[List[str]] = Field(default_factory=list)
    relationship_confidence: Optional[str] = None
    content_hash: Optional[str] = None
    document_version: Optional[str] = "1.0"
    relationship_type: Optional[str] = None
    content: str
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: DocumentMetadata

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v

    @model_validator(mode="after")
    def sync_top_level_metadata(self):
        """Ensure top-level metadata fields mirror the nested metadata object."""
        if self.metadata:
            if self.document_type is None:
                self.document_type = self.metadata.document_type
            if self.category is None:
                self.category = self.metadata.category
            if self.circular_number is None:
                self.circular_number = self.metadata.circular_number
            if self.published_date is None:
                self.published_date = self.metadata.published_date
            if self.effective_date is None:
                self.effective_date = self.metadata.effective_date
            if self.section is None:
                self.section = self.metadata.section
            if self.status == "unknown" and self.metadata.status != "unknown":
                self.status = self.metadata.status
            if self.source_status == "SOURCE_CURRENT" and self.metadata.source_status != "SOURCE_CURRENT":
                self.source_status = self.metadata.source_status
            if self.supersedes is None:
                self.supersedes = self.metadata.supersedes
            if self.superseded_by is None:
                self.superseded_by = self.metadata.superseded_by
            if not self.predecessor_candidates and self.metadata.predecessor_candidates:
                self.predecessor_candidates = self.metadata.predecessor_candidates
            if self.relationship_confidence is None:
                self.relationship_confidence = self.metadata.relationship_confidence
            if self.content_hash is None:
                self.content_hash = self.metadata.content_hash
            if self.document_version == "1.0" and self.metadata.document_version != "1.0":
                self.document_version = self.metadata.document_version
            if self.relationship_type is None:
                self.relationship_type = self.metadata.relationship_type
        return self


class DocumentChunk(BaseModel):
    """
    Represents a structure-aware, context-enriched regulatory document chunk.
    Prepared for Gemini embeddings and MongoDB Vector Search.
    """
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    title: Optional[str] = None
    section: Optional[str] = None
    source: SourceType
    document_type: Optional[str] = None
    category: Optional[str] = None
    circular_number: Optional[str] = None
    published_date: Optional[str] = None
    effective_date: Optional[str] = None
    status: Optional[str] = "unknown"
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    url: str
    token_count: int
    embedding_text: Optional[str] = None
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    content_hash: Optional[str] = None

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Chunk content cannot be empty")
        return v

    @field_validator("token_count")
    @classmethod
    def validate_token_count(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Token count must be greater than zero")
        return v


class IngestionRunSummary(BaseModel):
    """Model tracking aggregate metrics for an ingestion run (Phase 55.20)."""
    run_id: str
    source: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = "COMPLETED"  # "COMPLETED", "PARTIAL", "FAILED"
    discovered: int = 0
    unique: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    duplicate: int = 0
    failed: int = 0
    unsupported: int = 0
    chunks_created: int = 0
    chunks_reused: int = 0
    chunks_changed: int = 0
    embeddings_created: int = 0
    embeddings_reused: int = 0
    embeddings_failed: int = 0
    version_relationships_created: int = 0
    change_analyses_created: int = 0
    failures: List[Dict[str, Any]] = Field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        aliases = {
            "updated": "changed",
            "duplicates": "duplicate",
            "embeddings_skipped": "embeddings_reused",
            "embeddings_generated": "embeddings_created",
            "new_chunks": "chunks_created",
            "updated_chunks": "chunks_changed",
            "documents_chunked": "chunks_created",
        }
        actual_key = aliases.get(key, key)
        if hasattr(self, actual_key):
            return getattr(self, actual_key)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        aliases = {
            "updated": "changed",
            "duplicates": "duplicate",
            "embeddings_skipped": "embeddings_reused",
            "embeddings_generated": "embeddings_created",
            "new_chunks": "chunks_created",
            "updated_chunks": "chunks_changed",
            "documents_chunked": "chunks_created",
        }
        actual_key = aliases.get(key, key)
        return hasattr(self, actual_key) or actual_key in self.model_fields

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


# Serialization Helpers
def to_mongo(model: BaseModel) -> Dict[str, Any]:
    """Converts a Pydantic model to a MongoDB-compatible dictionary."""
    return model.model_dump()


def from_mongo(model_cls: type[BaseModel], data: Dict[str, Any]) -> BaseModel:
    """Constructs a Pydantic model from a MongoDB document dictionary."""
    clean_data = dict(data)
    # Remove MongoDB internal _id if present
    if "_id" in clean_data:
        clean_data.pop("_id")
    return model_cls.model_validate(clean_data)
