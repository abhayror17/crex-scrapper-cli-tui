"""Scheduling utilities for launching match scrapers."""

import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from .match import MatchScraper

# Global state (shared)
SCHEDULED = set()  # match keys that have been scheduled (or launched)
RUNNING = {}       # match_key -> MatchScraper instance
LOCK = threading.Lock()

MATCH_START_BUFFER_MINUTES = 5
MAX_CONCURRENT_MATCHES = 5


def launch_now(match_key: str, poll_interval: int = 10) -> None:
    """Immediately launch a scraper for the given match."""
    with LOCK:
        if match_key in RUNNING:
            return
        if len(RUNNING) >= MAX_CONCURRENT_MATCHES:
            print(f"[SCHED] Max concurrent limit reached, skipping {match_key}")
            return
        scraper = MatchScraper(match_key, poll_interval=poll_interval)
        RUNNING[match_key] = scraper

    threading.Thread(target=scraper.start_polling, daemon=True).start()
    print(f"[SCHED] Started live scraper for match {match_key}")


def schedule_match_scraping(
    match_key: str,
    start_time: datetime,
    poll_interval: int = 10,
) -> None:
    """
    Schedule a scraper to start near the match start time.

    Args:
        match_key: Unique match identifier
        start_time: UTC datetime when match is scheduled to begin
        poll_interval: Seconds between live score polls
    """
    with LOCK:
        if match_key in SCHEDULED:
            return
        SCHEDULED.add(match_key)

    now = datetime.now(timezone.utc)
    delay_seconds = (start_time - now).total_seconds()
    buffer_seconds = MATCH_START_BUFFER_MINUTES * 60

    if delay_seconds > buffer_seconds:
        # Schedule to start a bit before scheduled time
        def delayed_start():
            time.sleep(delay_seconds - buffer_seconds)
            launch_now(match_key, poll_interval)

        threading.Thread(target=delayed_start, daemon=True).start()
        print(f"[SCHED] Match {match_key} will launch in {delay_seconds/60:.1f} mins (at {start_time.isoformat()})")
    else:
        # Match starts soon or already started — launch immediately
        launch_now(match_key, poll_interval)
