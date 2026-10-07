"""Download public NFL team marks into web/logos/ for offline dashboard tiles.

Primary: ESPN CDN PNG. Aliases: LA→lar, WAS→wsh.
Fallback: ESPN 500-dark, then Wikimedia Commons (Giants).
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAMS_PATH = ROOT / "data" / "ref" / "teams_2021.json"
OUT_DIR = ROOT / "web" / "logos"

ESPN_ALIAS = {"LA": "lar", "WAS": "wsh"}
WIKI_PNG = {
    "NYG": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/New_York_Giants_logo.svg/500px-New_York_Giants_logo.svg.png",
}
MIN_BYTES = 12000
UA = {"User-Agent": "PGRScore-logo-fetch/1.0 (educational; github.com/ptkguedes/PGRScore)"}
CTX = ssl.create_default_context()


def download(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
        if "png" not in ctype and "octet-stream" not in ctype:
            return None
        if len(data) < 800:
            return None
        return data
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def urls_for(abbr: str) -> list[str]:
    espn = ESPN_ALIAS.get(abbr, abbr).lower()
    out = [
        f"https://a.espncdn.com/i/teamlogos/nfl/500/{espn}.png",
        f"https://a.espncdn.com/i/teamlogos/nfl/500-dark/{espn}.png",
    ]
    if abbr in WIKI_PNG:
        out.append(WIKI_PNG[abbr])
    return out


def fetch_one(abbr: str) -> tuple[bool, str]:
    dest = OUT_DIR / f"{abbr}.png"
    last = ""
    for url in urls_for(abbr):
        data = download(url)
        last = url
        if not data:
            continue
        if dest.exists() is False or len(data) >= MIN_BYTES or not dest.exists():
            dest.write_bytes(data)
            if len(data) >= MIN_BYTES or url == urls_for(abbr)[-1]:
                return True, f"{len(data)} {url}"
        time.sleep(0.05)
    if dest.exists() and dest.stat().st_size >= 800:
        return True, f"kept {dest.stat().st_size} {last}"
    return False, last


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    teams = json.loads(TEAMS_PATH.read_text(encoding="utf-8"))
    failed = []
    for team in teams:
        abbr = team["abbr"]
        ok, detail = fetch_one(abbr)
        print(("OK" if ok else "FAIL"), abbr, detail)
        if not ok:
            failed.append(abbr)
    if failed:
        raise SystemExit(f"missing logos: {failed}")


if __name__ == "__main__":
    main()
