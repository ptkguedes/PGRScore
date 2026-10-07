"""CLI: raw CSVs + tracking overlay -> processed_data.json + SQLite."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.assemble import assemble_document, build_player_table  # noqa: E402
from pipeline.ingest import (  # noqa: E402
    aggregate_pff,
    assign_snap_teams,
    load_games,
    load_pff,
    load_players,
    load_plays,
    load_team_ref,
    load_tracking,
)
from pipeline.persist import write_processed_json, write_sqlite  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PGRScore processed dataset")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--ref", type=Path, default=ROOT / "data" / "ref" / "teams_2021.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    parser.add_argument(
        "--web-dir",
        type=Path,
        default=ROOT / "web",
        help="Copy processed_data.json here so the dashboard can fetch it",
    )
    return parser.parse_args()


def run(raw_dir: Path, ref: Path, output_dir: Path, web_dir: Path | None) -> dict[str, Path]:
    games = load_games(raw_dir)
    players = load_players(raw_dir)
    pff = load_pff(raw_dir)
    plays = load_plays(raw_dir)
    tracking = load_tracking(raw_dir)
    team_ref = load_team_ref(ref)

    snaps = assign_snap_teams(pff, plays)
    pff_agg = aggregate_pff(snaps)
    scored = build_player_table(players, pff_agg, tracking)
    document = assemble_document(scored, games, team_ref)

    json_path = write_processed_json(document, output_dir / "processed_data.json")
    sqlite_path = write_sqlite(scored, document, output_dir / "pgrscore.sqlite")
    web_copy = None
    if web_dir is not None:
        web_dir.mkdir(parents=True, exist_ok=True)
        web_copy = web_dir / "processed_data.json"
        shutil.copyfile(json_path, web_copy)

    print(
        f"players={len(scored)} games={len(games)} "
        f"json={json_path} sqlite={sqlite_path}"
        + (f" web={web_copy}" if web_copy else "")
    )
    return {"json": json_path, "sqlite": sqlite_path}


def main() -> None:
    args = parse_args()
    run(args.raw_dir, args.ref, args.output_dir, args.web_dir)


if __name__ == "__main__":
    main()
