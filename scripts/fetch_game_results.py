"""Attach official 2021 week 1–8 finals to games.csv (ESPN scoreboard API).

games.csv has no scores. This writes data/raw/game_results.csv keyed by gameId.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ESPN_TO_REPO = {"LAR": "LA", "WSH": "WAS"}
UA = {"User-Agent": "PGRScore/1.0 (educational; github.com/ptkguedes/PGRScore)"}
CTX = ssl.create_default_context()


def espn_week(week: int) -> list[dict]:
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        f"?dates=2021&seasontype=2&week={week}"
    )
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
        payload = json.loads(resp.read().decode())
    out = []
    for event in payload.get("events") or []:
        comp = (event.get("competitions") or [None])[0]
        if not comp:
            continue
        teams = comp.get("competitors") or []
        home = next((t for t in teams if t.get("homeAway") == "home"), None)
        away = next((t for t in teams if t.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        status = ((comp.get("status") or {}).get("type") or {}).get("name")
        if status != "STATUS_FINAL":
            continue
        ha = ESPN_TO_REPO.get(home["team"]["abbreviation"], home["team"]["abbreviation"])
        aa = ESPN_TO_REPO.get(away["team"]["abbreviation"], away["team"]["abbreviation"])
        out.append(
            {
                "week": week,
                "homeTeamAbbr": ha,
                "visitorTeamAbbr": aa,
                "homeScore": int(home["score"]),
                "visitorScore": int(away["score"]),
            }
        )
    return out


def main() -> None:
    games = pd.read_csv(ROOT / "data" / "raw" / "games.csv")
    espn_rows: list[dict] = []
    for week in range(1, 9):
        espn_rows.extend(espn_week(week))
        time.sleep(0.1)
    espn = pd.DataFrame(espn_rows)
    merged = games.merge(
        espn,
        on=["week", "homeTeamAbbr", "visitorTeamAbbr"],
        how="left",
        validate="one_to_one",
    )
    missing = merged[merged["homeScore"].isna()]
    if len(missing):
        raise SystemExit(f"unmatched games:\n{missing[['gameId','week','homeTeamAbbr','visitorTeamAbbr']]}")
    out = merged[["gameId", "week", "homeTeamAbbr", "visitorTeamAbbr", "homeScore", "visitorScore"]]
    dest = ROOT / "data" / "raw" / "game_results.csv"
    out.to_csv(dest, index=False)
    print(f"wrote {dest} n={len(out)}")


if __name__ == "__main__":
    main()
