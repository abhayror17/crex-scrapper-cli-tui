# CREX Cricket TUI

A beautiful, interactive terminal UI for exploring live cricket scores and match data, built on top of `crex_scraper`.

```
  🏏  CREX CRICKET EXPLORER  🏏
```

## Features

- **Live Match Browser** – See all current and upcoming matches with clear status badges (LIVE, FINISHED, UPCOMING).
- **Real-time Scores** – Watch batting, bowling, and extras update live.
- **Full Scorecard** – Complete batting and bowling tables with strikerates and economies.
- **Squads View** – Two-column display showing players per team with roles (Batsman/Bowler).
- **Match Info** – Venue, series, toss, and umpires.
- **Clean UI** – No clutter, smooth navigation via arrow keys, and fast rendering with Rich.
- **Demo Mode** – Works even without `crex_scraper` installed using built-in mock data.

## Screenshot

```
-----------------------------------------   Mumbai Indians  vs  Chennai Super Kings  🏏 SCORECARD ------------------------------------------

----------------------------------------------- Mumbai Indians 1st Innings  139/6  (17.3 ov) -----------------------------------------------
+---------------------------------------------------------------------------------------------------+
| BATTER                 | DISMISSAL                        |     R |     B |   4s |   6s |      SR |
|------------------------+----------------------------------+-------+-------+------+------+---------|
| Will Jacks             |                                  |     1 |     5 |      |      |    20.0 |
| Ryan Rickelton         |                                  |    37 |    24 |      |    5 |  154.17 |
| Naman Dhir             |                                  |    57 |    37 |    4 |    3 |  154.05 |
| Suryakumar Yadav       |                                  |    21 |    12 |    3 |    1 |   175.0 |
| Tilak Varma            |                                  |     5 |     8 |      |      |    62.5 |
| Hardik Pandya          |                                  |    10 |    15 |    1 |      |    66.67 |
| Robin Minz             |                                  |     5 |     3 |    1 |      |   166.67 |
+---------------------------------------------------------------------------------------------------+
  Extras: 3    Total: 139/6 in 17.3 overs

+------------------------------------------------------------------------------+
| BOWLER                 |     O |     M |     R |    W |   ECON |   NB |   WD |
|------------------------+-------+-------+-------+------+--------+------+------|
| Mukesh Choudhary       |   3.0 |       |    25 |      |   8.33 |      |      |
| Anshul Kamboj          |   2.2 |       |    17 |      |   7.29 |      |      |
| Prashant Veer          |   2.0 |       |    25 |      |   12.5 |      |      |
| Noor Ahmad             |   4.0 |       |    26 |      |    6.5 |      |      |
| Ramakrishna Ghosh      |   3.0 |       |    24 |      |    8.0 |      |      |
| Jamie Overton          |   3.0 |       |    19 |      |   6.33 |      |      |
+------------------------------------------------------------------------------+
```

## Installation

### Option 1: Standalone Bundle (Recommended)

The `tui_bundle/` folder is a self-contained distribution — just install dependencies and run:

**Windows:**
```bash
cd tui_bundle
pip install -r requirements.txt
python tui.py
# or double-click run_tui.bat
```

**macOS / Linux:**
```bash
cd tui_bundle
pip install -r requirements.txt
./run_tui.sh
# or python3 tui.py
```

No additional setup required — the bundle includes its own copy of `crex_scraper` and config files.

### Option 2: Development Mode

If you want to run the root-level `tui.py` against the main package:

```bash
# Clone & setup the main project
git clone https://github.com/abhayror17/crex-scrapper-cli-tui.git
cd crex-scraper
pip install -r requirements.txt

# Run TUI from project root
python tui.py
```

## Usage

Once inside the TUI, use arrow keys to navigate the match list. Press Enter to open a match menu:

- **Scorecard** – Full innings breakdown
- **Live Score** – Current run rate, partnership, recent balls
- **Match Info** – Venue, series, toss, umpires
- **Squads** – Playing XI with roles
- **Raw JSON** – See original API response
- **Save All to Disk** – One-off full scrape
- **Back** – Return to match list

Press `Ctrl+C` or select **Exit** to quit.

## How It Works

- Data comes from `crex_scraper` imports (`get_live_matches`, `get_scorecard`, etc.). If the package isn't installed, beautiful mock data is used instead.
- Team and player names are resolved dynamically by fetching squads for each match. This ensures correct names for any tournament.
- The SC4 scorecard format (used by the API) is decoded client-side into proper batting and bowling statistics.

## Integration with crex_scraper

This TUI is designed to work hand-in-hand with the `crex_scraper` library:

- Uses the same data fetching functions (`get_live_matches`, `get_fixtures`, `get_scorecard`, `get_live_score`, `get_match_info`, `get_squads_from_details`).
- Honors the `config.yaml` for headers and endpoints.
- Can run in demo mode if `crex_scraper` isn't installed; great for UI development and testing.

## Project Structure (TUI-related)

```
crex-scraper/
├── tui_bundle/          # ← Standalone TUI distribution (recommended)
│   ├── tui.py
│   ├── run_tui.bat / run_tui.sh
│   ├── requirements.txt
│   ├── config.yaml
│   ├── crex_scraper/    # embedded package
│   └── data/            # team/player maps
├── tui.py               # Development version (uses main package)
├── crex_scraper/        # core scraper library
│   ├── client.py
│   ├── scorecard.py
│   └── ...
├── data/                # JSON fallback storage (optional)
└── requirements.txt
```

## Troubleshooting

- **No matches appear** – Check your internet and the `crex_scraper` installation. If you're offline, mock data will load (demo mode).
- **Garbled text** – Ensure your terminal supports UTF-8 and has a sizeable width (min 100 cols).
- **Warnings scrolling** – The TUI suppresses noisy warnings from the scraper module; they're still logged to disk if needed.

## License

Same as the parent `crex_scraper` project – for assignment use, not commercial.

---

*Happy exploring!* 🏏