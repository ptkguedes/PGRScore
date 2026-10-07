"""Load raw NFL sources (CSV + tracking overlay). Vectorized pandas joins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .positions import OFFENSE_PFF_ROLES, group_for

NA_VALUES = ["NA", "na", ""]


def height_to_inches(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    if not text or text.upper() == "NA":
        return None
    if "-" in text:
        feet, inches = text.split("-", 1)
        return int(feet) * 12 + int(inches)
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def load_games(raw_dir: Path) -> pd.DataFrame:
    games = pd.read_csv(raw_dir / "games.csv")
    games["gameId"] = games["gameId"].astype(np.int64)
    games["week"] = games["week"].astype(int)
    games["season"] = games["season"].astype(int)
    return games


def load_players(raw_dir: Path) -> pd.DataFrame:
    players = pd.read_csv(raw_dir / "players.csv", na_values=NA_VALUES)
    players["nflId"] = players["nflId"].astype(np.int64)
    players["group"] = players["officialPosition"].map(group_for)
    players["heightIn"] = players["height"].map(height_to_inches)
    players["college"] = players["collegeName"].fillna("NA")
    return players


def load_pff(raw_dir: Path) -> pd.DataFrame:
    usecols = [
        "gameId",
        "playId",
        "nflId",
        "pff_role",
        "pff_hit",
        "pff_hurry",
        "pff_sack",
        "pff_sackAllowed",
    ]
    pff = pd.read_csv(raw_dir / "pffScoutingData.csv", usecols=usecols, na_values=NA_VALUES)
    pff["gameId"] = pff["gameId"].astype(np.int64)
    pff["playId"] = pff["playId"].astype(np.int64)
    pff["nflId"] = pff["nflId"].astype(np.int64)
    for col in ("pff_hit", "pff_hurry", "pff_sack", "pff_sackAllowed"):
        pff[col] = pd.to_numeric(pff[col], errors="coerce").fillna(0.0)
    # Original dashboard: pressures = PFF hit + hurry (sacks counted separately).
    pff["pressure"] = pff["pff_hit"] + pff["pff_hurry"]
    return pff


def load_plays(raw_dir: Path) -> pd.DataFrame:
    plays = pd.read_csv(
        raw_dir / "plays.csv",
        usecols=["gameId", "playId", "possessionTeam", "defensiveTeam"],
        na_values=NA_VALUES,
    )
    plays["gameId"] = plays["gameId"].astype(np.int64)
    plays["playId"] = plays["playId"].astype(np.int64)
    return plays


def load_tracking(raw_dir: Path) -> pd.DataFrame:
    """Tracking overlay: peak speed/accel and per-game series.

    Full Next Gen Stats week files (~810 MB) are not in this repo. The overlay
    is extracted from the hackathon ``data.json`` (same metrics the JS used).
    """
    path = raw_dir / "tracking_metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["players"] if isinstance(payload, dict) else payload
    frame = pd.DataFrame(rows)
    frame["nflId"] = frame["nflId"].astype(np.int64)
    return frame


def load_team_ref(ref_path: Path) -> list[dict[str, Any]]:
    return json.loads(ref_path.read_text(encoding="utf-8"))


def assign_snap_teams(pff: pd.DataFrame, plays: pd.DataFrame) -> pd.DataFrame:
    """Attach the team that lined up each PFF snap (offense vs defense role)."""
    snaps = pff.merge(plays, on=["gameId", "playId"], how="inner")
    offense = snaps["pff_role"].isin(OFFENSE_PFF_ROLES)
    snaps["team"] = np.where(offense, snaps["possessionTeam"], snaps["defensiveTeam"])
    return snaps


def aggregate_pff(snaps: pd.DataFrame) -> pd.DataFrame:
    """Snaps, pressures, sacks allowed, primary roster team."""
    player_totals = (
        snaps.groupby("nflId", as_index=False)
        .agg(
            snaps=("playId", "size"),
            pressures=("pressure", "sum"),
            sacksAllowed=("pff_sackAllowed", "sum"),
        )
    )
    team_counts = snaps.groupby(["nflId", "team"], as_index=False).size()
    primary = (
        team_counts.sort_values(["nflId", "size"], ascending=[True, False])
        .drop_duplicates("nflId")
        .rename(columns={"team": "teamAbbr"})[["nflId", "teamAbbr"]]
    )
    return player_totals.merge(primary, on="nflId", how="left")
