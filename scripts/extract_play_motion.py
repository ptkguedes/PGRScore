"""Build a tiny demo play-motion JSON from one external tracking CSV.

Does not copy week-sized tracking files into the git repo.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.ingest import NA_VALUES  # noqa: E402
from pipeline.play_motion import extract_game_plays, write_play_motion  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tracking",
        type=Path,
        default=Path("/tmp/bdb-tracking/tracking_2021090900.csv"),
    )
    parser.add_argument("--plays", type=Path, default=ROOT / "data" / "raw" / "plays.csv")
    parser.add_argument("--pff", type=Path, default=ROOT / "data" / "raw" / "pffScoutingData.csv")
    parser.add_argument("--games", type=Path, default=ROOT / "data" / "raw" / "games.csv")
    parser.add_argument("--max-plays", type=int, default=12)
    parser.add_argument("--out", type=Path, default=ROOT / "web" / "play_motion.json")
    args = parser.parse_args()
    if not args.tracking.exists():
        raise SystemExit(f"missing tracking file {args.tracking} (keep it outside git)")
    plays = pd.read_csv(args.plays, na_values=NA_VALUES)
    pff = pd.read_csv(args.pff, na_values=NA_VALUES)
    games = pd.read_csv(args.games, na_values=NA_VALUES)
    doc = extract_game_plays(args.tracking, plays, pff, games, max_plays=args.max_plays)
    path = write_play_motion(doc, args.out)
    print(f"plays={len(doc['plays'])} bytes={path.stat().st_size} -> {path}")
    demo = ROOT / "output" / "play_motion.json"
    demo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, demo)


if __name__ == "__main__":
    main()
