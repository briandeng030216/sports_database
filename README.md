# Sports Database

Sports Database is a collection of Python pipelines for building local MLB, NBA, and NFL datasets. The repository contains only data-retrieval and completeness-checking code. Generated datasets, prediction models, experiments, and virtual environments are intentionally excluded.

Each sport writes its output to a local `data/` directory inside the corresponding league folder. The update scripts are incremental: they use status tables and existing CSV files to avoid reprocessing work that has already completed.

## Available data

### MLB

The MLB pipeline uses the public MLB Stats API and `pybaseball` to produce:

| File | Row level | Main contents |
| --- | --- | --- |
| `teams.csv` | One row per MLB team | Team ID, abbreviation, name, and league |
| `games.csv` | One row per game | Date, game type, teams, final score, winner, and innings |
| `players.csv` | One row per player | MLB and FanGraphs IDs, name, birth date, position, and handedness |
| `batter_game_stats.csv` | One row per batter-game | Plate appearances, hits, extra-base hits, walks, strikeouts, stolen bases, and related box-score statistics |
| `pitcher_game_stats.csv` | One row per pitcher-game | Innings, batters faced, pitches, hits, runs, walks, strikeouts, home runs, and decisions |
| `team_game_stats.csv` | One row per team-game | Team batting, pitching, baserunning, fielding, and result statistics |
| `pitch_by_pitch.csv` | One row per pitch | Count, pitch type, velocity, spin, release measurements, location, movement, outcome, and batted-ball measurements |
| `game_update_status.csv` | One row per tracked game | Completion flags for every MLB pipeline stage and any recorded error |
| `data_completeness_report.csv` | One row per checked game | Missing-table and row-count checks produced by the completeness script |

The pitch-level table can become very large. Plan local disk space before collecting multiple seasons.

### NBA

The NBA pipeline uses `nba_api` to produce:

| File | Row level | Main contents |
| --- | --- | --- |
| `teams.csv` | One row per NBA team | Team ID, abbreviation, city, name, conference, and division |
| `games.csv` | One row per game | Season, date, teams, final score, winner, and overtime indicator |
| `players.csv` | One row per player | NBA ID, name, biographical details, position, size, country, and draft year |
| `play_by_play.csv` | One row per recorded action | Period and clock, possession, event description, involved players, score, shot information, fouls, turnovers, rebounds, and event flags |
| `player_game_stats.csv` | One row per player-game | Traditional box score plus shooting, usage, rating, pace, and possession metrics |
| `team_game_stats.csv` | One row per team-game | Traditional and advanced team statistics, ratings, pace, and possessions |
| `game_update_status.csv` | One row per tracked game | Completion flags for games, players, play-by-play, team statistics, and player statistics |

### NFL

The NFL pipeline uses `nflreadpy` data sources to produce:

| File | Row level | Main contents |
| --- | --- | --- |
| `teams.csv` | One row per NFL team | Team ID, abbreviation, name, conference, and division |
| `games.csv` | One row per game | Season, week, date, game type, teams, final score, winner, and tie indicator |
| `players.csv` | One row per player | GSIS ID, name, biographical details, position, college, size, and draft year |
| `play_by_play.csv` | One row per play | Game state, field position, down and distance, play type, description, passing, rushing, scoring, turnover, and other event fields |
| `team_game_stats.csv` | One row per team-game | Score, plays, yards, first downs, turnovers, passing, rushing, penalties, conversions, and possession time |
| `player_passing_stats.csv` | One row per passer-game | Attempts, completions, yards, touchdowns, interceptions, sacks, air yards, depth splits, and rating |
| `player_rushing_stats.csv` | One row per rusher-game | Attempts, yards, touchdowns, first downs, fumbles, longest rush, and distance splits |
| `player_receiving_stats.csv` | One row per receiver-game | Targets, receptions, yards, touchdowns, air yards, yards after catch, fumbles, and depth splits |
| `player_def_games.csv` | One row per defender-game | Snaps, tackles, sacks, coverage events, turnovers, returns, and special-teams statistics |
| `player_block_games.csv` | One row per blocker-game | Blocking snaps, pressures and sacks allowed, penalties, and special-teams blocking activity |
| `game_update_status.csv` | One row per tracked game | Completion flags for every NFL pipeline stage and any recorded error |

## Repository structure

```text
sports_database/
├── README.md
├── requirements.txt
├── MLB/
│   ├── check_data_completeness.py
│   ├── get_batter_game_stats.py
│   ├── get_games.py
│   ├── get_pitch_by_pitch.py
│   ├── get_pitcher_game_stats.py
│   ├── get_players.py
│   ├── get_team_game_stats.py
│   ├── get_teams.py
│   └── update_data.py
├── NBA/
│   └── update_data.py
└── NFL/
    ├── get_games.py
    └── update_data.py
```

## Installation

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The scripts make requests to external sports-data services. Internet access is required, and long date ranges may take considerable time. Respect the upstream services' usage policies and avoid sending unnecessarily frequent requests.

## Usage

Run each command from its league directory. Output directories and CSV files are created automatically when the pipeline starts.

### MLB

The main updater prompts for a start date, end date, and optional team filter, then fills every table for the selected completed games:

```bash
cd MLB
python get_teams.py
python update_data.py
```

The individual scripts can be used when only one table needs to be rebuilt or inspected:

```bash
python get_games.py --help
python get_players.py
python get_batter_game_stats.py
python get_pitcher_game_stats.py
python get_team_game_stats.py
python get_pitch_by_pitch.py
```

After an update, run the completeness checker:

```bash
python check_data_completeness.py
```

The checker compares the game list with the dependent tables and writes a local completeness report. Review the report and `game_update_status.csv` before using the data in downstream analysis.

### NBA

The main updater prompts for the season start year and a month range:

```bash
cd NBA
python update_data.py
```

To update only the game list and regular-season team statistics used by modeling workflows:

```bash
python update_data.py --model-data-only
```

To reconcile play-by-play status flags with game IDs already present in the local CSV:

```bash
python update_data.py --reconcile-play-by-play-status
```

### NFL

The main updater prompts for a season, week range, and optional team filter:

```bash
cd NFL
python update_data.py
```

To update or inspect only the game schedule, use:

```bash
python get_games.py --help
```

## Recommended workflow

1. Activate the virtual environment.
2. Change into the desired league directory.
3. Run the league's main `update_data.py` script and enter a limited date, month, or week range.
4. Let the script resume or skip completed stages using `game_update_status.csv`.
5. Review the terminal output and any recorded `error_message` values.
6. For MLB, run `check_data_completeness.py` after collection.
7. Keep generated data locally or in dedicated data storage rather than committing it to Git.

## Notes

- Game and player identifiers should be treated as strings when leading zeros are possible.
- A status flag confirms that a pipeline stage completed; it does not replace downstream validation of row counts, missing values, or source revisions.
- Re-running an update may change historical data when an upstream provider corrects its records.
- The pipelines are intended for research and personal analysis. Confirm licensing and redistribution requirements before publishing the collected data.
