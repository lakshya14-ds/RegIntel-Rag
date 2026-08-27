import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from datetime import datetime

from app.config import settings
from app.ingestion.models import (
    RawDocument,
    RegulatoryDocument,
    canonicalize_url,
    generate_document_id,
    to_mongo,
    from_mongo
)
from app.ingestion.cleaner import clean_markdown
from app.ingestion.metadata import MetadataExtractor, derive_title_from_url_or_content
from app.ingestion.repository import save_document

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base asynchronous scraper orchestrating Crawl4AI, cleaning, metadata extraction, and storage."""

    def __init__(self, source_name: str, raw_dir: Optional[Path] = None, processed_dir: Optional[Path] = None):
        self.source_name = source_name
        self.raw_dir = raw_dir or settings.raw_data_dir
        self.processed_dir = processed_dir or settings.processed_data_dir
        
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def save_raw_document(self, raw_doc: RawDocument) -> Path:
        """Saves a raw scraped document locally in JSON format."""
        file_path = self.raw_dir / f"{self.source_name.lower()}_{raw_doc.document_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(raw_doc.model_dump(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved raw document to {file_path}")
        return file_path

    def save_processed_document(self, processed_doc: RegulatoryDocument) -> Path:
        """Saves a processed regulatory document locally in JSON format."""
        file_path = self.processed_dir / f"{self.source_name.lower()}_{processed_doc.document_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(processed_doc.model_dump(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved processed document to {file_path}")
        return file_path

    def process_raw_document(self, raw_doc: RawDocument, persist_db: bool = False) -> RegulatoryDocument:
        """
        Cleans raw markdown text, extracts metadata deterministically, and produces a RegulatoryDocument.
        Optionally persists to MongoDB.
        """
        # 1. Clean markdown text
        cleaned_text = clean_markdown(raw_doc.content)

        # 2. Derive descriptive title if generic
        resolved_title = derive_title_from_url_or_content(
            url=raw_doc.url,
            text=cleaned_text,
            generic_title=raw_doc.title
        )

        # 3. Extract metadata deterministically (rule-based, no LLM)
        metadata = MetadataExtractor.extract(
            text=cleaned_text,
            title=resolved_title,
            url=raw_doc.url
        )

        # 4. Construct RegulatoryDocument
        processed_doc = RegulatoryDocument(
            document_id=raw_doc.document_id,
            url=raw_doc.url,
            title=resolved_title,
            source=raw_doc.source,
            document_type=metadata.document_type,
            category=metadata.category,
            circular_number=metadata.circular_number,
            published_date=metadata.published_date,
            effective_date=metadata.effective_date,
            section=metadata.section,
            content=cleaned_text,
            scraped_at=raw_doc.scraped_at,
            metadata=metadata
        )

        # 5. Save to local data/processed directory
        self.save_processed_document(processed_doc)

        # 6. Optionally save to MongoDB
        if persist_db:
            try:
                save_document(processed_doc)
                logger.info(f"Persisted document {processed_doc.document_id} to MongoDB Atlas")
            except Exception as e:
                logger.warning(f"MongoDB persistence skipped or failed for {processed_doc.document_id}: {e}")

        return processed_doc

    def reprocess_all_raw_documents(self, persist_db: bool = False) -> int:
        """Reprocesses all raw JSON files from data/raw/ into data/processed/."""
        raw_files = list(self.raw_dir.glob(f"{self.source_name.lower()}_*.json"))
        count = 0
        for rf in raw_files:
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                raw_doc = from_mongo(RawDocument, data)
                self.process_raw_document(raw_doc, persist_db=persist_db)
                count += 1
            except Exception as e:
                logger.error(f"Failed to reprocess {rf.name}: {e}")
        return count
