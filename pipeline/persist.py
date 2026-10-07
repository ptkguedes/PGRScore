"""Write processed JSON and a local SQLite simulation of the serving layer."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS teams (
    abbr TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    conf TEXT,
    div TEXT,
    record TEXT,
    win_pct REAL,
    rank INTEGER,
    roster_count INTEGER
);

CREATE TABLE IF NOT EXISTS players (
    nfl_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    team_abbr TEXT,
    position TEXT,
    pos_group TEXT,
    jersey INTEGER,
    snaps INTEGER,
    pgr_score INTEGER,
    top_speed_mph REAL,
    burst_yd_s2 REAL,
    dist_per_snap REAL,
    pressures REAL,
    sacks_allowed REAL,
    z_composite REAL,
    FOREIGN KEY (team_abbr) REFERENCES teams(abbr)
);

CREATE TABLE IF NOT EXISTS player_games (
    nfl_id INTEGER,
    week INTEGER,
    opp TEXT,
    side TEXT,
    snaps INTEGER,
    top_speed_mph REAL,
    dist_per_snap REAL,
    PRIMARY KEY (nfl_id, week, opp, side),
    FOREIGN KEY (nfl_id) REFERENCES players(nfl_id)
);

CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_abbr, pos_group, pgr_score);
"""


def write_processed_json(document: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path


def write_sqlite(scored: pd.DataFrame, document: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        team_rows = [
            (
                t["abbr"],
                t["name"],
                t["conf"],
                t["div"],
                t["record"],
                t["winPct"],
                t["rank"],
                t["rosterCount"],
            )
            for t in document["teams"].values()
        ]
        conn.executemany(
            "INSERT INTO teams VALUES (?,?,?,?,?,?,?,?)",
            team_rows,
        )
        player_rows = []
        game_rows = []
        for _, row in scored.iterrows():
            jersey = None if pd.isna(row["jersey"]) else int(row["jersey"])
            player_rows.append(
                (
                    int(row["nflId"]),
                    row["displayName"],
                    row["teamAbbr"],
                    row["officialPosition"],
                    row["group"],
                    jersey,
                    int(row["snaps"]),
                    int(row["pgrScore"]),
                    float(row["topSpeedMph"]),
                    float(row["burstYdS2"]),
                    float(row["distPerSnap"]),
                    float(row["pressures"]),
                    float(row["sacksAllowed"]),
                    float(row["z_composite"]),
                )
            )
            for pg in row["perGame"] or []:
                game_rows.append(
                    (
                        int(row["nflId"]),
                        int(pg["week"]),
                        pg.get("opp"),
                        pg.get("side"),
                        int(pg.get("snaps") or 0),
                        float(pg.get("topSpeedMph") or 0.0),
                        float(pg.get("distPerSnap") or 0.0),
                    )
                )
        conn.executemany(
            "INSERT INTO players VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            player_rows,
        )
        conn.executemany(
            "INSERT INTO player_games VALUES (?,?,?,?,?,?,?)",
            game_rows,
        )
        conn.commit()
    finally:
        conn.close()
    return path
