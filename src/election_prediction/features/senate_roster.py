"""Dated official Senate seat identity, separate from historical election returns."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..geography import reference

ROSTER_SOURCE = "https://www.senate.gov/senators/"


def load_roster(path: str | Path, *, require_complete: bool = True) -> pd.DataFrame:
    roster = pd.read_csv(path, comment="#")
    required = {"state_po", "senate_class", "incumbent_name", "ballot_party", "caucus_party"}
    if not required.issubset(roster.columns):
        raise ValueError(f"Senate roster missing columns {sorted(required - set(roster.columns))}")
    if roster[list(required)].isna().any().any():
        raise ValueError("Senate roster contains missing seat identity or affiliation")
    if roster.duplicated(["state_po", "senate_class"]).any():
        raise ValueError("duplicate state/class Senate seat")
    if not roster["senate_class"].isin([1, 2, 3]).all():
        raise ValueError("Senate class must be 1, 2 or 3")
    if not roster["caucus_party"].isin(["DEMOCRAT", "REPUBLICAN"]).all():
        raise ValueError("each Senate caucus must be resolved from a cited source")
    if require_complete and (len(roster) != 100 or not roster.groupby("state_po").size().eq(2).all()):
        raise ValueError("Senate roster must cover exactly 100 seats, two per state")
    roster["geography_id"] = roster["state_po"].map(lambda s: f"state:{reference.by_postal(s).fips}")
    roster["source_url"] = ROSTER_SOURCE
    return roster


def scheduled_seats(roster: pd.DataFrame, specials: pd.DataFrame, *, cycle: int) -> pd.DataFrame:
    # Class I was elected in 2024, Class II in 2020, Class III in 2022.
    senate_class = {4: 2, 0: 3, 2: 1}[cycle % 6]
    regular = roster[roster["senate_class"] == senate_class].copy()
    regular["election_type"] = "regular"
    extra = specials[specials["cycle"] == cycle].copy()
    if extra.duplicated(["state_po", "senate_class"]).any():
        raise ValueError("duplicate special Senate seat")
    if len(extra) and (extra["source_url"].isna().any() or extra["retrieved_on"].isna().any()):
        raise ValueError("special elections require provenance")
    special = roster.merge(
        extra[["state_po", "senate_class"]], on=["state_po", "senate_class"], validate="one_to_one"
    )
    if len(special) != len(extra):
        raise ValueError("special election has no matching official Senate seat")
    special["election_type"] = "special"
    scheduled = pd.concat([regular, special], ignore_index=True)
    if scheduled.duplicated(["state_po", "senate_class"]).any():
        raise ValueError("a Senate seat cannot be both a regular and a special contest")
    # The current state-level projection key cannot encode two simultaneous races.
    if scheduled.duplicated("state_po").any():
        raise ValueError("two Senate contests in one state require seat-class projection keys")
    return scheduled


def reconcile(roster: pd.DataFrame, seats: pd.DataFrame) -> dict:
    up = seats[["state_po", "senate_class"]]
    if up.duplicated().any():
        raise ValueError("duplicate projected Senate seat")
    membership = roster.merge(
        up.assign(on_ballot=True), on=["state_po", "senate_class"], how="left", validate="one_to_one"
    )
    holdovers = membership[membership["on_ballot"].isna()]
    if len(seats) + len(holdovers) != 100:
        raise ValueError("projected Senate seats plus holdovers must equal 100")
    return {
        "seats_projected": len(seats),
        "holdovers": len(holdovers),
        "democratic_holdovers": int(holdovers["caucus_party"].eq("DEMOCRAT").sum()),
        "republican_holdovers": int(holdovers["caucus_party"].eq("REPUBLICAN").sum()),
        "current_democratic_caucus": int(roster["caucus_party"].eq("DEMOCRAT").sum()),
        "current_republican_caucus": int(roster["caucus_party"].eq("REPUBLICAN").sum()),
        "reconciled": True,
    }
