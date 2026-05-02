# CREX Cricket TUI – Standalone Bundle

Self-contained terminal UI for exploring cricket match data. No installation required beyond Python dependencies.

## What's Inside

```
tui_bundle/
├── tui.py           - Main TUI script
├── run_tui.bat      - Windows launcher
├── run_tui.sh       - macOS / Linux launcher
├── requirements.txt - Python dependencies
├── config.yaml      - Scraper configuration (endpoints, headers)
├── crex_scraper/    - Local Python package (data fetching, parsing)
└── data/            - Team/player name maps
    ├── team_map.json
    └── player_map.json
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

Required packages: `rich`, `questionary`, `aiohttp`, `PyYAML`, `loguru`, `orjson`, etc.

### 2. Run the TUI

**Windows:** double-click `run_tui.bat` or run from terminal:
```cmd
python tui.py
```

**macOS / Linux:**
```bash
./run_tui.sh
# or
python3 tui.py
```

## How It Works

`tui.py` adds the current script's directory to `sys.path` so it can import the local `crex_scraper` package without installation. All data files are resolved relative to the script location, so you can run the script from any working directory.

The TUI fetches live matches and fixtures from `crex.live` via `crex_scraper` and displays:
- **Scorecard** — full batting/bowling figures, fall of wickets
- **Squads** — playing XI with roles
- **Raw JSON** — inspect raw API responses
- **Save All** — scrape and persist full match archive

Live matches appear at the top of the list.