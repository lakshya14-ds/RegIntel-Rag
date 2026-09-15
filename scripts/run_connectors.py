"""
Multi-Regulator Connector Execution CLI (Phases 66–69).

CLI to discover, crawl, ingest, or inspect health for SEBI, RBI, IRDAI, PFRDA, and IFSCA:
  python scripts/run_connectors.py --authority RBI --discover --limit 5
  python scripts/run_connectors.py --authority RBI --ingest --limit 5
  python scripts/run_connectors.py --all --health
"""

import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.connectors import (
    connector_registry,
    source_registry,
    connector_tracker,
    RegulatoryAuthority,
    list_authorities
)
from app.ingestion.pipeline import IngestionPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scripts.run_connectors")


async def run_discovery(authority_str: str, limit: int = 10):
    """Executes document discovery for a given authority."""
    connector = connector_registry.get_connector(authority_str)
    if not connector:
        print(f"Error: Unknown authority '{authority_str}'. Supported: {[a.value for a in RegulatoryAuthority]}")
        return

    print(f"\n==========================================")
    print(f"[DISCOVERY] Discovering Documents: {connector.authority.value}")
    print(f"==========================================")

    sources = await connector.discover_sources()
    print(f"Registered official sources: {len(sources)}")
    for s in sources:
        print(f" - [{s.source_id}] {s.name} ({s.listing_url})")

    candidates = await connector.discover_documents(limit=limit)
    print(f"\nDiscovered {len(candidates)} candidate documents (limit={limit}):")
    for i, c in enumerate(candidates, 1):
        print(f" {i}. [{c.get('document_type', 'Doc')}] {c.get('title') or c.get('url')}")
        print(f"    URL: {c.get('url')}")
        if c.get("reference_number"):
            print(f"    Ref: {c.get('reference_number')}")
    print("==========================================\n")


def run_ingest(authority_str: str, limit: int = None, dry_run: bool = False, force: bool = False):
    """Runs ingestion pipeline for a given authority."""
    print(f"\n==========================================")
    print(f"[INGESTION] Running Ingestion: {authority_str.upper()} (dry_run={dry_run})")
    print(f"==========================================")
    pipeline = IngestionPipeline()
    summary = pipeline.run(
        source=authority_str.lower(),
        limit=limit,
        dry_run=dry_run,
        force=force
    )
    return summary


def display_health():
    """Displays health summaries for all regulatory connectors."""
    print("\n" + "=" * 65)
    print("[HEALTH] REGULATORY CONNECTOR HEALTH OVERVIEW")
    print("=" * 65)
    print(f"{'Authority':<10} {'Status':<12} {'Last Run':<22} {'Discovered':<12}")
    print("-" * 65)

    all_health = connector_tracker.get_all_health()
    for h in all_health:
        last_at = (h.last_run_at[:19] if h.last_run_at else "Never")
        status_str = h.status
        print(f"{h.authority.value:<10} {status_str:<12} {last_at:<22} {h.total_discovered_last_run:<12}")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="RegIntel Multi-Regulator Connector Tool")
    parser.add_argument("--authority", "-a", type=str, choices=[a.value for a in RegulatoryAuthority], help="Target regulatory authority")
    parser.add_argument("--all", action="store_true", help="Execute across all registered authorities")
    parser.add_argument("--discover", action="store_true", help="Discover documents and print candidates")
    parser.add_argument("--ingest", action="store_true", help="Run full incremental ingestion pipeline")
    parser.add_argument("--health", action="store_true", help="Display connector health status dashboard")
    parser.add_argument("--limit", type=int, default=10, help="Candidate document processing limit")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without modifying database")
    parser.add_argument("--force", action="store_true", help="Force reprocessing")

    args = parser.parse_args()

    if args.health or (not args.discover and not args.ingest and not args.authority and not args.all):
        display_health()
        return

    authorities = [args.authority] if args.authority else [a.value for a in RegulatoryAuthority] if args.all else ["SEBI"]

    for auth in authorities:
        if args.discover:
            asyncio.run(run_discovery(auth, limit=args.limit))
        if args.ingest:
            run_ingest(auth, limit=args.limit, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
