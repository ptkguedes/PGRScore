"""Join sources, score players, emit the dashboard JSON document."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .pgr_score_calculator import attach_z_and_scores, build_props
from .positions import GROUP_LABELS, POSITION_GROUPS


def parse_record(record: str) -> tuple[int, int, int]:
    wins = losses = ties = 0
    parts = (record or "0-0").split("-")
    if len(parts) >= 2:
        wins, losses = int(parts[0]), int(parts[1])
    if len(parts) == 3:
        ties = int(parts[2])
    return wins, losses, ties


def build_player_table(
    players: pd.DataFrame,
    pff_agg: pd.DataFrame,
    tracking: pd.DataFrame,
) -> pd.DataFrame:
    frame = players.merge(pff_agg, on="nflId", how="inner")
    track_cols = ["nflId", "jersey", "topSpeedMph", "burstYdS2", "distPerSnap", "perGame"]
    frame = frame.merge(tracking[track_cols], on="nflId", how="left")
    frame["snaps"] = frame["snaps"].fillna(0).astype(int)
    frame["pressures"] = frame["pressures"].fillna(0.0)
    frame["sacksAllowed"] = frame["sacksAllowed"].fillna(0.0)
    frame["topSpeedMph"] = frame["topSpeedMph"].fillna(0.0)
    frame["burstYdS2"] = frame["burstYdS2"].fillna(0.0)
    frame["distPerSnap"] = frame["distPerSnap"].fillna(0.0)
    frame["hasTracking"] = frame["perGame"].notna()
    frame["perGame"] = frame["perGame"].apply(lambda x: x if isinstance(x, list) else [])
    frame = frame[frame["group"].notna() & frame["teamAbbr"].notna()].copy()
    return attach_z_and_scores(frame)


def team_home_away_split(roster: pd.DataFrame, games: pd.DataFrame, abbr: str) -> dict[str, Any]:
    home_games = int((games["homeTeamAbbr"] == abbr).sum())
    away_games = int((games["visitorTeamAbbr"] == abbr).sum())
    home = {"snaps": 0, "dist": 0.0, "top": 0.0}
    away = {"snaps": 0, "dist": 0.0, "top": 0.0}
    for per_game in roster["perGame"]:
        if not isinstance(per_game, list):
            continue
        for row in per_game:
            bucket = home if row.get("side") == "home" else away
            snaps = int(row.get("snaps") or 0)
            dist = float(row.get("distPerSnap") or 0.0)
            spd = float(row.get("topSpeedMph") or 0.0)
            bucket["snaps"] += snaps
            bucket["dist"] += dist * snaps
            bucket["top"] = max(bucket["top"], spd)

    def pack(bucket: dict[str, Any], n_games: int) -> dict[str, Any]:
        avg = round(bucket["dist"] / bucket["snaps"], 1) if bucket["snaps"] else 0.0
        return {
            "games": n_games,
            "avgDistPerSnap": avg,
            "topSpeedMph": round(bucket["top"], 1),
            "snaps": int(bucket["snaps"]),
        }

    return {"home": pack(home, home_games), "away": pack(away, away_games)}


def player_payload(row: pd.Series) -> dict[str, Any]:
    jersey = row["jersey"]
    if pd.isna(jersey):
        jersey_out = None
    else:
        jersey_out = int(jersey)
    weight = row["weight"]
    return {
        "nflId": str(int(row["nflId"])),
        "name": row["displayName"],
        "position": row["officialPosition"],
        "group": row["group"],
        "jersey": jersey_out,
        "heightIn": None if pd.isna(row["heightIn"]) else int(row["heightIn"]),
        "weight": None if pd.isna(weight) else float(weight),
        "college": row["college"] if pd.notna(row["college"]) else "NA",
        "snaps": int(row["snaps"]),
        "pgrScore": int(row["pgrScore"]),
        "topSpeedMph": round(float(row["topSpeedMph"]), 1),
        "hasTracking": bool(row["hasTracking"]),
        "props": build_props(row),
        "perGame": row["perGame"] if isinstance(row["perGame"], list) else [],
    }


def assemble_document(
    scored: pd.DataFrame,
    games: pd.DataFrame,
    team_ref: list[dict[str, Any]],
) -> dict[str, Any]:
    week_min = int(games["week"].min())
    week_max = int(games["week"].max())
    teams_out: dict[str, Any] = {}
    standings: list[dict[str, Any]] = []

    for meta in sorted(team_ref, key=lambda t: t["rank"]):
        abbr = meta["abbr"]
        roster = scored[scored["teamAbbr"] == abbr]
        groups: dict[str, list[dict[str, Any]]] = {g: [] for g in POSITION_GROUPS}
        for _, row in roster.sort_values(["pgrScore", "snaps"], ascending=[False, False]).iterrows():
            groups[row["group"]].append(player_payload(row))
        wins, losses, ties = parse_record(meta["record"])
        gp = wins + losses + ties
        win_pct = meta.get("winPct")
        if win_pct is None:
            win_pct = round((wins + 0.5 * ties) / gp, 3) if gp else 0.0
        teams_out[abbr] = {
            "abbr": abbr,
            "name": meta["name"],
            "conf": meta["conf"],
            "div": meta["div"],
            "record": meta["record"],
            "winPct": win_pct,
            "rank": meta["rank"],
            "colors": meta["colors"],
            "logo": f"logos/{abbr}.png",
            "rosterCount": int(len(roster)),
            "groups": groups,
            "splitHomeAway": team_home_away_split(roster, games, abbr),
        }
        standings.append(
            {
                "rank": meta["rank"],
                "abbr": abbr,
                "name": meta["name"],
                "record": meta["record"],
                "conf": meta["conf"],
                "div": meta["div"],
            }
        )

    n_players = int(scored["nflId"].nunique())
    return {
        "meta": {
            "source": "NFL Big Data Bowl 2022 (temporada 2021)",
            "gamesProcessed": int(len(games)),
            "playersRegistered": n_players,
            "playersInRosters": n_players,
            "weekMin": week_min,
            "weekMax": week_max,
            "coverage": f"Semanas {week_min}–{week_max} da temporada 2021 · {len(games)} jogos",
            "note": "PGRScore (40–99) calculado em Python por grupo de posição. Props e tracking derivados do dataset original.",
            "positionGroups": list(POSITION_GROUPS),
            "groupLabels": dict(GROUP_LABELS),
        },
        "standings": standings,
        "teams": teams_out,
    }
