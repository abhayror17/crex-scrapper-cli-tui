# CREX Live - On-Demand Cricket Scraper

## Quick Start

```bash
# From the project root directory
python webapp.py
```

Open browser: **http://localhost:5000**

---

## How It Works

### Simplified On-Demand Model
- **No background agents**
- **No job queues**
- **No auto-scraping**

**User clicks → Scrape happens → Data displayed**

---

## Features

### 1. Live Scores Tab
- Shows all currently live matches
- Team names resolved from `team_map.json`
- Scores updated on refresh (auto-refresh every 30s)

### 2. Upcoming Tab
- List of upcoming matches (status = 0)
- Shows teams, date, time, format
- Click any match → modal with basic info + **Scrape All Data** button

### 3. Completed Tab
- Finished matches (status = 2)
- Result shown
- Can scrape to get full scorecard

### 4. Match Detail Modal
- Shows basic match info immediately (from cached live/fixtures data)
- **Scrape All Data** button → fetches:
  - Match Info (IV4)
  - Squads (from HTML)
  - Live Score (SV3)
  - Scorecard (SC4)
- Tabbed view to see each data type as pretty-printed JSON
- All scraped data auto-saved to `data/YYYY-MM-DD/<match_key>/`

---

## Data Storage

### JSON Files
```
data/
  ├─ 2026-05-01/
  │   ├─ 10XU/
  │   │   ├─ info_120003.json
  │   │   ├─ squads_200519.json
  │   │   ├─ scorecard_210222.json
  │   │   └─ live_210225.json
  │   └─ 11LY/
  │       └─ ...
```

### Name Maps (auto-generated)
- `data/team_map.json` - team code → full name (35+ entries)
- `data/player_map.json` - player code → full name (230+ entries)

These are built from your existing scraped squads files. Re-run `analyze_data.py` after new scrapes to rebuild.

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/live` | GET | Live matches with team names resolved |
| `/api/fixtures?page=0` | GET | Upcoming/completed fixtures |
| `/api/teams` | GET | Team code → name mapping |
| `/api/players` | GET | Player code → name mapping |
| `/api/match/<key>/scrape` | POST | Scrape all data for a match (on-demand) |
| `/api/match/<key>/info` | GET | Match info only |
| `/api/match/<key>/squads` | GET | Squads only |
| `/api/match/<key>/scorecard` | GET | Scorecard only |
| `/api/match/<key>/live` | GET | Live score only |
| `/api/logs` | GET | System logs |
| `/api/data/` | GET | Browse saved JSON files |
| `/data/<path>` | GET | Serve JSON file |

---

## Technical Details

### Dependencies
- Flask 2.3.3
- Flask-Cors 4.0.0
- crex_scraper package (uses curl.exe)

### Configuration
All endpoints and headers are in `crex_scraper/client.py` (from original cURL).

### Team Name Resolution
1. Load from `data/team_map.json` (generated)
2. Fallback to hardcoded common codes (W, R, E, P, I, AUS, IND, PAK, RSA, ENG, NZ)
3. If still unknown → returns the code itself

### Player Name Resolution
1. Load from `data/player_map.json` (generated from squads)
2. If unknown → returns the code

---

## Scripts

### `analyze_data.py`
Generates `team_map.json` and `player_map.json` from existing scraped data.
Run after you've scraped some matches to build the name maps.

```bash
python analyze_data.py
```

---

## Known Issues

- Team/player codes that haven't been scraped yet will show as codes (e.g., "VU").
- To fix: click any match that includes those teams/players and click "Scrape All Data". The names will be saved to the JSON files, then re-run `analyze_data.py` to rebuild the maps.

---

## License
Private - CREX Scraper Take-Home Assignment
