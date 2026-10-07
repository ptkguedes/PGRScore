"""PGRScore: Madden-style 40–99 index computed within position group.

The original hackathon dashboard embedded precomputed scores in ``data.js``.
The missing ``pipeline.py`` derived those scores from Big Data Bowl tracking
(speed, acceleration, yards/snap) plus PFF pressures / sacks allowed.

This module makes that business rule explicit and vectorized.

Formula (documented, position-relative)
---------------------------------------
For each position group independently:

1. Build component z-scores (population std, ddof=0):

   * ``z_snaps``  = z(log1p(snaps))     — playing time
   * ``z_speed``  = z(topSpeedMph)      — peak tracking speed
   * ``z_burst``  = z(burst yd/s²)      — peak acceleration
   * ``z_motor``  = z(yards per snap)   — work rate
   * ``z_press``  = z(pressures)        — DL/LB only (PFF hit + hurry)
   * ``z_passpro``= z(-sacks_allowed)   — OL only (fewer sacks allowed is better)

2. Weighted composite ``z`` using ``GROUP_WEIGHTS``.

3. Map to the closed integer interval [40, 99] with a logistic curve
   shifted so a group-average player lands near 78 (typical Madden / original
   sample bulk ~55–97, mean ~80–86):

       pgr = 40 + 59 * sigmoid(0.85 * z + 0.70)
       pgrScore = clip(round(pgr), 40, 99)

Props (over/under lines) match the original dashboard conventions:

* top_speed line = actual − 0.6 mph
* burst line     = actual − 0.4 yd/s²
* motor line     = actual − 0.5 yd/snap
* pressures line = actual − 0.5
* pass_pro line  = 0.5 (any sack allowed is OVER)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SCORE_MIN = 40
SCORE_MAX = 99
SIGMOID_SCALE = 0.85
SIGMOID_SHIFT = 0.70

# Weights sum to 1.0 per group.
GROUP_WEIGHTS: dict[str, dict[str, float]] = {
    "QB": {"snaps": 0.30, "speed": 0.40, "burst": 0.20, "motor": 0.10},
    "RB": {"snaps": 0.30, "speed": 0.35, "burst": 0.25, "motor": 0.10},
    "WR": {"snaps": 0.30, "speed": 0.35, "burst": 0.25, "motor": 0.10},
    "TE": {"snaps": 0.30, "speed": 0.35, "burst": 0.20, "motor": 0.15},
    "OL": {"snaps": 0.25, "speed": 0.25, "burst": 0.25, "motor": 0.05, "pass_pro": 0.20},
    "DL": {"snaps": 0.25, "speed": 0.30, "burst": 0.20, "motor": 0.05, "pressures": 0.20},
    "LB": {"snaps": 0.25, "speed": 0.30, "burst": 0.20, "motor": 0.05, "pressures": 0.20},
    "DB": {"snaps": 0.30, "speed": 0.40, "burst": 0.20, "motor": 0.10},
}

PROP_DELTAS = {
    "top_speed": 0.6,
    "burst": 0.4,
    "motor": 0.5,
    "pressures": 0.5,
}


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    x = np.clip(x, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-x))


def zscore(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    mean = values.mean()
    std = values.std(ddof=0)
    if not np.isfinite(std) or std == 0:
        return pd.Series(0.0, index=series.index)
    return (values - mean) / std


def composite_z(frame: pd.DataFrame, group: str) -> pd.Series:
    weights = GROUP_WEIGHTS.get(group) or GROUP_WEIGHTS["DB"]
    acc = pd.Series(0.0, index=frame.index)
    weight_sum = 0.0
    mapping = {
        "snaps": "z_snaps",
        "speed": "z_speed",
        "burst": "z_burst",
        "motor": "z_motor",
        "pressures": "z_pressures",
        "pass_pro": "z_pass_pro",
    }
    for key, col in mapping.items():
        w = weights.get(key)
        if not w or col not in frame.columns:
            continue
        acc = acc + w * frame[col].fillna(0.0)
        weight_sum += w
    if weight_sum == 0:
        return acc
    return acc / weight_sum


def map_to_pgr_score(z_composite: pd.Series) -> pd.Series:
    raw = SCORE_MIN + (SCORE_MAX - SCORE_MIN) * sigmoid(
        SIGMOID_SCALE * z_composite.to_numpy() + SIGMOID_SHIFT
    )
    return pd.Series(np.clip(np.round(raw), SCORE_MIN, SCORE_MAX), index=z_composite.index).astype(int)


def attach_z_and_scores(players: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with component z-scores and integer pgrScore."""
    out = players.copy()
    z_cols = ["z_snaps", "z_speed", "z_burst", "z_motor", "z_pressures", "z_pass_pro", "z_composite"]
    for col in z_cols:
        out[col] = 0.0
    out["pgrScore"] = SCORE_MIN

    for group, idx in out.groupby("group", sort=False).groups.items():
        g = out.loc[idx]
        z_snaps = zscore(np.log1p(g["snaps"].astype(float)))
        z_speed = zscore(g["topSpeedMph"])
        z_burst = zscore(g["burstYdS2"])
        z_motor = zscore(g["distPerSnap"])
        z_press = zscore(g["pressures"])
        z_pass = zscore(-g["sacksAllowed"].astype(float))
        block = pd.DataFrame(
            {
                "z_snaps": z_snaps,
                "z_speed": z_speed,
                "z_burst": z_burst,
                "z_motor": z_motor,
                "z_pressures": z_press,
                "z_pass_pro": z_pass,
            },
            index=idx,
        )
        zc = composite_z(block, str(group))
        out.loc[idx, "z_snaps"] = z_snaps
        out.loc[idx, "z_speed"] = z_speed
        out.loc[idx, "z_burst"] = z_burst
        out.loc[idx, "z_motor"] = z_motor
        out.loc[idx, "z_pressures"] = z_press
        out.loc[idx, "z_pass_pro"] = z_pass
        out.loc[idx, "z_composite"] = zc
        out.loc[idx, "pgrScore"] = map_to_pgr_score(zc)
    return out


def _round_line(actual: float, delta: float, ndigits: int) -> float:
    return round(float(actual) - delta, ndigits)


def build_props(row: pd.Series) -> list[dict[str, Any]]:
    """Over/under props shown on player cards (presentation data only)."""
    props: list[dict[str, Any]] = [
        {
            "key": "top_speed",
            "label": "Velocidade Máx",
            "line": _round_line(row["topSpeedMph"], PROP_DELTAS["top_speed"], 1),
            "actual": round(float(row["topSpeedMph"]), 1) if pd.notna(row["topSpeedMph"]) else None,
            "unit": "mph",
        },
        {
            "key": "burst",
            "label": "Aceleração Máx",
            "line": _round_line(row["burstYdS2"], PROP_DELTAS["burst"], 2),
            "actual": round(float(row["burstYdS2"]), 2) if pd.notna(row["burstYdS2"]) else None,
            "unit": "yd/s²",
        },
        {
            "key": "motor",
            "label": "Jardas / snap",
            "line": _round_line(row["distPerSnap"], PROP_DELTAS["motor"], 1),
            "actual": round(float(row["distPerSnap"]), 1) if pd.notna(row["distPerSnap"]) else None,
            "unit": "yd",
        },
    ]
    group = row.get("group")
    if group in {"DL", "LB"}:
        actual = float(row["pressures"])
        props.append(
            {
                "key": "pressures",
                "label": "Pressões",
                "line": actual - PROP_DELTAS["pressures"],
                "actual": actual,
                "unit": "",
            }
        )
    if group == "OL":
        props.append(
            {
                "key": "pass_pro",
                "label": "Sacks permitidos",
                "line": 0.5,
                "actual": float(row["sacksAllowed"]),
                "unit": "",
            }
        )
    return props
