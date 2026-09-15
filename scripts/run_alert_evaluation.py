"""
CLI runner for daily regulatory intelligence & alert evaluation job (Phase 65.11, 65.12).
Usage:
    python -m scripts.run_alert_evaluation [--as-of YYYY-MM-DD]
"""

import sys
import json
import argparse
import logging
from app.compliance.jobs import get_job_runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run Regulatory Alert & Deadline Evaluation Job.")
    parser.add_argument("--as-of", type=str, default=None, help="Reference date YYYY-MM-DD (defaults to UTC today)")
    args = parser.parse_args()

    runner = get_job_runner()
    result = runner.run_daily_evaluation(as_of_date=args.as_of)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
