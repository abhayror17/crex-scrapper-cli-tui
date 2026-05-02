"""
Configuration loader for CREX Scraper.
Loads config.yaml and provides typed access to all settings.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config(path: Path = None) -> Dict[str, Any]:
    """Load configuration from YAML file with caching."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    
    p = path or _CONFIG_PATH
    if not p.exists():
        return _default_config()
    
    raw = p.read_text(encoding="utf-8")
    
    if HAS_YAML:
        _CONFIG_CACHE = yaml.safe_load(raw)
    else:
        _CONFIG_CACHE = _parse_yaml_fallback(raw)
    
    return _CONFIG_CACHE or _default_config()


def reload_config():
    """Force reload config from disk."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
    return load_config()


def get_endpoint(name: str) -> str:
    """Get a full endpoint URL."""
    cfg = load_config()
    ep = cfg.get("endpoints", {})
    base = ep.get("base_url", "")
    path = ep.get(name, "")
    return f"{base.rstrip('/')}{path}"


def get_header(key: str) -> str:
    """Get a specific header value."""
    cfg = load_config()
    return cfg.get("headers", {}).get(key, "")


def get_headers_dict() -> Dict[str, str]:
    """Get all headers as a dict."""
    return dict(load_config().get("headers", {}))


def get_polling() -> Dict[str, int]:
    return load_config().get("polling", {})


def get_concurrency() -> Dict[str, Any]:
    return load_config().get("concurrency", {})


def get_http_config() -> Dict[str, Any]:
    return load_config().get("http", {})


def get_storage_config() -> Dict[str, str]:
    return load_config().get("storage", {})


def get_cache_config() -> Dict[str, Any]:
    return load_config().get("cache", {})


def get_logging_config() -> Dict[str, Any]:
    return load_config().get("logging", {})


def get_export_config() -> Dict[str, Any]:
    return load_config().get("export", {})


def get_server_config() -> Dict[str, Any]:
    return load_config().get("server", {})


def _default_config() -> Dict[str, Any]:
    """Fallback default config when no file exists."""
    return {
        "endpoints": {
            "base_url": "https://api.goscorer.com/api/v3",
            "fixtures_url": "https://stats.crickapi.com/fixture/getFixture",
            "live_matches": "/getLiveMatches",
            "match_info": "/getIV4",
            "live_score": "/getSV3",
            "scorecard": "/getSC4",
        },
        "polling": {
            "fixtures_interval": 60,
            "live_score_interval": 10,
            "match_start_buffer": 300,
        },
        "concurrency": {
            "max_concurrent_matches": 5,
            "request_timeout": 30,
            "max_retries": 3,
            "retry_backoff_base": 2,
            "retry_jitter": True,
        },
        "http": {
            "connection_pool_size": 20,
            "keepalive_timeout": 30,
        },
        "storage": {
            "engine": "sqlite",
            "db_path": "crex_data.db",
            "json_fallback": True,
            "data_root": "data",
        },
        "logging": {
            "level": "INFO",
            "format": "json",
        },
    }


def _parse_yaml_fallback(raw: str) -> Dict[str, Any]:
    """Minimal YAML parser for when PyYAML is not available."""
    config = {}
    section = None
    for line in raw.split("\n"):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line[0] != " " and line.endswith(":"):
            section = line.rstrip(": ").strip()
            config[section] = {}
            continue
        if section and ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.isdigit():
                val = int(val)
            elif val.replace(".", "").isdigit():
                val = float(val)
            config[section][key] = val
    return config