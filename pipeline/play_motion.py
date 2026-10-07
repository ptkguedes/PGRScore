"""NGS tracking: play catalog (all games) + frame sequences for playback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

NA_VALUES = ["NA", "na", ""]
TRACK_COLS = [
    "gameId",
    "playId",
    "nflId",
    "frameId",
    "jerseyNumber",
    "team",
    "playDirection",
    "x",
    "y",
    "s",
    "event",
]


def _round(val: float, n: int = 2) -> float:
    return float(round(float(val), n))


def _pressure_table(pff: pd.DataFrame) -> pd.DataFrame:
    return (
        pff.assign(
            hit=lambda d: pd.to_numeric(d["pff_hit"], errors="coerce").fillna(0),
            hurry=lambda d: pd.to_numeric(d["pff_hurry"], errors="coerce").fillna(0),
            sack=lambda d: pd.to_numeric(d["pff_sack"], errors="coerce").fillna(0),
        )
        .groupby(["gameId", "playId"], as_index=False)
        .agg(hits=("hit", "sum"), hurries=("hurry", "sum"), sacks=("sack", "sum"))
    )


def pack_frame(fr: pd.DataFrame) -> dict[str, Any]:
    ball = fr.loc[fr["team"] == "football"]
    players = fr.loc[fr["team"] != "football"]
    plist = []
    for row in players.itertuples(index=False):
        if pd.isna(row.x) or pd.isna(row.y):
            continue
        jersey = None if pd.isna(row.jerseyNumber) else int(row.jerseyNumber)
        nfl_id = None if pd.isna(row.nflId) else int(row.nflId)
        plist.append(
            {
                "id": nfl_id,
                "t": str(row.team),
                "j": jersey,
                "x": _round(row.x),
                "y": _round(row.y),
                "s": _round(row.s, 2) if pd.notna(row.s) else 0.0,
            }
        )
    ball_xy = None
    if len(ball) and pd.notna(ball.iloc[0]["x"]):
        ball_xy = [_round(ball.iloc[0]["x"]), _round(ball.iloc[0]["y"])]
    return {"f": int(fr["frameId"].iloc[0]), "b": ball_xy, "p": plist}


def pack_snap(fr: pd.DataFrame) -> dict[str, Any]:
    packed = pack_frame(fr)
    return {
        "b": packed["b"],
        "p": [[pl["t"], pl["j"], pl["x"], pl["y"]] for pl in packed["p"]],
    }


def frames_for_play(track: pd.DataFrame, play_id: int) -> list[dict[str, Any]]:
    chunk = track.loc[track["playId"] == play_id].sort_values(["frameId", "nflId"])
    return [pack_frame(fr) for _, fr in chunk.groupby("frameId")]


def extract_play_document(
    track: pd.DataFrame,
    plays: pd.DataFrame,
    pff: pd.DataFrame,
    games: pd.DataFrame,
    play_id: int,
) -> dict[str, Any]:
    game_id = int(track["gameId"].iloc[0])
    chunk = track.loc[track["playId"] == play_id]
    if chunk.empty:
        raise KeyError(play_id)
    meta_row = plays.loc[(plays["gameId"] == game_id) & (plays["playId"] == play_id)]
    if meta_row.empty:
        raise KeyError((game_id, play_id))
    meta = meta_row.iloc[0]
    game = games.loc[games["gameId"] == game_id].iloc[0]
    press = _pressure_table(pff.loc[(pff["gameId"] == game_id) & (pff["playId"] == play_id)])
    pressure = {
        "hits": int(press["hits"].iloc[0]) if len(press) else 0,
        "hurries": int(press["hurries"].iloc[0]) if len(press) else 0,
        "sacks": int(press["sacks"].iloc[0]) if len(press) else 0,
    }
    snap_frames = chunk.loc[chunk["event"] == "ball_snap", "frameId"]
    rel_frames = chunk.loc[chunk["event"] == "pass_forward", "frameId"]
    snap_f = int(snap_frames.min()) if len(snap_frames) else int(chunk["frameId"].min())
    rel_f = int(rel_frames.min()) if len(rel_frames) else None
    return {
        "gameId": game_id,
        "playId": int(play_id),
        "week": int(game["week"]),
        "home": str(game["homeTeamAbbr"]),
        "away": str(game["visitorTeamAbbr"]),
        "desc": str(meta["playDescription"]),
        "down": int(meta["down"]) if pd.notna(meta["down"]) else None,
        "ytg": int(meta["yardsToGo"]) if pd.notna(meta["yardsToGo"]) else None,
        "playResult": int(meta["playResult"]) if pd.notna(meta["playResult"]) else None,
        "passResult": None if pd.isna(meta["passResult"]) else str(meta["passResult"]),
        "possessionTeam": str(meta["possessionTeam"]),
        "defensiveTeam": str(meta["defensiveTeam"]),
        "playDirection": str(chunk["playDirection"].iloc[0]),
        "snapFrame": snap_f,
        "releaseFrame": rel_f,
        "pressure": pressure,
        "frames": frames_for_play(track, play_id),
    }


def catalog_from_tracking_file(
    tracking_path: Path,
    plays: pd.DataFrame,
    press: pd.DataFrame,
    games: pd.DataFrame,
) -> list[dict[str, Any]]:
    track = pd.read_csv(tracking_path, usecols=TRACK_COLS, na_values=NA_VALUES)
    if track.empty:
        return []
    game_id = int(track["gameId"].iloc[0])
    game_rows = games.loc[games["gameId"] == game_id]
    if game_rows.empty:
        return []
    game = game_rows.iloc[0]
    gplays = plays.loc[plays["gameId"] == game_id]
    out: list[dict[str, Any]] = []
    for pid, chunk in track.groupby("playId"):
        ev = chunk["event"].dropna().astype(str)
        if "ball_snap" not in set(ev):
            continue
        meta_row = gplays.loc[gplays["playId"] == pid]
        if meta_row.empty:
            continue
        meta = meta_row.iloc[0]
        pr = press.loc[(press["gameId"] == game_id) & (press["playId"] == pid)]
        snap_f = int(chunk.loc[chunk["event"] == "ball_snap", "frameId"].min())
        rel = chunk.loc[chunk["event"] == "pass_forward", "frameId"]
        rel_f = int(rel.min()) if len(rel) else None
        snap_rows = chunk.loc[chunk["frameId"] == snap_f]
        item = {
            "gameId": game_id,
            "playId": int(pid),
            "week": int(game["week"]),
            "home": str(game["homeTeamAbbr"]),
            "away": str(game["visitorTeamAbbr"]),
            "desc": str(meta["playDescription"]),
            "down": int(meta["down"]) if pd.notna(meta["down"]) else None,
            "ytg": int(meta["yardsToGo"]) if pd.notna(meta["yardsToGo"]) else None,
            "playResult": int(meta["playResult"]) if pd.notna(meta["playResult"]) else None,
            "passResult": None if pd.isna(meta["passResult"]) else str(meta["passResult"]),
            "possessionTeam": str(meta["possessionTeam"]),
            "defensiveTeam": str(meta["defensiveTeam"]),
            "playDirection": str(chunk["playDirection"].iloc[0]),
            "snapFrame": snap_f,
            "releaseFrame": rel_f,
            "pressure": {
                "hits": int(pr["hits"].iloc[0]) if len(pr) else 0,
                "hurries": int(pr["hurries"].iloc[0]) if len(pr) else 0,
                "sacks": int(pr["sacks"].iloc[0]) if len(pr) else 0,
            },
            "nFrames": int(chunk["frameId"].nunique()),
            "snap": pack_snap(snap_rows),
        }
        out.append(item)
    return out


def build_catalog(tracking_dir: Path, plays: pd.DataFrame, pff: pd.DataFrame, games: pd.DataFrame) -> dict[str, Any]:
    press = _pressure_table(pff)
    files = sorted(tracking_dir.glob("tracking_*.csv"))
    plays_out: list[dict[str, Any]] = []
    games_out = []
    for path in files:
        chunk = catalog_from_tracking_file(path, plays, press, games)
        plays_out.extend(chunk)
        if chunk:
            g0 = chunk[0]
            games_out.append(
                {
                    "gameId": g0["gameId"],
                    "week": g0["week"],
                    "home": g0["home"],
                    "away": g0["away"],
                    "plays": len(chunk),
                }
            )
    teams = sorted({p["possessionTeam"] for p in plays_out} | {p["defensiveTeam"] for p in plays_out})
    return {
        "meta": {
            "source": "NFL Next Gen Stats tracking (Big Data Bowl)",
            "games": len(games_out),
            "plays": len(plays_out),
            "weekMin": int(games["week"].min()) if len(games) else None,
            "weekMax": int(games["week"].max()) if len(games) else None,
            "teams": teams,
            "motion": "ngs-tracking",
            "note": "Índice de todas as jogadas com snap; playback carrega frames NGS sob demanda.",
        },
        "games": games_out,
        "plays": plays_out,
    }


def write_json(document: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path


def extract_game_plays(
    tracking_path: Path,
    plays: pd.DataFrame,
    pff: pd.DataFrame,
    games: pd.DataFrame,
    max_plays: int = 12,
) -> dict[str, Any]:
    """Legacy single-game sample used by extract_play_motion.py."""
    track = pd.read_csv(tracking_path, usecols=TRACK_COLS, na_values=NA_VALUES)
    game_id = int(track["gameId"].iloc[0])
    ids = []
    for pid, chunk in track.groupby("playId"):
        if "ball_snap" in set(chunk["event"].dropna().astype(str)):
            ids.append(int(pid))
        if len(ids) >= max_plays:
            break
    out = [extract_play_document(track, plays, pff, games, pid) for pid in ids]
    game = games.loc[games["gameId"] == game_id].iloc[0]
    return {
        "meta": {
            "source": "NFL Next Gen Stats tracking (Big Data Bowl)",
            "gameId": game_id,
            "week": int(game["week"]),
            "home": str(game["homeTeamAbbr"]),
            "away": str(game["visitorTeamAbbr"]),
            "note": "Amostra de jogadas com frames reais (x,y,s).",
            "motion": "ngs-tracking",
        },
        "plays": out,
    }


write_play_motion = write_json
