"""Unit tests for the PGRScore mapping (no raw CSVs required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.pgr_score_calculator import (  # noqa: E402
    SCORE_MAX,
    SCORE_MIN,
    attach_z_and_scores,
    build_props,
    map_to_pgr_score,
    zscore,
)


def test_zscore_zero_variance() -> None:
    s = pd.Series([5.0, 5.0, 5.0])
    assert list(zscore(s)) == [0.0, 0.0, 0.0]


def test_score_bounds() -> None:
    out = map_to_pgr_score(pd.Series([-10.0, 0.0, 10.0]))
    assert int(out.min()) >= SCORE_MIN
    assert int(out.max()) <= SCORE_MAX
    assert int(out.iloc[1]) >= 70  # average player sits in the high 70s


def test_within_group_ranking() -> None:
    frame = pd.DataFrame(
        {
            "group": ["QB", "QB"],
            "snaps": [300, 2],
            "topSpeedMph": [20.0, 8.0],
            "burstYdS2": [9.0, 3.0],
            "distPerSnap": [8.0, 4.0],
            "pressures": [0.0, 0.0],
            "sacksAllowed": [0.0, 0.0],
        }
    )
    scored = attach_z_and_scores(frame)
    assert int(scored.iloc[0]["pgrScore"]) > int(scored.iloc[1]["pgrScore"])


def test_ol_props_include_pass_pro() -> None:
    row = pd.Series(
        {
            "group": "OL",
            "topSpeedMph": 11.4,
            "burstYdS2": 5.61,
            "distPerSnap": 7.7,
            "pressures": 0.0,
            "sacksAllowed": 2.0,
        }
    )
    keys = {p["key"] for p in build_props(row)}
    assert keys == {"top_speed", "burst", "motor", "pass_pro"}


if __name__ == "__main__":
    test_zscore_zero_variance()
    test_score_bounds()
    test_within_group_ranking()
    test_ol_props_include_pass_pro()
    print("ok")
