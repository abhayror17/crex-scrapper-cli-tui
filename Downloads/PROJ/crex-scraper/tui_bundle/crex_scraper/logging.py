"""Structured JSON logging with SQLite persistence."""

import json
import sys
import time
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from traceback import format_exception

try:
    from loguru import logger as lg
    HAS_LOGURU = True
except ImportError:
    HAS_LOGURU = False
    lg = None

from .config import get_logging_config, get_storage_config

# Use standard logging as base
std_logger = logging.getLogger("crex")
std_logger.setLevel(logging.INFO)
if not std_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    std_logger.addHandler(handler)


def get_logger(name: str) -> Any:
    """Get a logger instance (loguru if available, else standard)."""
    if HAS_LOGURU:
        return lg.bind(name=name)
    else:
        # Return a standard logger adapter
        return logging.getLogger(name)


# SQLite logger for structured logs
class SQLiteLogger:
    """Persist logs to SQLite for querying."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or get_storage_config().get("db_path", "scraper_state.db")
        self._init_db()
    
    def _init_db(self):
        """Create logs table if not exists."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS structured_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    extra TEXT,
                    file TEXT,
                    line INTEGER
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SQLiteLogger] DB init error: {e}", file=sys.stderr)
    
    def log(
        self,
        level: str,
        name: str,
        message: str,
        extra: Optional[Dict] = None,
        file: str = "",
        line: int = 0
    ):
        """Write log entry to SQLite."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            c = conn.cursor()
            c.execute('''
                INSERT INTO structured_logs 
                (timestamp, level, name, message, extra, file, line)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                level.upper(),
                name,
                message[:5000],
                json.dumps(extra or {}, ensure_ascii=False) if extra else None,
                file,
                line
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SQLiteLogError] {e}", file=sys.stderr)


_sqlite_logger: Optional[SQLiteLogger] = None


def get_sqlite_logger() -> SQLiteLogger:
    global _sqlite_logger
    if _sqlite_logger is None:
        try:
            _sqlite_logger = SQLiteLogger()
        except Exception as e:
            print(f"[SQLiteLogger] Failed to initialize: {e}", file=sys.stderr)
            # Return a dummy logger
            _sqlite_logger = None
    return _sqlite_logger


def log_event(
    level: str,
    message: str,
    name: str = "crex",
    extra: Optional[Dict] = None,
    file: str = "",
    line: int = 0
):
    """Log event to all handlers."""
    # Use loguru if available, else standard
    if HAS_LOGURU:
        log = getattr(lg, level.lower(), lg.info)
        log(message, name=name, extra=extra or {})
    else:
        std_logger.log(getattr(logging, level.upper(), logging.INFO), message)
    
    # Also SQLite
    try:
        sql_logger = get_sqlite_logger()
        if sql_logger:
            sql_logger.log(level, name, message, extra, file, line)
    except Exception:
        pass

