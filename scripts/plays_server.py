"""Serve the dashboard plus on-demand NGS play frames (tracking CSVs stay on disk)."""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.ingest import NA_VALUES  # noqa: E402
from pipeline.play_motion import TRACK_COLS, extract_play_document  # noqa: E402


def load_tables(raw: Path):
    plays = pd.read_csv(raw / "plays.csv", na_values=NA_VALUES)
    pff = pd.read_csv(raw / "pffScoutingData.csv", na_values=NA_VALUES)
    games = pd.read_csv(raw / "games.csv", na_values=NA_VALUES)
    return plays, pff, games


def make_handler(web_dir: Path, tracking_dir: Path, plays, pff, games):
    @lru_cache(maxsize=4)
    def tracking_for(game_id: int):
        path = tracking_dir / f"tracking_{game_id}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        return pd.read_csv(path, usecols=TRACK_COLS, na_values=NA_VALUES)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_dir), **kwargs)

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "motion":
                try:
                    game_id = int(parts[2])
                    play_id = int(parts[3])
                    track = tracking_for(game_id)
                    doc = extract_play_document(track, plays, pff, games, play_id)
                    payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                except FileNotFoundError:
                    self.send_error(404, "tracking csv missing")
                    return
                except KeyError:
                    self.send_error(404, "play not found")
                    return
                except Exception as exc:  # noqa: BLE001
                    self.send_error(500, str(exc))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "public, max-age=120")
                self.end_headers()
                self.wfile.write(payload)
                return
            return super().do_GET()

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=43127)
    parser.add_argument("--web", type=Path, default=ROOT / "web")
    parser.add_argument("--tracking-dir", type=Path, default=Path("/tmp/bdb-tracking"))
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    plays, pff, games = load_tables(args.raw)
    handler = make_handler(args.web, args.tracking_dir, plays, pff, games)
    httpd = ThreadingHTTPServer(("0.0.0.0", args.port), handler)
    print(f"dashboard http://127.0.0.1:{args.port}  tracking={args.tracking_dir}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
