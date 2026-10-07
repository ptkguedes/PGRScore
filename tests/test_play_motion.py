"""Catalog helpers for NGS play thumbs (no 850 MB tracking CSVs)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.play_motion import pack_frame, pack_snap  # noqa: E402


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"frameId": 6, "nflId": 1, "jerseyNumber": 15, "team": "KC", "x": 73.4, "y": 26.8, "s": 0.5, "event": "ball_snap"},
            {"frameId": 6, "nflId": 2, "jerseyNumber": 95, "team": "CLE", "x": 72.1, "y": 20.7, "s": 0.2, "event": "ball_snap"},
            {"frameId": 6, "nflId": None, "jerseyNumber": None, "team": "football", "x": 72.8, "y": 26.8, "s": 0.0, "event": "ball_snap"},
        ]
    )


def test_pack_frame_keeps_ball_and_jerseys() -> None:
    packed = pack_frame(_frame())
    assert packed["f"] == 6
    assert packed["b"] == [72.8, 26.8]
    teams = {p["t"] for p in packed["p"]}
    assert teams == {"KC", "CLE"}
    assert all("id" in p and "j" in p and "x" in p and "y" in p for p in packed["p"])


def test_pack_snap_is_compact() -> None:
    snap = pack_snap(_frame())
    assert snap["b"] == [72.8, 26.8]
    assert snap["p"][0][0] in {"KC", "CLE"}
    assert len(snap["p"][0]) == 4
