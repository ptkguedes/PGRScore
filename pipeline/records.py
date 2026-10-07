"""Week 1–8 W-L-T from scheduled games joined to official final scores.

``games.csv`` has matchups only (no scores). Results live in
``data/raw/game_results.csv`` (ESPN public scoreboard, 2021 regular season
weeks 1–8), keyed by the same gameId / home / visitor as ``games.csv``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

ESPN_TO_REPO = {"LAR": "LA", "WSH": "WAS"}


def format_record(wins: int, losses: int, ties: int) -> str:
    if ties:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def load_game_results(raw_dir) -> pd.DataFrame:
    path = raw_dir / "game_results.csv"
    if not path.exists():
        raise FileNotFoundError(
            "Missing data/raw/game_results.csv (home/visitor scores for weeks 1–8). "
            "games.csv has no outcomes. Run scripts/fetch_game_results.py."
        )
    results = pd.read_csv(path)
    results["gameId"] = results["gameId"].astype(np.int64)
    return results


def attach_scores(games: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    scored = games.merge(
        results[["gameId", "homeScore", "visitorScore"]],
        on="gameId",
        how="left",
        validate="one_to_one",
    )
    missing = scored[scored["homeScore"].isna()]
    if len(missing):
        raise ValueError(
            f"{len(missing)} scheduled games have no final score in game_results.csv"
        )
    scored["homeScore"] = scored["homeScore"].astype(int)
    scored["visitorScore"] = scored["visitorScore"].astype(int)
    return scored


def compute_team_records(scored_games: pd.DataFrame) -> pd.DataFrame:
    """One row per team: wins, losses, ties, points, winPct, rank (1=best)."""
    frames = []
    for side, team_col, own, opp in (
        ("home", "homeTeamAbbr", "homeScore", "visitorScore"),
        ("away", "visitorTeamAbbr", "visitorScore", "homeScore"),
    ):
        chunk = scored_games[[team_col, own, opp, "week"]].rename(
            columns={team_col: "abbr", own: "pf", opp: "pa"}
        )
        chunk["side"] = side
        frames.append(chunk)
    long = pd.concat(frames, ignore_index=True)
    long["win"] = (long["pf"] > long["pa"]).astype(int)
    long["loss"] = (long["pf"] < long["pa"]).astype(int)
    long["tie"] = (long["pf"] == long["pa"]).astype(int)
    agg = long.groupby("abbr", as_index=False).agg(
        wins=("win", "sum"),
        losses=("loss", "sum"),
        ties=("tie", "sum"),
        pointsFor=("pf", "sum"),
        pointsAgainst=("pa", "sum"),
        games=("week", "size"),
    )
    gp = (agg["wins"] + agg["losses"] + agg["ties"]).replace(0, np.nan)
    agg["winPct"] = ((agg["wins"] + 0.5 * agg["ties"]) / gp).round(3)
    agg["pointDiff"] = agg["pointsFor"] - agg["pointsAgainst"]
    agg["record"] = [
        format_record(int(w), int(l), int(t))
        for w, l, t in zip(agg["wins"], agg["losses"], agg["ties"])
    ]
    agg = agg.sort_values(
        ["winPct", "wins", "pointDiff", "pointsFor", "abbr"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)
    agg["rank"] = np.arange(1, len(agg) + 1)
    return agg


def records_by_abbr(scored_games: pd.DataFrame) -> dict[str, dict[str, Any]]:
    table = compute_team_records(scored_games)
    return {row["abbr"]: row.to_dict() for _, row in table.iterrows()}
