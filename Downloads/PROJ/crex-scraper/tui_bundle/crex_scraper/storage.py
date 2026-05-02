"""Storage layer: SQLite state + JSON files (backward compatible)."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from threading import Lock

from .config import get_storage_config, get_export_config
from .logging import get_logger

logger = get_logger(__name__)

_config = get_storage_config()
DB_PATH = _config.get("db_path", "crex_data.db")
DATA_ROOT = Path(_config.get("data_root", "data"))
JSON_FALLBACK = _config.get("json_fallback", True)

# Ensure directories exist
DATA_ROOT.mkdir(exist_ok=True, parents=True)


# SQLite state management
class StateDB:
    """Thread-safe SQLite state store."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.lock = Lock()
        self._init_db()
    
    def _init_db(self):
        """Create tables with WAL mode for concurrency."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            c = conn.cursor()
            
            # Match state table
            c.execute('''
                CREATE TABLE IF NOT EXISTS match_state (
                    match_key TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'scheduled',
                    scheduled_time TIMESTAMP,
                    last_scraped TIMESTAMP,
                    scraped_count INTEGER DEFAULT 0,
                    info_saved BOOLEAN DEFAULT 0,
                    squads_saved BOOLEAN DEFAULT 0,
                    scorecard_saved BOOLEAN DEFAULT 0,
                    live_saved BOOLEAN DEFAULT 0,
                    live_updates INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for fast queries
            c.execute('CREATE INDEX IF NOT EXISTS idx_status ON match_state(status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_scheduled ON match_state(scheduled_time)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_updated ON match_state(updated_at)')
            
            # Scrape history (for metrics/audit)
            c.execute('''
                CREATE TABLE IF NOT EXISTS scrape_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_key TEXT NOT NULL,
                    scrape_type TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    success BOOLEAN,
                    error TEXT,
                    duration_ms INTEGER,
                    records_count INTEGER
                )
            ''')
            
            # System metrics
            c.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    labels TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
    
    def upsert_match(
        self,
        match_key: str,
        status: Optional[str] = None,
        scheduled_time: Optional[str] = None,
        **fields
    ) -> None:
        """Insert or update match state."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            c = conn.cursor()
            
            # Check if exists
            c.execute('SELECT 1 FROM match_state WHERE match_key = ?', (match_key,))
            exists = c.fetchone() is not None
            
            if exists:
                # Build UPDATE dynamically
                set_parts = []
                params = []
                if status is not None:
                    set_parts.append("status = ?")
                    params.append(status)
                if scheduled_time is not None:
                    set_parts.append("scheduled_time = ?")
                    params.append(scheduled_time)
                for k, v in fields.items():
                    set_parts.append(f"{k} = ?")
                    params.append(v)
                set_parts.append("updated_at = ?")
                params.append(datetime.now(timezone.utc).isoformat())
                params.append(match_key)
                
                c.execute(f'''
                    UPDATE match_state 
                    SET {', '.join(set_parts)}
                    WHERE match_key = ?
                ''', params)
            else:
                # INSERT
                columns = ["match_key"]
                values = [match_key]
                placeholders = ["?"]
                if status:
                    columns.append("status")
                    values.append(status)
                    placeholders.append("?")
                if scheduled_time:
                    columns.append("scheduled_time")
                    values.append(scheduled_time)
                    placeholders.append("?")
                for k, v in fields.items():
                    columns.append(k)
                    values.append(v)
                    placeholders.append("?")
                
                c.execute(f'''
                    INSERT INTO match_state 
                    ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                ''', values)
            
            conn.commit()
            conn.close()
    
    def mark_scraped(
        self,
        match_key: str,
        scrape_type: str,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
        records: Optional[int] = None
    ):
        """Record a scrape attempt."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            c = conn.cursor()
            
            # Update scrape history
            c.execute('''
                INSERT INTO scrape_history 
                (match_key, scrape_type, completed_at, success, error, duration_ms, records_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                match_key,
                scrape_type,
                datetime.now(timezone.utc).isoformat(),
                success,
                error[:500] if error else None,
                duration_ms,
                records
            ))
            
            # Update match state
            c.execute('''
                UPDATE match_state 
                SET scraped_count = scraped_count + 1,
                    updated_at = ?,
                    error_count = error_count + ?
                WHERE match_key = ?
            ''', (
                datetime.now(timezone.utc).isoformat(),
                0 if success else 1,
                match_key
            ))
            
            if success:
                # Mark specific data as saved
                field_map = {
                    "info": "info_saved",
                    "squads": "squads_saved",
                    "scorecard": "scorecard_saved",
                    "live": "live_saved",
                }
                if scrape_type in field_map:
                    c.execute(f'''
                        UPDATE match_state 
                        SET {field_map[scrape_type]} = 1,
                            live_updates = CASE WHEN ? = 'live' THEN live_updates + 1 ELSE live_updates END
                        WHERE match_key = ?
                    ''', (scrape_type, match_key))
            
            conn.commit()
            conn.close()
    
    def get_match_state(self, match_key: str) -> Optional[Dict]:
        """Get match state by key."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM match_state WHERE match_key = ?', (match_key,))
            row = c.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def get_matches_needing_scrape(self, scrape_type: str, max_age_hours: int = 24) -> List[Dict]:
        """Get matches that need a specific scrape type (e.g., info not saved yet)."""
        field_map = {
            "info": "info_saved",
            "squads": "squads_saved",
            "scorecard": "scorecard_saved",
            "live": "live_saved",
        }
        field = field_map.get(scrape_type)
        if not field:
            return []
        
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(f'''
                SELECT match_key, status, scheduled_time 
                FROM match_state 
                WHERE {field} = 0 
                AND status != 'completed'
                AND (
                    scheduled_time IS NULL 
                    OR datetime(scheduled_time) > datetime('now', '-{max_age_hours} hours')
                )
                ORDER BY updated_at ASC
                LIMIT 50
            ''')
            rows = c.fetchall()
            conn.close()
            return [dict(r) for r in rows]
    
    def get_stats(self) -> Dict:
        """Get overall statistics."""
        with self.lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM match_state")
            total = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM match_state WHERE status = 'live'")
            live = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM match_state WHERE status = 'scheduled'")
            scheduled = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM match_state WHERE info_saved = 1")
            has_info = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM scrape_history WHERE success = 1")
            successful_scrapes = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM scrape_history WHERE success = 0")
            failed_scrapes = c.fetchone()[0]
            
            conn.close()
            
            return {
                "total_matches": total,
                "live_matches": live,
                "scheduled_matches": scheduled,
                "matches_with_info": has_info,
                "successful_scrapes": successful_scrapes,
                "failed_scrapes": failed_scrapes,
            }


# Global state DB instance
_state_db: Optional[StateDB] = None


def get_state_db() -> StateDB:
    global _state_db
    if _state_db is None:
        _state_db = StateDB()
    return _state_db


# JSON file storage (backward compatible)
def ensure_dirs(date_str: str = None) -> Path:
    """Ensure data directory exists for a given date."""
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d = DATA_ROOT / date_str
    d.mkdir(exist_ok=True, parents=True)
    return d


def save_json(
    data: Any,
    match_key: str,
    category: str,
    date_str: str = None,
    force: bool = False
) -> Path:
    """Save JSON data to file with state tracking."""
    if not JSON_FALLBACK and not force:
        # Just update state, don't write JSON
        get_state_db().upsert_match(match_key, **{f"{category}_saved": True})
        return None
    
    ensure_dirs(date_str)
    ts = datetime.now(timezone.utc)
    fname = f"{category}_{ts.strftime('%H%M%S')}.json"
    p = DATA_ROOT / (date_str or ts.strftime("%Y-%m-%d")) / match_key / fname
    
    p.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        
        # Record in state DB
        get_state_db().upsert_match(
            match_key,
            **{f"{category}_saved": True}
        )
        
        # Record scrape metric
        get_state_db().mark_scraped(
            match_key=match_key,
            scrape_type=category,
            success=True,
            records=len(data) if isinstance(data, (list, dict)) else None
        )
        
        logger.debug(f"Saved {category} for {match_key} -> {p}")
        return p
    except Exception as e:
        logger.error(f"Failed to save {category} for {match_key}: {e}")
        get_state_db().mark_scraped(
            match_key=match_key,
            scrape_type=category,
            success=False,
            error=str(e)
        )
        return None


def get_saved_files(match_key: str, date: str = None) -> List[Path]:
    """List all JSON files for a match."""
    d = DATA_ROOT / (date or datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    if not d.exists():
        return []
    base = d / match_key
    if not base.exists():
        return []
    return list(base.glob("*.json"))


# CSV exporter
def export_match_to_csv(match_key: str, date: str = None) -> List[Path]:
    """Export all match data to CSV files."""
    from .client import get_match_info, get_scorecard, get_live_score, get_fixtures
    
    files = []
    export_dir = Path(get_export_config().get("output_dir", "exports")) / match_key
    export_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Export info
        info = get_match_info(match_key)
        if info:
            f = export_dir / "info.csv"
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("key,value\n")
                for k, v in info.items():
                    if isinstance(v, (str, int, float)):
                        fh.write(f"{k},{v}\n")
            files.append(f)
        
        # Export scorecard (decoded)
        from .scorecard import decode_scorecard
        sc = get_scorecard(match_key)
        if sc:
            decoded = decode_scorecard(sc)
            for inning_idx, inning in enumerate(decoded.get("innings", [])):
                f = export_dir / f"inning_{inning_idx + 1}.csv"
                with open(f, "w", encoding="utf-8") as fh:
                    # Batting
                    fh.write("Type,Position,PlayerCode,PlayerName,Runs,Balls,Fours,Sixes,StrikeRate,Dismissal\n")
                    for batter in inning.get("batting", []):
                        fh.write(
                            f"batting,{batter.get('order','')},{batter.get('code','')},"
                            f"{batter.get('name','')},{batter.get('runs','')},{batter.get('balls','')},"
                            f"{batter.get('fours','')},{batter.get('sixes','')},{batter.get('strike_rate','')},"
                            f"{batter.get('out_text','')}\n"
                        )
                    fh.write("\n")
                    # Bowling
                    fh.write("Type,PlayerCode,PlayerName,Overs,Balls,Runs,Wickets,Economy\n")
                    for bowler in inning.get("bowling", []):
                        fh.write(
                            f"bowling,{bowler.get('code','')},{bowler.get('name','')},"
                            f"{bowler.get('overs','')},{bowler.get('balls','')},{bowler.get('runs','')},"
                            f"{bowler.get('wickets','')},{bowler.get('economy','')}\n"
                        )
                files.append(f)
        
        logger.info(f"Exported {len(files)} CSV files for {match_key} to {export_dir}")
    except Exception as e:
        logger.error(f"CSV export failed for {match_key}: {e}")
    
    return files
