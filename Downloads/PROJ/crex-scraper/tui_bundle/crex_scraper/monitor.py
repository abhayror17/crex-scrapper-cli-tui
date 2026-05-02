"""Monitor schedule and trigger match scrapers."""

import time
from datetime import datetime, timezone, timedelta

from .client import get_fixtures
from .scheduler import schedule_match_scraping, launch_now, SCHEDULED, RUNNING, LOCK
from .storage import ensure_dirs

ensure_dirs()

FIXTURES_POLL_INTERVAL = 60  # seconds


def monitor_schedule(poll_interval: int = FIXTURES_POLL_INTERVAL) -> None:
    """Main monitoring loop."""
    print(f"[MONITOR] Starting schedule monitor (poll every {poll_interval}s)")
    consecutive_errors = 0

    try:
        while True:
            try:
                fixtures = get_fixtures(0) or []
                fixtures1 = get_fixtures(1) or []
                all_fixtures = fixtures + fixtures1

                if not all_fixtures:
                    print("[MONITOR] No fixtures fetched, will retry...")
                    consecutive_errors += 1
                    time.sleep(poll_interval)
                    continue

                consecutive_errors = 0
                now = datetime.now(timezone.utc)

                for f in all_fixtures:
                    mf = f.get("mf")
                    if not mf:
                        continue
                    status = f.get("status", 0)
                    ts = f.get("t")
                    if not ts:
                        continue
                    try:
                        start_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                    except Exception:
                        continue

                    # Skip completed matches
                    if status == 2:
                        continue

                    if status == 1:
                        # Live match — launch immediately if not already running
                        with LOCK:
                            if mf not in RUNNING:
                                launch_now(mf, poll_interval=10)
                    elif status == 0:
                        # Upcoming — schedule if starting within buffer
                        if start_time <= now + timedelta(minutes=5):
                            schedule_match_scraping(mf, start_time, poll_interval=10)

                # Status summary
                with LOCK:
                    running = list(RUNNING.keys())
                print(
                    f"[MONITOR] Checked {len(all_fixtures)} fixtures. "
                    f"Active: {len(running)} | Scheduled: {len(SCHEDULED)}"
                )
                time.sleep(poll_interval)

            except KeyboardInterrupt:
                print("\n[MONITOR] Shutting down...")
                break
            except Exception as e:
                print(f"[MONITOR] Error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print("[MONITOR] Too many errors, exiting.")
                    break
                time.sleep(poll_interval)

    finally:
        print("[MONITOR] Exited.")