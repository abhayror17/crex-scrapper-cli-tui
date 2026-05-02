"""Crex Scraper - Real-time cricket data scraping system for CREX.com"""

from .client import (
    run_curl,
    get_live_matches,
    get_fixtures,
    get_live_score,
    get_match_info,
    get_scorecard,
    get_squads_from_details,
)
from .storage import save_json, ensure_dirs
from .monitor import monitor_schedule
from .scheduler import schedule_match_scraping, launch_now, SCHEDULED, RUNNING
from .match import scrape_match, MatchScraper

__version__ = "1.0.0"

__all__ = [
    "run_curl",
    "get_live_matches",
    "get_fixtures",
    "get_live_score",
    "get_match_info",
    "get_scorecard",
    "get_squads_from_details",
    "save_json",
    "ensure_dirs",
    "monitor_schedule",
    "schedule_match_scraping",
    "launch_now",
    "scrape_match",
    "MatchScraper",
    "SCHEDULED",
    "RUNNING",
]
