"""Scan local NGS tracking CSVs and write web/plays/index.json (no raw weeks in git)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.ingest import NA_VALUES  # noqa: E402
from pipeline.play_motion import build_catalog, write_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-dir", type=Path, default=Path("/tmp/bdb-tracking"))
    parser.add_argument("--plays", type=Path, default=ROOT / "data" / "raw" / "plays.csv")
    parser.add_argument("--pff", type=Path, default=ROOT / "data" / "raw" / "pffScoutingData.csv")
    parser.add_argument("--games", type=Path, default=ROOT / "data" / "raw" / "games.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "web" / "plays" / "index.json")
    args = parser.parse_args()
    files = list(args.tracking_dir.glob("tracking_*.csv"))
    if not files:
        raise SystemExit(f"no tracking_*.csv in {args.tracking_dir}")
    plays = pd.read_csv(args.plays, na_values=NA_VALUES)
    pff = pd.read_csv(args.pff, na_values=NA_VALUES)
    games = pd.read_csv(args.games, na_values=NA_VALUES)
    doc = build_catalog(args.tracking_dir, plays, pff, games)
    path = write_json(doc, args.out)
    print(
        f"games={doc['meta']['games']} plays={doc['meta']['plays']} "
        f"bytes={path.stat().st_size} -> {path}"
    )


if __name__ == "__main__":
    main()
