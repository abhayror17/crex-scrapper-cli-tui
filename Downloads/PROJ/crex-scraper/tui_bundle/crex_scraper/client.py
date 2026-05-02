"""HTTP client using curl.exe with IPv4, retry logic, and parse responses."""

import subprocess
import json
import re
import time
from typing import Any, Dict, List, Optional

BASE_HEADERS = [
    "accept: application/json, text/plain, */*",
    "accept-language: en-US,en;q=0.6",
    "authorization: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImV4cGlyZXNJbiI6IjM2NWQifQ.eyJ0aW1lIjoxNjYwMDQ2NjIwMDAwfQ.bTEmMWlR7hLRUHxPPq6-1TP7cuuW7m6sZ9jcdbYzLRA",
    "cc: IN",
    "content-type: application/json",
    "dnt: 1",
    "origin: https://crex.com",
    "priority: u=1, i",
    "referer: https://crex.com/",
    "sec-ch-ua: \"Brave\";v=\"147\", \"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"147\"",
    "sec-ch-ua-mobile: ?1",
    "sec-ch-ua-platform: \"Android\"",
    "sec-fetch-dest: empty",
    "sec-fetch-mode: cors",
    "sec-fetch-site: cross-site",
    "sec-gpc: 1",
    "user-agent: Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36"
]


def run_curl(
    url: str,
    headers: Optional[List[str]] = None,
    data: Optional[Dict[str, Any]] = None,
    extra_args: Optional[List[str]] = None,
    method: str = "GET",
    max_retries: int = 3,
    retry_delay: float = 2.0,
    timeout: int = 30,
) -> Optional[Any]:
    """Execute curl command with retry logic."""
    hdrs = list(headers) if headers else []
    
    # Build curl command base
    cmd = ["curl.exe", "-4", "-s", "--connect-timeout", str(timeout), url]
    for h in hdrs:
        cmd.extend(["-H", h])
    if data:
        cmd.extend(["--data-raw", json.dumps(data)])
    if extra_args:
        cmd.extend(extra_args)

    attempt = 0
    while attempt < max_retries:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout)
            if result.returncode == 0:
                stdout = result.stdout.decode("utf-8", errors="replace").strip()
                if stdout:
                    try:
                        return json.loads(stdout)
                    except json.JSONDecodeError as e:
                        print(f"[WARN] JSON parse error: {e}. Response: {stdout[:200]}")
                        return None
                else:
                    print("[WARN] Empty response")
                    return None
            else:
                stderr = result.stderr.decode("utf-8", errors="replace")
                print(f"[WARN] curl failed (code {result.returncode}): {stderr[:200]}")
        except subprocess.TimeoutExpired:
            print("[WARN] Request timed out")
        except Exception as e:
            print(f"[WARN] Unexpected error: {e}")

        attempt += 1
        if attempt < max_retries:
            delay = retry_delay * (2 ** (attempt - 1))
            time.sleep(delay)

    print(f"[ERROR] Failed after {max_retries} attempts: {url}")
    return None


def get_live_matches() -> Optional[Dict[str, Any]]:
    """Fetch currently live matches."""
    return run_curl("https://api.goscorer.com/api/v3/getLiveMatches", headers=BASE_HEADERS)


def get_fixtures(page: int = 0) -> Optional[Dict[str, Any]]:
    """Fetch upcoming fixtures."""
    payload = {"type": "0", "page": page, "wise": "1", "lang": "en"}
    return run_curl(
        "https://stats.crickapi.com/fixture/getFixture",
        headers=BASE_HEADERS,
        data=payload,
        method="POST",
    )


def get_live_score(match_key: str, etag: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch live score for a match."""
    url = f"https://api.goscorer.com/api/v3/getSV3?key={match_key}"
    headers = BASE_HEADERS.copy()
    if etag:
        headers.append(f"if-none-match: {etag}")
    return run_curl(url, headers=headers)


def get_match_info(match_key: str) -> Optional[Dict[str, Any]]:
    """Fetch match metadata (venue, teams, start time, etc.)."""
    url = f"https://api.goscorer.com/api/v3/getIV4?key={match_key}"
    return run_curl(url, headers=BASE_HEADERS)


def get_scorecard(match_key: str) -> Optional[Any]:
    """Fetch full scorecard (batting/bowling figures)."""
    url = f"https://api.goscorer.com/api/v3/getSC4?key={match_key}"
    return run_curl(url, headers=BASE_HEADERS)


def get_squads_from_details(match_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch squads (player list) by scraping match details page.
    The details page embeds JSON in <script id="app-root-state">.
    """
    details_url = f"https://crex.com/cricket-live-score/{match_key}/match-details"
    cmd = [
        "curl.exe", "-4", "-s", details_url,
        "-H", "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            print(f"[ERROR] Details page fetch failed: {result.returncode}")
            return None
        html = result.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[ERROR] Exception fetching details page: {e}")
        return None

    # Find the embedded JSON state block
    match = re.search(r'<script id="app-root-state"[^>]*>(\{.*\})</script>', html, re.DOTALL)
    if not match:
        print(f"[WARN] No app-root-state script found for {match_key}")
        return None

    raw_json = match.group(1)
    # The JSON uses &q; as escaped quotes; replace with normal quotes
    json_str = raw_json.replace("&q;", '"')
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[WARN] JSON parse error: {e}")
        with open(f"debug_squads_{match_key}.html", "w", encoding="utf-8") as f:
            f.write(html)
        return None

    # The squads data is under key 'https://oc.crickapi.com/mapping/getHomeMapDatamatchinfo'
    key = "https://oc.crickapi.com/mapping/getHomeMapDatamatchinfo"
    val = data.get(key)
    if val and isinstance(val, dict) and "p" in val:
        return val
    print(f"[WARN] Key {key} not found in preloaded JSON keys: {list(data.keys())[:5]}")
    return None
