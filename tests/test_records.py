"""Week 1–8 W-L-T from scored games (no full-season table)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.records import compute_team_records, format_record  # noqa: E402


def test_format_record() -> None:
    assert format_record(6, 2, 0) == "6-2"
    assert format_record(4, 3, 1) == "4-3-1"


def test_records_from_scored_games() -> None:
    games = pd.DataFrame(
        {
            "week": [1, 1],
            "homeTeamAbbr": ["TB", "GB"],
            "visitorTeamAbbr": ["DAL", "NO"],
            "homeScore": [31, 3],
            "visitorScore": [29, 38],
        }
    )
    table = compute_team_records(games).set_index("abbr")
    assert table.loc["TB", "record"] == "1-0"
    assert table.loc["DAL", "record"] == "0-1"
    assert table.loc["NO", "record"] == "1-0"
    assert table.loc["GB", "record"] == "0-1"
    assert int(table.loc["TB", "rank"]) < int(table.loc["DAL", "rank"])


if __name__ == "__main__":
    test_format_record()
    test_records_from_scored_games()
    print("ok")
