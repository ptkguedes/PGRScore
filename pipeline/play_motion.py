"""Compact NGS tracking slices for dashboard playback (frame x,y,s,dir,event)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

NA_VALUES = ["NA", "na", ""]


def _round(val: float, n: int = 2) -> float:
    return float(round(float(val), n))


def extract_game_plays(
    tracking_path: Path,
    plays: pd.DataFrame,
    pff: pd.DataFrame,
    games: pd.DataFrame,
    max_plays: int = 12,
) -> dict[str, Any]:
    track = pd.read_csv(tracking_path, na_values=NA_VALUES)
    game_id = int(track["gameId"].iloc[0])
    game = games.loc[games["gameId"] == game_id].iloc[0]
    gplays = plays.loc[plays["gameId"] == game_id].copy()

    press = (
        pff.loc[pff["gameId"] == game_id]
        .assign(
            hit=lambda d: pd.to_numeric(d["pff_hit"], errors="coerce").fillna(0),
            hurry=lambda d: pd.to_numeric(d["pff_hurry"], errors="coerce").fillna(0),
            sack=lambda d: pd.to_numeric(d["pff_sack"], errors="coerce").fillna(0),
        )
        .groupby(["playId"], as_index=False)
        .agg(hits=("hit", "sum"), hurries=("hurry", "sum"), sacks=("sack", "sum"))
    )

    play_ids = []
    for pid, chunk in track.groupby("playId"):
        ev = set(chunk["event"].dropna().astype(str))
        if "ball_snap" not in ev:
            continue
        play_ids.append(int(pid))
        if len(play_ids) >= max_plays:
            break

    out_plays: list[dict[str, Any]] = []
    for pid in play_ids:
        chunk = track.loc[track["playId"] == pid].sort_values(["frameId", "nflId"])
        meta_row = gplays.loc[gplays["playId"] == pid]
        if meta_row.empty:
            continue
        meta = meta_row.iloc[0]
        pr = press.loc[press["playId"] == pid]
        pressure = {
            "hits": int(pr["hits"].iloc[0]) if len(pr) else 0,
            "hurries": int(pr["hurries"].iloc[0]) if len(pr) else 0,
            "sacks": int(pr["sacks"].iloc[0]) if len(pr) else 0,
        }
        snap_frames = chunk.loc[chunk["event"] == "ball_snap", "frameId"]
        rel_frames = chunk.loc[chunk["event"] == "pass_forward", "frameId"]
        snap_f = int(snap_frames.min()) if len(snap_frames) else int(chunk["frameId"].min())
        rel_f = int(rel_frames.min()) if len(rel_frames) else None

        frames = []
        for fid, fr in chunk.groupby("frameId"):
            ball = fr.loc[fr["team"] == "football"]
            players = fr.loc[fr["team"] != "football"]
            plist = []
            for _, row in players.iterrows():
                if pd.isna(row["x"]) or pd.isna(row["y"]):
                    continue
                plist.append(
                    {
                        "id": None if pd.isna(row["nflId"]) else int(row["nflId"]),
                        "t": str(row["team"]),
                        "j": None if pd.isna(row["jerseyNumber"]) else int(row["jerseyNumber"]),
                        "x": _round(row["x"]),
                        "y": _round(row["y"]),
                        "s": _round(row["s"], 2),
                    }
                )
            ball_xy = None
            if len(ball) and pd.notna(ball.iloc[0]["x"]):
                ball_xy = [_round(ball.iloc[0]["x"]), _round(ball.iloc[0]["y"])]
            frames.append({"f": int(fid), "b": ball_xy, "p": plist})

        desc = str(meta["playDescription"])
        out_plays.append(
            {
                "gameId": game_id,
                "playId": pid,
                "desc": desc,
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
                "frames": frames,
            }
        )

    return {
        "meta": {
            "source": "NFL Next Gen Stats tracking (Big Data Bowl)",
            "gameId": game_id,
            "week": int(game["week"]),
            "home": str(game["homeTeamAbbr"]),
            "away": str(game["visitorTeamAbbr"]),
            "note": "Amostra de jogadas com frames reais (x,y,s). Não é animação sintética.",
            "motion": "ngs-tracking",
        },
        "plays": out_plays,
    }


def write_play_motion(document: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path
