import subprocess
import sys
import time
import logging
from datetime import datetime, timedelta, timezone

ISLAND_CODES = [
    "9642-0223-9671",  # trio
    "9752-7422-1395",  # duo
]
CSV_FILE = "island_metrics_history.csv"
LOG_FILE = "scheduler.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def seconds_until_next_midnight():
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (tomorrow - now).total_seconds()


def run_fetch(island_code, today):
    cmd = [
        sys.executable,
        "fortnite_island.py",
        "--island", island_code,
        "--start", today,
        "--end", today,
        "--csv", CSV_FILE,
    ]
    log.info("[%s] Fetching metrics for %s", island_code, today)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log.info("[%s]   %s", island_code, line)
    if result.returncode != 0:
        log.error("[%s] Fetch failed (exit %d): %s", island_code, result.returncode, result.stderr.strip())
    else:
        log.info("[%s] Done.", island_code)


def run_all():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log.info("Starting daily fetch for %d island(s) — %s", len(ISLAND_CODES), today)
    for code in ISLAND_CODES:
        run_fetch(code, today)
    log.info("All fetches complete.")


def main():
    log.info("Scheduler started. Tracking %d island(s): %s", len(ISLAND_CODES), ", ".join(ISLAND_CODES))
    log.info("Data will be appended to: %s", CSV_FILE)

    while True:
        wait = seconds_until_next_midnight()
        next_run = datetime.now(timezone.utc) + timedelta(seconds=wait)
        log.info("Next run at %s UTC (in %.0f seconds / %.1f hours)",
                 next_run.strftime("%Y-%m-%d %H:%M:%S"), wait, wait / 3600)
        time.sleep(wait)
        run_all()


if __name__ == "__main__":
    main()
