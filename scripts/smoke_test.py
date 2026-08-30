"""
RegIntel RAG Production Smoke Test Script (Phase 52.17).

Executes quick or full non-destructive validation against a live or local RegIntel backend:
1. Backend Health Check (/health)
2. Document Search (/search)
3. RAG Question Answering (/ask)
4. Latest Documents Listing (/latest)
5. Document Comparison (/compare)

Usage:
    python scripts/smoke_test.py --quick
    python scripts/smoke_test.py --full --base-url http://localhost:8000
"""

import sys
import time
import argparse
import logging
from typing import Dict, Any
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smoke_test")


def run_smoke_tests(base_url: str, quick_mode: bool = False) -> bool:
    base_url = base_url.rstrip("/")
    logger.info(f"Starting RegIntel RAG Smoke Tests against: {base_url} (Quick: {quick_mode})")

    success_count = 0
    total_tests = 4 if quick_mode else 5

    # 1. Health Check
    try:
        t0 = time.perf_counter()
        res = requests.get(f"{base_url}/health", timeout=10)
        dur = (time.perf_counter() - t0) * 1000.0
        if res.status_code == 200:
            data = res.json()
            logger.info(f"[PASS] GET /health (Status: {data.get('status')}, Version: {data.get('version')}) - {dur:.1f}ms")
            success_count += 1
        else:
            logger.error(f"[FAIL] GET /health returned HTTP {res.status_code}")
    except Exception as e:
        logger.error(f"[FAIL] GET /health connection error: {e}")

    # 2. Search Endpoint Check
    try:
        t0 = time.perf_counter()
        payload = {"query": "Investment Adviser fee structure", "top_k": 3, "retrieval_mode": "bm25"}
        res = requests.post(f"{base_url}/search", json=payload, timeout=15)
        dur = (time.perf_counter() - t0) * 1000.0
        if res.status_code == 200:
            data = res.json()
            logger.info(f"[PASS] POST /search (Results: {data.get('total_results')}) - {dur:.1f}ms")
            success_count += 1
        else:
            logger.error(f"[FAIL] POST /search returned HTTP {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"[FAIL] POST /search error: {e}")

    # 3. Latest Documents Check
    try:
        t0 = time.perf_counter()
        res = requests.get(f"{base_url}/latest?limit=3", timeout=10)
        dur = (time.perf_counter() - t0) * 1000.0
        if res.status_code == 200:
            data = res.json()
            logger.info(f"[PASS] GET /latest (Count: {len(data)}) - {dur:.1f}ms")
            success_count += 1
        else:
            logger.error(f"[FAIL] GET /latest returned HTTP {res.status_code}")
    except Exception as e:
        logger.error(f"[FAIL] GET /latest error: {e}")

    # 4. RAG Ask Endpoint Check (Fast query / mockable)
    try:
        t0 = time.perf_counter()
        payload = {
            "question": "What is the net worth requirement for investment advisers?",
            "top_k": 3,
            "retrieval_mode": "bm25"
        }
        res = requests.post(f"{base_url}/ask", json=payload, timeout=30)
        dur = (time.perf_counter() - t0) * 1000.0
        if res.status_code == 200:
            data = res.json()
            logger.info(f"[PASS] POST /ask (Grounded: {data.get('sufficient_evidence')}, Sources: {len(data.get('sources', []))}) - {dur:.1f}ms")
            success_count += 1
        else:
            logger.error(f"[FAIL] POST /ask returned HTTP {res.status_code}: {res.text}")
    except Exception as e:
        logger.error(f"[FAIL] POST /ask error: {e}")

    # 5. Compare Endpoint Check (Full mode only)
    if not quick_mode:
        try:
            t0 = time.perf_counter()
            # Non-existent comparison to verify clean 404/400 handling or valid comparison
            payload = {"document_a_id": "test_doc_a", "document_b_id": "test_doc_b"}
            res = requests.post(f"{base_url}/compare", json=payload, timeout=20)
            dur = (time.perf_counter() - t0) * 1000.0
            if res.status_code in (200, 404):
                logger.info(f"[PASS] POST /compare (Status Code: {res.status_code}) - {dur:.1f}ms")
                success_count += 1
            else:
                logger.error(f"[FAIL] POST /compare returned unexpected HTTP {res.status_code}")
        except Exception as e:
            logger.error(f"[FAIL] POST /compare error: {e}")

    logger.info(f"Smoke Test Summary: {success_count}/{total_tests} tests passed.")
    return success_count == total_tests


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RegIntel RAG Smoke Tests")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of FastAPI service")
    parser.add_argument("--quick", action="store_true", help="Run quick critical path check")
    parser.add_argument("--full", action="store_true", help="Run full smoke test suite")
    args = parser.parse_args()

    quick = not args.full if args.quick else False
    success = run_smoke_tests(base_url=args.base_url, quick_mode=quick)
    sys.exit(0 if success else 1)
