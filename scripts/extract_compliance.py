"""
Compliance Extraction & Backfill CLI Tool (Phases 61, 62, 63).

Usage:
    python -m scripts.extract_compliance --dry-run
    python -m scripts.extract_compliance --document-id <DOC_ID>
    python -m scripts.extract_compliance --all
    python -m scripts.extract_compliance --generate-checklist --title "Annual Compliance Checklist"
"""

import argparse
import logging
import json
from pathlib import Path
from typing import Optional, List

from app.config import settings
from app.compliance.repository import get_compliance_repository
from app.compliance.requirement_extractor import get_requirement_extractor
from app.compliance.obligation_extractor import get_obligation_extractor
from app.compliance.checklist_generator import get_checklist_generator
from app.change_detection.diff_engine import extract_hierarchical_sections

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("compliance_cli")


def load_local_documents() -> List[dict]:
    """Loads processed document dictionaries from local processed directory."""
    docs = []
    for fp in settings.processed_data_dir.glob("*.json"):
        if fp.name.startswith("chunk") or fp.name.startswith("compliance") or "summary" in fp.name:
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict) and "document_id" in d and "content" in d:
                    docs.append(d)
        except Exception:
            continue
    return docs


def process_document(
    doc: dict,
    dry_run: bool = False,
    use_llm: bool = False
) -> tuple:
    """Processes a single document for requirements and obligations."""
    doc_id = doc.get("document_id", "")
    title = doc.get("title", "Untitled")
    content = doc.get("content", "")
    source = doc.get("source", "SEBI")
    doc_type = doc.get("document_type", "Circular")
    eff_date = doc.get("effective_date")
    status = doc.get("status", "unknown")

    logger.info(f"Processing '{title[:50]}...' [ID: {doc_id}]")

    sections = extract_hierarchical_sections(content, document_id=doc_id)
    req_extractor = get_requirement_extractor()
    ob_extractor = get_obligation_extractor()
    repo = get_compliance_repository()

    all_reqs = []
    if not sections:
        reqs = req_extractor.extract_requirements_from_text(
            text=content,
            document_id=doc_id,
            authority=source,
            document_title=title,
            document_type=doc_type,
            effective_date=eff_date,
            use_llm=use_llm
        )
        all_reqs.extend(reqs)
    else:
        for sec in sections:
            reqs = req_extractor.extract_requirements_from_text(
                text=sec.content,
                document_id=doc_id,
                authority=source,
                document_title=title,
                document_type=doc_type,
                effective_date=eff_date,
                section_id=sec.section_id,
                section_number=sec.section_number,
                heading=sec.heading,
                page_number=sec.page_start,
                use_llm=use_llm
            )
            all_reqs.extend(reqs)

    obs = ob_extractor.extract_obligations(all_reqs, document_status=status)

    if not dry_run:
        saved_reqs = repo.save_requirements(all_reqs)
        saved_obs = repo.save_obligations(obs)
        logger.info(f"Saved {saved_reqs} requirements and {saved_obs} obligations for {doc_id}.")
    else:
        logger.info(f"[DRY-RUN] Extracted {len(all_reqs)} requirements and {len(obs)} obligations for {doc_id}.")

    return all_reqs, obs


def main():
    parser = argparse.ArgumentParser(description="Compliance Intelligence Backfill Tool")
    parser.add_argument("--dry-run", action="store_true", help="Inspect extraction without saving")
    parser.add_argument("--document-id", type=str, help="Process a specific document ID")
    parser.add_argument("--all", action="store_true", help="Process all available documents")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM semantic enrichment")
    parser.add_argument("--generate-checklist", action="store_true", help="Generate compliance checklist")
    parser.add_argument("--title", type=str, default="SEBI Compliance Master Checklist", help="Checklist title")

    args = parser.parse_args()

    docs = load_local_documents()
    if not docs:
        logger.warning(f"No processed regulatory documents found in {settings.processed_data_dir}.")
        return

    targets = []
    if args.document_id:
        targets = [d for d in docs if d.get("document_id") == args.document_id]
        if not targets:
            logger.error(f"Document with ID '{args.document_id}' not found.")
            return
    elif args.all:
        targets = docs
    else:
        # Default: process first 3 documents as sample
        targets = docs[:3]

    logger.info(f"Targeting {len(targets)} documents (Dry Run: {args.dry_run})...")

    collected_obs = []
    for doc in targets:
        _, obs = process_document(doc, dry_run=args.dry_run, use_llm=args.use_llm)
        collected_obs.extend(obs)

    if args.generate_checklist and collected_obs and not args.dry_run:
        chk_gen = get_checklist_generator()
        repo = get_compliance_repository()
        chk = chk_gen.generate_checklist(
            title=args.title,
            obligations=collected_obs,
            document_ids=[d.get("document_id") for d in targets if d.get("document_id")]
        )
        repo.save_checklist(chk)
        logger.info(f"Successfully generated checklist '{chk.title}' with {len(chk.items)} items [ID: {chk.checklist_id}].")


if __name__ == "__main__":
    main()
