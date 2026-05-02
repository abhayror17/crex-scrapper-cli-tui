"""Match scraper: collects all data for a specific match."""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .client import (
    get_match_info,
    get_squads_from_details,
    get_scorecard,
    get_live_score,
)
from .storage import save_json


class MatchScraper:
    """Scrapes a single match across all tabs (info, squads, live, scorecard)."""

    def __init__(self, match_key: str, poll_interval: int = 10, max_polls: int = 0):
        """
        Args:
            match_key: Unique match identifier (e.g., "118O")
            poll_interval: Seconds between live score updates
            max_polls: Maximum number of polls (0 = unlimited)
        """
        self.match_key = match_key
        self.poll_interval = poll_interval
        self.max_polls = max_polls
        self.etag: Optional[str] = None
        self.poll_count = 0
        self.is_running = True

    def scrape_once(self, save: bool = True) -> Dict[str, Any]:
        """Perform one round of scraping all data sources."""
        result = {
            "match_key": self.match_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Match info
        info = get_match_info(self.match_key)
        if info:
            result["info"] = info
            if save:
                save_json(info, self.match_key, "info")

        # 2. Squads (from details page HTML scraping)
        squads = get_squads_from_details(self.match_key)
        if squads:
            result["squads"] = squads
            if save:
                save_json(squads, self.match_key, "squads")

        # 3. Live score
        score_data = get_live_score(self.match_key, self.etag)
        if score_data:
            result["live"] = score_data
            if save:
                save_json(score_data, self.match_key, "live")
            # Update etag for next conditional GET & handle 304 Not Modified
            # We'll extract etag from response headers if available, but we don't capture them.
            # Reset etag to always fetch fresh for now
            self.etag = None

        # 4. Scorecard
        scorecard = get_scorecard(self.match_key)
        if scorecard:
            result["scorecard"] = scorecard
            if save:
                save_json(scorecard, self.match_key, "scorecard")

        return result

    def is_match_live(self, live_data: Optional[Dict]) -> bool:
        """Determine if match is still ongoing based on live score data."""
        if not live_data:
            return False
        # 'status' field maybe 1 = live, 0 = completed
        # In earlier samples, status 1 = live
        return live_data.get("status", 0) == 1

    def start_polling(self) -> None:
        """Start continuous polling for live updates."""
        print(f"[{self.match_key}] Starting polling (interval={self.poll_interval}s)")
        try:
            while self.is_running:
                result = self.scrape_once(save=True)

                live_data = result.get("live")
                if live_data:
                    print(
                        f"[{self.match_key}] Poll {self.poll_count}: "
                        f"Score={live_data.get('score1','N/A')}/{live_data.get('score2','N/A')}"
                    )
                else:
                    print(f"[{self.match_key}] Poll {self.poll_count}: No live data")

                # Check if match concluded
                if not self.is_match_live(live_data):
                    print(f"[{self.match_key}] Match appears to be finished. Stopping poll.")
                    break

                self.poll_count += 1
                if self.max_polls > 0 and self.poll_count >= self.max_polls:
                    print(f"[{self.match_key}] Reached max polls ({self.max_polls}). Stopping.")
                    break

                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print(f"[{self.match_key}] Polling interrupted.")
        finally:
            self.is_running = False

    def stop(self) -> None:
        """Stop polling."""
        self.is_running = False


def scrape_match(match_key: str, one_off: bool = False, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to scrape a single match.

    Args:
        match_key: Match identifier
        one_off: If True, fetch all data once without polling. If False, start polling.
        **kwargs: Passed to MatchScraper (poll_interval, max_polls)

    Returns:
        dict of scraped data (if one_off) else empty (polling runs in background)
    """
    scraper = MatchScraper(match_key, **kwargs)
    if one_off:
        return scraper.scrape_once()
    else:
        import threading

        thread = threading.Thread(target=scraper.start_polling, daemon=True)
        thread.start()
        return {"status": "polling_started", "match_key": match_key}
