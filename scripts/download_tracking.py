"""Download Bliss NGS tracking CSVs to a local dir (not committed)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = (
    "https://raw.githubusercontent.com/ThompsonJamesBliss/"
    "nfl-big-data-bowl-regional-event-data/main/data/tracking"
)


def main() -> None:
    dest = Path("/tmp/bdb-tracking")
    dest.mkdir(parents=True, exist_ok=True)
    games = pd.read_csv(ROOT / "data" / "raw" / "games.csv")
    cmds = []
    for gid in games["gameId"].astype(int).tolist():
        path = dest / f"tracking_{gid}.csv"
        if path.exists() and path.stat().st_size > 1000:
            continue
        url = f"{BASE}/tracking_{gid}.csv"
        cmds.append(f"curl -fsSL --retry 3 -o {path} {url}")
    print(f"download {len(cmds)} files to {dest}")
    if cmds:
        script = dest / "fetch.sh"
        script.write_text("\n".join(cmds) + "\n", encoding="utf-8")
        subprocess.check_call(["bash", "-c", f"cat {script} | xargs -P 8 -I{{}} bash -c '{{}}'"])
    n = len(list(dest.glob("tracking_*.csv")))
    print("csv files", n)


if __name__ == "__main__":
    main()
