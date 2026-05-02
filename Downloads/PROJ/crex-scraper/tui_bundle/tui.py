#!/usr/bin/env python3
"""
CREX Cricket TUI  —  Beautiful terminal cricket explorer.
Runs from project root; no installation required.
"""

import sys, json, os, time, re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# ─── Ensure local crex_scraper package is importable ─────────────────────────
_this_file = Path(__file__).resolve()
_project_root = _this_file.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ─── Data file locations (relative to script, not CWD) ────────────────────────
_TEAM_FILE   = _project_root / "data" / "team_map.json"
_PLAYER_FILE = _project_root / "data" / "player_map.json"

# ─── Rich imports ────────────────────────────────────────────────────────────
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.text    import Text
from rich.align   import Align
from rich.rule    import Rule
from rich.columns import Columns
from rich.padding import Padding
from rich.prompt  import Prompt
from rich         import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
import questionary
from questionary  import Style as QStyle

# ─── Optional crex_scraper ───────────────────────────────────────────────────
try:
    from crex_scraper import (
        get_live_matches, get_fixtures,
        get_scorecard, get_squads_from_details, save_json,
    )
    from crex_scraper.storage import ensure_dirs
    CREX_AVAILABLE = True
    ensure_dirs()
except ImportError:
    CREX_AVAILABLE = False





# ══════════════════════════════════════════════════════════════════════════════
#  NAME RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

TEAM_MAP: Dict[str, str] = {
    # Full codes
    "IND": "India",  "ENG": "England",    "AUS": "Australia",    "NZ":  "New Zealand",
    "PAK": "Pakistan","SL":  "Sri Lanka",  "SA":  "South Africa", "WI":  "West Indies",
    "BAN": "Bangladesh","ZIM":"Zimbabwe",  "AFG": "Afghanistan",  "IRE": "Ireland",
    "SCO": "Scotland","UAE":"UAE",         "NAM": "Namibia",      "OMA": "Oman",
    "USA": "USA",    "CAN": "Canada",     "NED": "Netherlands",  "KEN": "Kenya",
    # IPL / franchise
    "MI":  "Mumbai Indians",              "CSK": "Chennai Super Kings",
    "RCB": "Royal Challengers Bengaluru", "KKR": "Kolkata Knight Riders",
    "SRH": "Sunrisers Hyderabad",         "DC":  "Delhi Capitals",
    "PBKS":"Punjab Kings",                "RR":  "Rajasthan Royals",
    "GT":  "Gujarat Titans",              "LSG": "Lucknow Super Giants",
    # Slug forms
    "india": "India", "england": "England", "australia": "Australia",
    "new-zealand": "New Zealand", "pakistan": "Pakistan", "sri-lanka": "Sri Lanka",
    "south-africa": "South Africa", "west-indies": "West Indies",
}

PLAYER_MAP: Dict[str, str] = {
    # India
    "rohit-sharma":     "Rohit Sharma",      "shubman-gill":       "Shubman Gill",
    "virat-kohli":      "Virat Kohli",       "suryakumar-yadav":   "Suryakumar Yadav",
    "hardik-pandya":    "Hardik Pandya",     "rinku-singh":        "Rinku Singh",
    "dinesh-karthik":   "Dinesh Karthik",    "axar-patel":         "Axar Patel",
    "yuzvendra-chahal": "Yuzvendra Chahal",  "kuldeep-yadav":      "Kuldeep Yadav",
    "jasprit-bumrah":   "Jasprit Bumrah",    "arshdeep-singh":     "Arshdeep Singh",
    # Australia
    "pat-cummins":      "Pat Cummins",       "josh-hazlewood":     "Josh Hazlewood",
    "mitchell-starc":   "Mitchell Starc",    "adam-zampa":         "Adam Zampa",
    "glenn-maxwell":    "Glenn Maxwell",     "travis-head":        "Travis Head",
    "david-warner":     "David Warner",      "steven-smith":       "Steven Smith",
    "marnus-labuschagne":"Marnus Labuschagne","tim-david":         "Tim David",
    "matthew-wade":     "Matthew Wade",      "josh-inglis":        "Josh Inglis",
    # England
    "jos-buttler":      "Jos Buttler",       "phil-salt":          "Phil Salt",
    "dawid-malan":      "Dawid Malan",       "harry-brook":        "Harry Brook",
    "ben-stokes":       "Ben Stokes",        "liam-livingstone":   "Liam Livingstone",
    "sam-curran":       "Sam Curran",        "moeen-ali":          "Moeen Ali",
    "adil-rashid":      "Adil Rashid",       "mark-wood":          "Mark Wood",
    "jofra-archer":     "Jofra Archer",
}

def _load_json_map(path: Path) -> Dict[str, str]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

TEAM_MAP   = {**TEAM_MAP,   **_load_json_map(_TEAM_FILE)}
PLAYER_MAP = {**PLAYER_MAP, **_load_json_map(_PLAYER_FILE)}

# ── Dynamic caches for squads ───────────────────────────────────────────────────
_SQUAD_CACHE: Dict[str, Any] = {}


def _first_non_empty(*args) -> str:
    """Return first non-empty string from args."""
    for a in args:
        if a and str(a).strip():
            return str(a).strip()
    return ""


def _ensure_squads_for_match(match_key: str) -> Optional[Dict]:
    """Fetch and cache squads for a match, updating global team/player maps."""
    if match_key in _SQUAD_CACHE:
        return _SQUAD_CACHE[match_key]
    if not CREX_AVAILABLE:
        return None
    # Suppress noisy prints from crex_scraper
    old_stdout = sys.stdout
    devnull = None
    try:
        devnull = open(os.devnull, 'w')
        sys.stdout = devnull
        squads = get_squads_from_details(match_key)
    except Exception:
        squads = None
    finally:
        if devnull:
            devnull.close()
        sys.stdout = old_stdout
    _SQUAD_CACHE[match_key] = squads
    if squads:
        # Update team map from squads 't' field
        for team in squads.get("t", []):
            f_key = team.get("f_key", "")
            name = team.get("n", "")
            if f_key and name:
                TEAM_MAP[f_key] = name
                TEAM_MAP[f_key.upper()] = name
                TEAM_MAP[f_key.lower()] = name
                TEAM_MAP[f_key.title()] = name
        # Update player map from squads 'p' field
        for player in squads.get("p", []):
            f_key = player.get("f_key", "")
            name = player.get("n", "")
            if f_key and name:
                PLAYER_MAP[f_key] = name
                PLAYER_MAP[f_key.upper()] = name
                PLAYER_MAP[f_key.lower()] = name
                PLAYER_MAP[f_key.title()] = name
    return squads


def resolve_team(raw: str) -> str:
    if not raw:
        return "TBA"
    s = str(raw).strip()
    for key in (s, s.upper(), s.lower(), s.title()):
        if key in TEAM_MAP:
            return TEAM_MAP[key]
    # slug: "south-africa-national" → "South Africa National"
    pretty = s.replace("-", " ").replace("_", " ").title()
    return TEAM_MAP.get(pretty, pretty)


def resolve_player(raw: str) -> str:
    if not raw:
        return "Unknown"
    s = str(raw).strip()
    for key in (s, s.lower()):
        if key in PLAYER_MAP:
            return PLAYER_MAP[key]
    pretty = s.replace("-", " ").replace("_", " ").title()
    return PLAYER_MAP.get(pretty, pretty)


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

try:
    _term_w = max(os.get_terminal_size().columns, 130)
except OSError:
    _term_w = 140
console = Console(width=_term_w)


def _sh(text: str, n: int) -> str:
    """Shorten text to n chars with ellipsis."""
    s = str(text or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def _ms_to_str(ts: Any) -> str:
    """Convert millisecond UNIX timestamp to local time string."""
    try:
        t = int(ts or 0)
        if t <= 0:
            return "TBD"
        # Convert from milliseconds to seconds and use local timezone
        dt = datetime.fromtimestamp(t / 1000)
        return dt.strftime("%d %b  %H:%M")
    except Exception:
        return "N/A"


def _status(m: Dict) -> str:
    """Derive LIVE / FINISHED / UPCOMING from a match dict."""
    # Normalise fields
    score1 = m.get("score1", "") or ""
    score2 = m.get("score2", "") or ""
    result_str = (m.get("result") or m.get("res") or "").lower()

    # 1. Finished by result keywords
    finished_kw = [
        "won by", "win by", "abandoned", "drawn", "tied", "no result",
        "match over", "stumps", "won the match"
    ]
    if any(kw in result_str for kw in finished_kw):
        return "FINISHED"

    # 2. Innings break is still part of a live match
    if "innings break" in result_str:
        return "LIVE"

    # 3. Delays/postponements => upcoming
    delay_kw = ["toss delayed", "match delayed", "delayed", "suspended"]
    if any(kw in result_str for kw in delay_kw):
        return "UPCOMING"

    # 4. If any score present, the match is in progress or recently concluded
    if score1 or score2:
        return "LIVE"

    # 5. Default to upcoming
    return "UPCOMING"


Q_STYLE = QStyle([
    ("qmark",       "fg:#00ff88 bold"),
    ("question",    "bold"),
    ("answer",      "fg:#ffd700 bold"),
    ("pointer",     "fg:#00ff88 bold"),
    ("highlighted", "fg:#00ff88 bold"),
    ("selected",    "fg:#ffffff"),
    ("separator",   "fg:#444444"),
    ("instruction", "fg:#888888"),
])


def _pause():
    console.print()
    console.print(Padding("[bright_black]  Press Enter to continue[/bright_black]", (0, 0)))
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


def _header_banner(subtitle: str = ""):
    console.print()
    title = Text(" 🏏  CREX CRICKET EXPLORER  🏏 ", style="bold bright_white on dark_green")
    if not CREX_AVAILABLE:
        title = Text(" 🏏  CREX CRICKET EXPLORER  [crex_scraper required] 🏏 ", style="bold bright_white on dark_green")
    console.print(Align.center(title))
    if subtitle:
        console.print(Align.center(Text(subtitle, style="bright_black")))
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
#  DATA FETCHING — requires crex_scraper
# ══════════════════════════════════════════════════════════════════════════════

def _pick(*args) -> str:
    """Return first non-empty string from args."""
    for a in args:
        if a and str(a).strip():
            return str(a).strip()
    return ""


def build_match_list() -> List[Dict[str, Any]]:
    matches: List[Dict] = []

    if CREX_AVAILABLE:
        live_raw    = get_live_matches() or {}
        fixture_raw = get_fixtures(0)   or []
    else:
        live_raw    = {}
        fixture_raw = []

    seen_keys = set()

    # ── Live matches ─────────────────────────────────────────────────────────
    for key, m in live_raw.items():
        t1_code = _first_non_empty(m.get("b"), m.get("t1"), m.get("home"))
        t2_code = _first_non_empty(m.get("c"), m.get("t2"), m.get("away"))
        t1 = resolve_team(t1_code)
        t2 = resolve_team(t2_code)
        seen_keys.add(key)
        matches.append({
            "key":        key,
            "source":     "live",
            "date_str":   _ms_to_str(m.get("ti", 0)),
            "timestamp":  int(m.get("ti") or 0),
            "team1":      t1,
            "team2":      t2,
            "team1_code": t1_code,
            "team2_code": t2_code,
            "score1":     str(m.get("j") or ""),
            "score2":     str(m.get("k") or ""),
            "result":     str(m.get("res") or ""),
            "series":     str(m.get("tn")  or m.get("sn") or ""),
            "venue":      str(m.get("venue") or m.get("v") or ""),
            "f":          m.get("f", 0),
            "raw":        m,
        })

    # ── Fixtures / completed ─────────────────────────────────────────────────
    for f in fixture_raw:
        key = _first_non_empty(f.get("fi"), f.get("f_key"), f.get("id"), f.get("key"))
        if not key or key in seen_keys:
            continue
        t1_code = _first_non_empty(f.get("t1f"), f.get("t1"), f.get("t1_code"), f.get("home"), f.get("b"))
        t2_code = _first_non_empty(f.get("t2f"), f.get("t2"), f.get("t2_code"), f.get("away"), f.get("c"))
        t1 = resolve_team(t1_code)
        t2 = resolve_team(t2_code)
        ts = int(f.get("t") or f.get("start_time") or f.get("ti") or 0)
        # If timestamp is unreasonably small (e.g., < year 2000), treat as missing
        if ts < 1_000_000_000_000:
            ts = 0
        matches.append({
            "key":        key,
            "source":     "fixture",
            "date_str":   _ms_to_str(ts),
            "timestamp":  ts,
            "team1":      t1,
            "team2":      t2,
            "team1_code": t1_code,
            "team2_code": t2_code,
            "score1":     "",
            "score2":     "",
            "result":     str(f.get("stt") or f.get("status") or ""),
            "series":     str(f.get("tn")  or f.get("sn") or ""),
            "venue":      str(f.get("venue") or f.get("v") or ""),
            "f":          f.get("f", 0),
            "raw":        f,
        })
        seen_keys.add(key)

    # Enrich team names using squads data (if available) to resolve unknown codes
    if CREX_AVAILABLE:
        for m in matches:
            try:
                _ensure_squads_for_match(m["key"])
            except Exception:
                pass
            # Re-resolve with potentially updated maps
            m["team1"] = resolve_team(m["team1_code"])
            m["team2"] = resolve_team(m["team2_code"])

    # Sort: live matches first (by timestamp desc), then others (by timestamp desc)
    def _match_sort_key(m: Dict) -> Tuple[int, int]:
        st = _status(m)
        priority = 0 if st == "LIVE" else 1
        return (priority, -int(m.get("timestamp") or 0))
    
    matches.sort(key=_match_sort_key)
    return matches


def _fetch(fn, key: str):
    """Fetch from crex_scraper or return None if unavailable."""
    if CREX_AVAILABLE:
        return fn(key)
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSFORM RAW SCORECARD (SC4) TO DISPLAY FORMAT
# ══════════════════════════════════════════════════════════════════════════════

def _first_int(token: str) -> Optional[int]:
    """Extract the first integer from a token (digits at start)."""
    m = re.match(r'(\d+)', token)
    return int(m.group(1)) if m else None


def _transform_scorecard(sc_data, match_key: str) -> Optional[Dict[str, Any]]:
    """Convert raw SC4 scorecard data into structure expected by display_scorecard."""
    if not sc_data:
        return None

    _ensure_squads_for_match(match_key)

    transformed = {"innings": []}

    for idx, raw_inn in enumerate(sc_data):
        team_code = raw_inn.get("c", "") or raw_inn.get("team_code", "")
        team_name = resolve_team(team_code) if team_code else "Unknown"

        # --- Batting: parse from 'b' array ---
        batting = []
        b_raw = raw_inn.get("b", [])
        for entry in b_raw:
            parts = entry.split(".")
            if len(parts) < 5:
                continue
            code = parts[0]
            # Extract first four numeric values from the rest of the tokens
            nums = []
            for tok in parts[1:]:
                val = _first_int(tok)
                if val is not None:
                    nums.append(val)
                # If token is not numeric at leading part, it will be ignored
                if len(nums) >= 4:
                    break
            if len(nums) < 4:
                continue
            runs, balls, fours, sixes = nums[:4]
            name = PLAYER_MAP.get(code) or resolve_player(code)
            sr = round((runs / balls) * 100, 2) if balls else 0.0
            batting.append({
                "n": name,
                "s": "",   # dismissal info TBD
                "r": runs,
                "b": balls,
                "4s": fours,
                "6s": sixes,
                "sr": sr,
            })

        # --- Bowling: parse from 'a' array ---
        bowling = []
        for a_str in raw_inn.get("a", []):
            parts = a_str.split(".")
            if len(parts) < 5:
                continue
            code = parts[0]
            try:
                runs   = int(parts[1])
                balls  = int(parts[2])
                # Some a entries might have extra slash suffix; handle safely
                fours_val = parts[3]  # not used but parsed safely
                sixes_val = parts[4]
                # Ensure fours and sixes are integers if they are pure numeric, otherwise ignore
                # Maidens and wickets are not directly available; set defaults
            except (ValueError, IndexError):
                continue
            name = PLAYER_MAP.get(code) or resolve_player(code)
            overs = balls / 6.0
            overs_str = f"{balls//6}.{balls%6}" if balls else "0.0"
            econ = round(runs / overs, 2) if overs else 0.0
            bowling.append({
                "n": name,
                "o": overs_str,
                "m": 0,
                "r": runs,
                "w": 0,
                "e": econ,
                "nb": 0,
                "wd": 0,
            })

        # --- Extras: from 'e' field (dot-separated ints) ---
        e_str = raw_inn.get("e", "")
        extras_val = 0
        if e_str:
            for part in e_str.split("."):
                try:
                    extras_val += int(part)
                except ValueError:
                    pass

        # --- Total & overs: from 'd' field ---
        d_val = raw_inn.get("d", "")
        score_str = d_val
        overs_str_total = ""
        total_str = ""
        m = re.search(r'(\d+)/(\d+)\((\d+)', d_val)
        if m:
            tot_runs = int(m.group(1))
            tot_wkts = m.group(2)
            tot_balls = int(m.group(3))
            overs_f = tot_balls / 6.0
            overs_str_total = f"{overs_f:.1f}"
            score_str = f"{tot_runs}/{tot_wkts}"
            total_str = f"Total: {score_str} in {overs_str_total} overs"
            # If extras not parsed, we can compute as tot_runs - sum(batsmen runs)
            if extras_val == 0:
                bat_sum = sum(b["r"] for b in batting)
                extras_val = max(0, tot_runs - bat_sum)

        extras_display = f"Extras: {extras_val}" if extras_val else ""

        # Innings name
        ordinal = idx + 1
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(ordinal, "th")
        inn_name = f"{team_name} {ordinal}{suffix} Innings"

        inn = {
            "i":         inn_name,
            "team_code": team_code,
            "batting":   batting,
            "bowling":   bowling,
            "fow":       [],
            "extras":    extras_display,
            "score":     score_str,
            "overs":     overs_str_total,
            "total":     total_str,
        }
        transformed["innings"].append(inn)

    return transformed


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY: MATCH LIST TABLE
# ══════════════════════════════════════════════════════════════════════════════

def display_match_list(matches: List[Dict]) -> None:
    table = Table(
        box=box.HEAVY_HEAD,
        border_style="dark_green",
        header_style="bold bright_white on grey23",
        show_lines=False,
        padding=(0, 1),
        min_width=100,
    )
    table.add_column("#",       style="bright_black bold", no_wrap=True, width=4,  justify="right")
    table.add_column("STATUS",  width=9,  justify="center")
    table.add_column("DATE",    style="bright_black", width=12, no_wrap=True)
    table.add_column("TEAM 1",  style="bold yellow",   width=22)
    table.add_column("SCORE",   style="bright_white",  width=14, justify="center", no_wrap=True)
    table.add_column("TEAM 2",  style="bold yellow",   width=22)
    table.add_column("SCORE",   style="bright_white",  width=14, justify="center", no_wrap=True)
    table.add_column("RESULT / SERIES",                width=28)

    for i, m in enumerate(matches, 1):
        st = _status(m)
        if st == "LIVE":
            badge = Text("● LIVE",  style="bold red")
            rs = ""
        elif st == "FINISHED":
            badge = Text("✓ DONE",  style="bold green")
            rs = "dim"
        else:
            badge = Text("◷ SOON",  style="bold cyan")
            rs = "bright_black"

        result_info = _sh(m["result"] or m["series"], 29)
        table.add_row(
            str(i), badge, m["date_str"],
            _sh(m["team1"], 21),
            _sh(m["score1"] or "—", 13),
            _sh(m["team2"], 21),
            _sh(m["score2"] or "—", 13),
            result_info,
            style=rs,
        )

    console.print(table)


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY: SCORECARD
# ══════════════════════════════════════════════════════════════════════════════

def display_scorecard(data: Any, match: Dict) -> None:
    if not data:
        console.print(Panel("[yellow]No scorecard data.[/yellow]", border_style="yellow"))
        _pause(); return

    # Normalise
    if isinstance(data, dict):
        innings_list = data.get("innings") or [data]
    elif isinstance(data, list):
        innings_list = data
    else:
        innings_list = [data]

    # Top banner
    console.print(Rule(
        f"  [bold yellow]{match['team1']}[/bold yellow]"
        f"  [white]vs[/white]  "
        f"[bold yellow]{match['team2']}[/bold yellow]"
        f"  [bright_black]—[/bright_black]  [bold green]SCORECARD[/bold green]",
        style="green",
    ))

    for idx, inn in enumerate(innings_list, 1):
        inn_name  = _sh(str(inn.get("i") or inn.get("name") or f"Innings {idx}"), 60)
        inn_score = str(inn.get("score") or inn.get("s") or "")
        inn_overs = str(inn.get("overs") or inn.get("ov") or "")

        # Innings heading
        heading_parts = [f"[bold cyan]{inn_name}[/bold cyan]"]
        if inn_score:
            heading_parts.append(f"  [bold bright_white]{inn_score}[/bold bright_white]")
        if inn_overs:
            heading_parts.append(f"  [bright_black]({inn_overs} ov)[/bright_black]")
        console.print()
        console.print(Rule("".join(heading_parts), style="cyan"))

        # ── Batting table ────────────────────────────────────────────────────
        batting = inn.get("batting") or inn.get("bat") or []
        if batting:
            bt = Table(
                box=box.SIMPLE_HEAD, border_style="cyan",
                header_style="bold cyan", padding=(0, 1), show_edge=True,
            )
            bt.add_column("BATTER",     style="bold bright_white",  width=22)
            bt.add_column("DISMISSAL",  style="bright_black",        width=32)
            bt.add_column("R",  justify="right", style="bold yellow",   width=5)
            bt.add_column("B",  justify="right", style="white",          width=5)
            bt.add_column("4s", justify="right", style="bold green",     width=4)
            bt.add_column("6s", justify="right", style="bold magenta",   width=4)
            bt.add_column("SR", justify="right", style="bright_cyan",    width=7)

            for b in batting:
                raw_n = _pick(b.get("n"), b.get("player"), b.get("name"))
                name  = resolve_player(raw_n)
                dism  = _pick(b.get("s"), b.get("status"), b.get("how_out"))
                runs  = str(b.get("r")  or b.get("runs",  "") or "")
                balls = str(b.get("b")  or b.get("balls", "") or "")
                fours = str(b.get("4s") or b.get("fours", "") or "")
                sixes = str(b.get("6s") or b.get("sixes", "") or "")
                sr    = str(b.get("sr") or b.get("strike_rate", "") or "")

                # highlight not out
                name_styled = f"[bold green]{name}[/bold green]" if "not out" in dism.lower() else name
                runs_styled = Text(runs, style="bold yellow") if runs else Text("")

                bt.add_row(name_styled, _sh(dism, 32), runs_styled, balls, fours, sixes, sr)

            console.print(bt)

        # Extras / Total
        extras = str(inn.get("extras") or inn.get("ex") or "")
        total  = str(inn.get("total")  or inn.get("tot") or "")
        parts  = []
        if extras: parts.append(f"[bright_black]{extras}[/bright_black]")
        if total:  parts.append(f"[bold]{total}[/bold]")
        if parts:
            console.print("  " + "    ".join(parts))

        # ── Bowling table ────────────────────────────────────────────────────
        bowling = inn.get("bowling") or inn.get("bowl") or []
        if bowling:
            console.print()
            bwt = Table(
                box=box.SIMPLE_HEAD, border_style="magenta",
                header_style="bold magenta", padding=(0, 1), show_edge=True,
            )
            bwt.add_column("BOWLER", style="bold bright_white",  width=22)
            bwt.add_column("O",   justify="right",               width=5)
            bwt.add_column("M",   justify="right",               width=5)
            bwt.add_column("R",   justify="right", style="yellow",     width=5)
            bwt.add_column("W",   justify="right", style="bold red",   width=4)
            bwt.add_column("ECON",justify="right", style="bright_blue",width=6)
            bwt.add_column("NB",  justify="right", style="bright_black",width=4)
            bwt.add_column("WD",  justify="right", style="bright_black",width=4)

            for b in bowling:
                raw_n = _pick(b.get("n"), b.get("bowler"), b.get("name"))
                name  = resolve_player(raw_n)
                w_val = str(b.get("w") or b.get("wickets", "") or "")
                w_styled = Text(w_val, style="bold red") if w_val and w_val != "0" else Text(w_val or "")
                bwt.add_row(
                    name,
                    str(b.get("o") or b.get("overs",   "") or ""),
                    str(b.get("m") or b.get("maidens", "") or ""),
                    str(b.get("r") or b.get("runs",    "") or ""),
                    w_styled,
                    str(b.get("e") or b.get("econ") or b.get("economy", "") or ""),
                    str(b.get("nb") or b.get("no_ball", "") or ""),
                    str(b.get("wd") or b.get("wide",    "") or ""),
                )
            console.print(bwt)

        # ── Fall of Wickets ──────────────────────────────────────────────────
        fow = inn.get("fow") or inn.get("fall_of_wickets") or []
        if fow and isinstance(fow, list):
            pieces = []
            for f in fow:
                pname = resolve_player(_pick(f.get("n"), f.get("player"), "?"))
                pieces.append(
                    f"[yellow]{f.get('w','?')}[/yellow]-"
                    f"[white]{f.get('r','?')}[/white] "
                    f"[bright_black]({pname}, {f.get('o','?')} ov)[/bright_black]"
                )
            console.print()
            console.print("  [bold]Fall of Wickets:[/bold]  " + "  ".join(pieces))

    console.print()
    _pause()



# ══════════════════════════════════════════════════════════════════════════════

def display_squads(data: Any, match: Dict) -> None:
    if not data:
        console.print(Panel("[yellow]No squad data.[/yellow]", border_style="yellow"))
        _pause(); return

    def _squad_table(title: str, players: List[Dict]) -> Table:
        t = Table(
            title=f"[bold yellow]{title}[/bold yellow]",
            box=box.SIMPLE_HEAD,
            header_style="bold bright_white",
            border_style="yellow",
            padding=(0, 1),
        )
        t.add_column("#",    style="bright_black", width=3, justify="right")
        t.add_column("NAME", style="bright_white",  width=26)
        t.add_column("ROLE", style="bright_blue",   width=20)
        for i, p in enumerate(players, 1):
            raw_n = _pick(p.get("n"), p.get("name"), p.get("player"))
            name  = resolve_player(raw_n) if raw_n else "N/A"
            role  = _pick(p.get("role"), p.get("r"), p.get("batting_style"))
            t.add_row(str(i), name, _sh(role, 20))
        return t

    t1p = data.get("t1") or data.get("squad1") or data.get("home") or []
    t2p = data.get("t2") or data.get("squad2") or data.get("away") or []
    all_p = data.get("p") or data.get("players") or data.get("squad") or []

    console.print(Rule(
        f"  [bold yellow]{match['team1']}[/bold yellow]  [white]vs[/white]  "
        f"[bold yellow]{match['team2']}[/bold yellow]  [bold green]— SQUADS[/bold green]",
        style="yellow",
    ))
    console.print()

    if t1p and t2p:
        console.print(Columns([
            _squad_table(match["team1"], t1p),
            _squad_table(match["team2"], t2p),
        ], equal=True))
    elif t1p:
        console.print(_squad_table(match["team1"], t1p))
    elif t2p:
        console.print(_squad_table(match["team2"], t2p))
    elif all_p:
        console.print(_squad_table("Squad", all_p))
    else:
        from rich.syntax import Syntax
        console.print("[yellow]Unrecognised squad structure — raw JSON:[/yellow]")
        console.print(Syntax(json.dumps(data, indent=2), "json", theme="dracula"))

    console.print()
    _pause()


# ══════════════════════════════════════════════════════════════════════════════
#  DISPLAY: RAW JSON
# ══════════════════════════════════════════════════════════════════════════════

def display_raw_json(data: Any, title: str) -> None:
    from rich.syntax import Syntax
    js = json.dumps(data, indent=2, ensure_ascii=False)
    console.print(Panel(
        Syntax(js, "json", theme="dracula", word_wrap=True),
        title=f"[bold bright_green]{title}[/bold bright_green]",
        border_style="bright_green",
    ))
    _pause()


# ══════════════════════════════════════════════════════════════════════════════
#  MATCH DETAIL SUB-MENU
# ══════════════════════════════════════════════════════════════════════════════

def show_match_menu(match: Dict) -> None:
    while True:
        console.clear()
        _header_banner()

        st = _status(match)
        badge_map = {"LIVE": "🔴 LIVE", "FINISHED": "✓ FINISHED", "UPCOMING": "◷ UPCOMING"}
        badge     = badge_map.get(st, st)
        border_map = {"LIVE": "red", "FINISHED": "green", "UPCOMING": "cyan"}
        border    = border_map.get(st, "white")

        # Match card
        info_lines = []
        if match["score1"] or match["score2"]:
            if match["score1"]:
                info_lines.append(f"[bold yellow]{match['team1']}[/bold yellow]  [bright_white]{match['score1']}[/bright_white]")
            if match["score2"]:
                info_lines.append(f"[bold yellow]{match['team2']}[/bold yellow]  [bright_white]{match['score2']}[/bright_white]")
        if match["result"]:
            info_lines.append(f"[bright_black]{match['result']}[/bright_black]")
        if match["series"]:
            info_lines.append(f"[bright_black]{match['series']}[/bright_black]")
        if match["venue"]:
            info_lines.append(f"[bright_black]📍 {match['venue']}[/bright_black]")

        card_body = (
            f"\n[bold yellow]{match['team1']}[/bold yellow]"
            f"  [white]vs[/white]  "
            f"[bold yellow]{match['team2']}[/bold yellow]"
            f"  [bright_black]|[/bright_black]  {badge}"
            f"  [bright_black]|[/bright_black]  [cyan]{match['date_str']}[/cyan]\n"
        )
        if info_lines:
            card_body += "\n".join(info_lines) + "\n"

        console.print(Panel(card_body, border_style=border, padding=(0, 2)))
        console.print()

        choices = [
            "📋   Scorecard",
            "👥   Squads",
            "🗂    Raw JSON",
            "💾   Save All to Disk",
            "← Back",
        ]

        choice = questionary.select(
            "Choose a view:",
            choices=choices,
            style=Q_STYLE,
        ).ask()

        if choice is None or "Back" in choice:
            break

        key = match["key"]
        console.clear()
        _header_banner()

        if "Scorecard" in choice:
            with console.status("[bold green]Fetching scorecard…"):
                sc = _fetch(get_scorecard, key)
            if sc:
                if CREX_AVAILABLE:
                    try: save_json(sc, key, "scorecard")
                    except: pass
                # Transform raw scorecard to display format if real data
                display_sc = _transform_scorecard(sc, key) if CREX_AVAILABLE else sc
                if display_sc:
                    display_scorecard(display_sc, match)
                else:
                    console.print("[red]Failed to decode scorecard.[/red]")
                    _pause()
            else:
                console.print("[red]No scorecard data.[/red]")
                _pause()

        elif "Squads" in choice:
            with console.status("[bold green]Fetching squads…"):
                sq = _fetch(get_squads_from_details, key)
            if sq:
                if CREX_AVAILABLE:
                    try: save_json(sq, key, "squads")
                    except: pass
                # If the squads data doesn't contain separate team lists, attempt to build from scorecard
                if not (sq.get("t1") or sq.get("t2") or sq.get("squad1") or sq.get("squad2")):
                    # Derive squads from scorecard for live/completed matches
                    with console.status("[bold green]Deriving squads from scorecard…"):
                        sc = _fetch(get_scorecard, key)
                    if sc:
                        transformed = _transform_scorecard(sc, key)
                        innings_list = transformed.get("innings", []) if transformed else []
                        if innings_list:
                            code1 = match.get("team1_code", "")
                            code2 = match.get("team2_code", "")
                            squads_by_code = {code1: [], code2: []}
                            for inn in innings_list:
                                bat_code = inn.get("team_code")
                                if not bat_code:
                                    inn_team_name = inn["i"].split(" ")[0]
                                    if inn_team_name == match["team1"]:
                                        bat_code = code1
                                    elif inn_team_name == match["team2"]:
                                        bat_code = code2
                                bowl_code = None
                                if bat_code == code1:
                                    bowl_code = code2
                                elif bat_code == code2:
                                    bowl_code = code1
                                for b in inn.get("batting", []):
                                    name = b["n"]
                                    target = squads_by_code.get(bat_code, [])
                                    if not any(p["n"] == name for p in target):
                                        target.append({"n": name, "role": "Batsman"})
                                for bo in inn.get("bowling", []):
                                    name = bo["n"]
                                    if bowl_code is not None:
                                        target = squads_by_code.get(bowl_code, [])
                                        if not any(p["n"] == name for p in target):
                                            target.append({"n": name, "role": "Bowler"})
                            squad1 = squads_by_code.get(code1, [])
                            squad2 = squads_by_code.get(code2, [])
                            if squad1 or squad2:
                                sq = {"t1": squad1, "t2": squad2}
                display_squads(sq, match)
            else:
                console.print("[red]No squad data.[/red]"); _pause()

        elif "Raw JSON" in choice:
            with console.status("[bold green]Fetching scorecard…"):
                sc = _fetch(get_scorecard, key)
            if sc:
                display_raw_json(sc, f"Raw Scorecard — {key}")
            else:
                console.print("[red]No data.[/red]"); _pause()

        elif "Save All" in choice:
            if CREX_AVAILABLE:
                with console.status("[bold green]Scraping all data…"):
                    try:
                        from crex_scraper import scrape_match
                        result = scrape_match(key, one_off=True, poll_interval=10, max_polls=1)
                        if result:
                            console.print(f"[green]✓ Saved all data for [bold]{key}[/bold][/green]")
                        else:
                            console.print("[red]Scrape returned no data.[/red]")
                    except Exception as e:
                        console.print(f"[red]Error: {e}[/red]")
            else:
                console.print("[yellow]Save requires crex_scraper — library not available.[/yellow]")
            _pause()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  DATA FETCHING — with progress reporting
# ══════════════════════════════════════════════════════════════════════════════

def _load_matches_with_progress() -> List[Dict[str, Any]]:
    """Fetch and build match list with visual progress indicators."""
    if not CREX_AVAILABLE:
        # Quick fallback: just return empty list (will be handled by main)
        return []
    
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    
    matches: List[Dict] = []
    live_raw = {}
    fixture_raw = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]{task.description}[/bold green]"),
        BarColumn(bar_width=40),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        # ── Step 1: Fetch live matches ─────────────────────────────────────────
        task1 = progress.add_task("Connecting to crex.live…", total=1)
        try:
            live_raw = get_live_matches() or {}
            progress.update(task1, completed=1, description="Live matches fetched")
        except Exception as e:
            progress.update(task1, completed=1, description=f"[red]Failed to fetch live: {e}[/red]")
            live_raw = {}
            time.sleep(0.4)
        
        # ── Step 2: Fetch fixtures ────────────────────────────────────────────
        task2 = progress.add_task("Fetching upcoming fixtures…", total=1)
        try:
            fixture_raw = get_fixtures(0) or []
            progress.update(task2, completed=1, description="Fixtures fetched")
        except Exception as e:
            progress.update(task2, completed=1, description=f"[red]Failed to fetch fixtures: {e}[/red]")
            fixture_raw = []
            time.sleep(0.4)
        
        # ── Step 3: Build match list ──────────────────────────────────────────
        task3 = progress.add_task("Building match list…", total=1)
        seen_keys = set()
        
        # Process live matches
        for key, m in live_raw.items():
            t1_code = _first_non_empty(m.get("b"), m.get("t1"), m.get("home"))
            t2_code = _first_non_empty(m.get("c"), m.get("t2"), m.get("away"))
            t1 = resolve_team(t1_code)
            t2 = resolve_team(t2_code)
            seen_keys.add(key)
            matches.append({
                "key":        key,
                "source":     "live",
                "date_str":   _ms_to_str(m.get("ti", 0)),
                "timestamp":  int(m.get("ti") or 0),
                "team1":      t1,
                "team2":      t2,
                "team1_code": t1_code,
                "team2_code": t2_code,
                "score1":     str(m.get("j") or ""),
                "score2":     str(m.get("k") or ""),
                "result":     str(m.get("res") or ""),
                "series":     str(m.get("tn")  or m.get("sn") or ""),
                "venue":      str(m.get("venue") or m.get("v") or ""),
                "f":          m.get("f", 0),
                "raw":        m,
            })
        
        # Process fixtures
        for f in fixture_raw:
            key = _first_non_empty(f.get("fi"), f.get("f_key"), f.get("id"), f.get("key"))
            if not key or key in seen_keys:
                continue
            t1_code = _first_non_empty(f.get("t1f"), f.get("t1"), f.get("t1_code"), f.get("home"), f.get("b"))
            t2_code = _first_non_empty(f.get("t2f"), f.get("t2"), f.get("t2_code"), f.get("away"), f.get("c"))
            t1 = resolve_team(t1_code)
            t2 = resolve_team(t2_code)
            ts = int(f.get("t") or f.get("start_time") or f.get("ti") or 0)
            if ts < 1_000_000_000_000:
                ts = 0
            matches.append({
                "key":        key,
                "source":     "fixture",
                "date_str":   _ms_to_str(ts),
                "timestamp":  ts,
                "team1":      t1,
                "team2":      t2,
                "team1_code": t1_code,
                "team2_code": t2_code,
                "score1":     "",
                "score2":     "",
                "result":     str(f.get("stt") or f.get("status") or ""),
                "series":     str(f.get("tn")  or f.get("sn") or ""),
                "venue":      str(f.get("venue") or f.get("v") or ""),
                "f":          f.get("f", 0),
                "raw":        f,
            })
            seen_keys.add(key)
        
        progress.update(task3, completed=1, description=f"Match list built ({len(matches)} total)")
        time.sleep(0.3)
        
        # ── Step 4: Enrich with squads ─────────────────────────────────────────
        if matches:
            task4 = progress.add_task(f"Loading squads for {len(matches)} matches…", total=len(matches))
            for idx, m in enumerate(matches):
                try:
                    _ensure_squads_for_match(m["key"])
                except Exception:
                    pass
                # Re-resolve with potentially updated maps
                m["team1"] = resolve_team(m["team1_code"])
                m["team2"] = resolve_team(m["team2_code"])
                progress.update(task4, advance=1)
            progress.update(task4, description="Squads loaded")
            time.sleep(0.3)
        
        # ── Step 5: Sort ───────────────────────────────────────────────────────
        task5 = progress.add_task("Sorting matches (live first)…", total=1)
        def _match_sort_key(m: Dict) -> Tuple[int, int]:
            st = _status(m)
            priority = 0 if st == "LIVE" else 1
            return (priority, -int(m.get("timestamp") or 0))
        matches.sort(key=_match_sort_key)
        progress.update(task5, completed=1)
        time.sleep(0.2)
    
    return matches


def main() -> None:
    console.clear()
    _header_banner("Fetching live cricket data…")
    
    matches = _load_matches_with_progress()
    
    if not matches:
        console.print("[red]No matches found.[/red]")
        sys.exit(0)
    
    console.print(f"[green]✓ Loaded {len(matches)} matches[/green]")
    time.sleep(0.6)
    
    while True:
        console.clear()
        _header_banner(
            f"{'🟢 crex_scraper connected' if CREX_AVAILABLE else '⚠  crex_scraper not installed — install to use'}  |  {len(matches)} matches"
        )
        
        display_match_list(matches)
        
        # Build numbered choices
        match_choices = []
        for i, m in enumerate(matches, 1):
            st = _status(m)
            badge = {"LIVE": "🔴", "FINISHED": "✓ ", "UPCOMING": "◷ "}.get(st, "  ")
            t1 = _sh(m["team1"], 22)
            t2 = _sh(m["team2"], 22)
            sc = f"  [{m['score1']}]" if m["score1"] else ""
            match_choices.append(f"{i:>2}. {badge} {t1:<22} vs  {t2}{sc}")
        
        all_choices = match_choices + ["⟳  Refresh", "✕  Exit"]
        
        choice = questionary.select(
            "Select a match to open:",
            choices=all_choices,
            style=Q_STYLE,
            use_shortcuts=False,
        ).ask()
        
        if choice is None or "Exit" in choice:
            console.print("\n[bold yellow]Goodbye! 🏏[/bold yellow]\n")
            break
        elif "Refresh" in choice:
            with console.status("[bold green]Refreshing…"):
                matches = build_match_list()
            continue
        
        try:
            idx = int(choice.strip().split(".")[0].strip()) - 1
            show_match_menu(matches[idx])
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Goodbye![/yellow]")
        sys.exit(0)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        console.print(f"[red]Fatal error: {exc}[/red]")
        sys.exit(1)