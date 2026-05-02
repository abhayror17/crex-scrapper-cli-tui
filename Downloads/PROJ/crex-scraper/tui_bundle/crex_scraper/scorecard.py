"""Decode SC4 scorecard format into readable batting/bowling tables."""

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class BatterStats:
    """Batting statistics."""
    order: int = 0
    code: str = ""
    name: str = ""
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    strike_rate: float = 0.0
    dismissal: str = ""
    out_text: str = ""


@dataclass
class BowlerStats:
    """Bowling statistics."""
    code: str = ""
    name: str = ""
    overs: str = "0"
    balls: int = 0
    runs: int = 0
    wickets: int = 0
    economy: float = 0.0
    dot_balls: int = 0
    maidens: int = 0


def decode_scorecard(sc4_data: List[Any], team_map: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Decode SC4 scorecard array into structured format.
    
    SC4 format:
    [
      {  // Inning 1
        "a": ["PLAYER_CODE1^NAME1^...", "PLAYER_CODE2^NAME2^..."],
        "b": [BOWLER_ARRAY],
        "c": batting_order_array,
        "d": ...
      },
      {  // Inning 2 (if second innings)
        ...
      }
    ]
    
    Returns:
        {
            "innings": [
                {
                    "batting": [BatterStats, ...],
                    "bowling": [BowlerStats, ...],
                    "total": {"runs": ..., "wickets": ..., "overs": ...},
                    "extras": {"run": 0, "wide": 0, "no_ball": 0, "bye": 0, "leg_bye": 0}
                }
            ]
        }
    """
    team_map = team_map or {}
    decoded = {"innings": []}
    
    for inning_idx, inning_data in enumerate(sc4_data):
        inning = {
            "batting": [],
            "bowling": [],
            "total": {},
            "extras": {},
            "raw": inning_data  # Preserve raw for debugging
        }
        
        # Decode batting from 'a' array and 'c' (order)
        a_array = inning_data.get("a", [])
        c_array = inning_data.get("c", [])
        
        if a_array:
            for i, player_str in enumerate(a_array):
                # Format: "CODE^NAME^someOtherFields^..."
                # Regex: first two fields are code and name separated by ^
                if player_str and isinstance(player_str, str):
                    parts = player_str.split("^")
                    code = parts[0] if parts else ""
                    name = parts[1] if len(parts) > 1 else ""
                    
                    # Get order from 'c' array if available
                    if isinstance(c_array, list) and i < len(c_array):
                        order = c_array[i]
                    else:
                        order = i + 1
                    
                    # Convert order to int safely
                    try:
                        order_int = int(order)
                    except (ValueError, TypeError):
                        order_int = i + 1
                    
                    # Decode dismissal from scorecard 'b' array
                    dismissal = ""
                    b_array = inning_data.get("b", [])
                    if b_array and i < len(b_array):
                        dismissal = _decode_dismissal(b_array[i])
                    
                    batter = BatterStats(
                        order=order_int,
                        code=code,
                        name=name or team_map.get(code, code),
                        runs=0,
                        balls=0,
                        fours=0,
                        sixes=0,
                        strike_rate=0.0,
                        dismissal=dismissal,
                        out_text=dismissal
                    )
                    inning["batting"].append(asdict(batter))
        
        # Decode total from 'c' summary
        c_val = inning_data.get("c", "")
        if isinstance(c_val, list):
            # Convert list to string representation
            c_str = "-".join(str(x) for x in c_val)
        else:
            c_str = str(c_val)
        
        # Parse "160/5 (20.0 Ovs)" → total runs, wickets, overs
        total_match = re.search(r'(\d+)/(\d+)\s*\(([^)]*)\)', c_str)
        if total_match:
            inning["total"] = {
                "runs": int(total_match.group(1)),
                "wickets": int(total_match.group(2)),
                "overs": total_match.group(3).strip()
            }
        else:
            inning["total"] = {"runs": 0, "wickets": 0, "overs": ""}
        
        # Extras from 'd' array
        extras_array = inning_data.get("d", [])
        if extras_array and len(extras_array) >= 4:
            def _to_int(val, default=0):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return default
            
            extras_map = {
                "run": _to_int(extras_array[0]),
                "wide": _to_int(extras_array[1]) if len(extras_array) > 1 else 0,
                "no_ball": _to_int(extras_array[2]) if len(extras_array) > 2 else 0,
                "bye": _to_int(extras_array[3]) if len(extras_array) > 3 else 0,
                "leg_bye": _to_int(extras_array[4]) if len(extras_array) > 4 else 0
            }
            inning["extras"] = extras_map
            # Add extras to total if not already included
            total_runs = inning["total"].get("runs", 0)
            inning["total"]["runs_with_extras"] = total_runs + extras_map.get("run", 0)
        
        decoded["innings"].append(inning)
    
    return decoded


def _decode_dismissal(b_value: Any) -> str:
    """
    Decode dismissal from 'b' array element.
    Common codes:
      0 = not out
      1 = bowled
      2 = caught
      3 = lbw
      4 = run out
      5 = stumped
      6 = hit wicket
      8 = retired
    """
    if not b_value:
        return "not out"
    
    try:
        val = int(b_value) if isinstance(b_value, (int, float, str)) else 0
    except (ValueError, TypeError):
        return "unknown"
    
    dismissal_map = {
        0: "not out",
        1: "bowled",
        2: "caught",
        3: "lbw",
        4: "run out",
        5: "stumped",
        6: "hit wicket",
        7: "obstructing field",
        8: "retired",
        9: "timed out"
    }
    return dismissal_map.get(val, "unknown")


def format_overs(overs: Any) -> str:
    """Format overs string nicely."""
    if not overs:
        return "0.0"
    s = str(overs).strip()
    # Already in "x.x" format
    if re.match(r'^\d+\.\d+$', s):
        return s
    # Try to convert from integer balls
    try:
        balls = int(s)
        return f"{balls // 6}.{balls % 6}"
    except ValueError:
        return s


def calculate_strike_rate(runs: int, balls: int) -> float:
    """Calculate strike rate safely."""
    if not balls:
        return 0.0
    return round((runs / balls) * 100, 2)


def calculate_economy(runs: int, balls: int) -> float:
    """Calculate economy rate (runs per over)."""
    if not balls:
        return 0.0
    return round((runs / balls) * 6, 2)
