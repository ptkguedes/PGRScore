"""Official NFL position -> PGRScore group mapping (Big Data Bowl 2022)."""

from __future__ import annotations

POSITION_GROUPS: tuple[str, ...] = ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB")

GROUP_LABELS: dict[str, str] = {
    "QB": "Quarterbacks",
    "RB": "Running Backs",
    "WR": "Wide Receivers",
    "TE": "Tight Ends",
    "OL": "Linha Ofensiva",
    "DL": "Linha Defensiva",
    "LB": "Linebackers",
    "DB": "Defensive Backs",
}

# officialPosition in players.csv -> dashboard group
OFFICIAL_TO_GROUP: dict[str, str] = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "T": "OL",
    "G": "OL",
    "C": "OL",
    "OT": "OL",
    "OG": "OL",
    "DE": "DL",
    "DT": "DL",
    "NT": "DL",
    "OLB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "LB": "LB",
    "CB": "DB",
    "FS": "DB",
    "SS": "DB",
    "DB": "DB",
    "S": "DB",
}

OFFENSE_PFF_ROLES: frozenset[str] = frozenset({"Pass", "Pass Route", "Pass Block"})


def group_for(official_position: str | None) -> str | None:
    if official_position is None:
        return None
    return OFFICIAL_TO_GROUP.get(str(official_position).strip().upper())
