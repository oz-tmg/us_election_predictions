"""Model-ready race table (P0-008).

Collapses the conformed silver election-returns (one row per candidate) into the
central modeling grain: one row per race, with winner, margin, two-party Democratic
share, candidate count, and contest flags. Two-party share is the default comparison
basis (CLAUDE.md §6); third-party votes are excluded from it but retained in totals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RACE_TABLE_COLUMNS = [
    "race_id",
    "cycle",
    "office",
    "state_po",
    "state_fips",
    "district_num",
    "geography_id",
    "geog_level",
    "n_candidates",
    "total_votes",
    "winner",
    "winner_party",
    "winner_votes",
    "winner_share",
    "runner_up",
    "runner_up_party",
    "runner_up_votes",
    "margin_votes",
    "margin_share",
    "dem_votes",
    "rep_votes",
    "other_votes",
    "two_party_dem_share",
    "uncontested_flag",
    "certified_flag",
    "source_id",
    "snapshot_date",
]


def _int_or_none(value) -> int | None:
    """Coerce a possibly-NA nullable vote count to ``int``, preserving 'not reported'."""
    return None if pd.isna(value) else int(value)


def _party_votes(g: pd.DataFrame, party: str) -> int:
    return int(g.loc[g["party_simplified"] == party, "candidatevotes"].sum())


def build_race_table(returns: pd.DataFrame) -> pd.DataFrame:
    """Build the gold race table from silver election returns.

    ``returns`` must carry the silver schema (see data.medsl.SILVER_COLUMNS).
    """
    rows = []
    for race_id, g in returns.groupby("race_id", sort=False):
        g = g.sort_values("candidatevotes", ascending=False, na_position="last")
        first = g.iloc[0]

        # A race whose jurisdiction reported no count (MEDSL's -1 sentinel, typically
        # an unopposed candidate elected without appearing on the ballot) has a real
        # winner but no vote totals. Counts stay null rather than collapsing to zero,
        # so downstream shares are excluded instead of silently reading as 0-0.
        winner_votes = _int_or_none(first["candidatevotes"])
        n_cand = int((g["candidatevotes"] > 0).fillna(False).sum())

        total: int | None = None
        dem: int | None = None
        rep: int | None = None
        other: int | None = None
        margin_votes: int | None = None
        two_party_dem: float = np.nan
        winner_share: float = np.nan
        margin_share: float = np.nan

        if len(g) > 1:
            second = g.iloc[1]
            ru = second["candidate"]
            ru_party = second["party_simplified"]
            ru_votes = _int_or_none(second["candidatevotes"]) or 0
        else:
            ru, ru_party, ru_votes = None, None, 0

        if winner_votes is not None:
            total = int(g["candidatevotes"].sum())
            dem = _party_votes(g, "DEMOCRAT")
            rep = _party_votes(g, "REPUBLICAN")
            other = total - dem - rep
            margin_votes = winner_votes - ru_votes
            if dem + rep > 0:
                two_party_dem = dem / (dem + rep)
            if total > 0:
                winner_share = winner_votes / total
                margin_share = margin_votes / total
        rows.append(
            {
                "race_id": race_id,
                "cycle": int(first["cycle"]),
                "office": first["office"],
                "state_po": first["state_po"],
                "state_fips": first["state_fips"],
                "district_num": first["district_num"],
                "geography_id": first["geography_id"],
                "geog_level": first["geog_level"],
                "n_candidates": n_cand,
                "total_votes": total,
                "winner": first["candidate"],
                "winner_party": first["party_simplified"],
                "winner_votes": winner_votes,
                "winner_share": winner_share,
                "runner_up": ru,
                "runner_up_party": ru_party,
                "runner_up_votes": ru_votes,
                "margin_votes": margin_votes,
                "margin_share": margin_share,
                "dem_votes": dem,
                "rep_votes": rep,
                "other_votes": other,
                "two_party_dem_share": two_party_dem,
                "uncontested_flag": bool(first["uncontested_flag"]),
                "certified_flag": bool(first["certified_flag"]),
                "source_id": first["source_id"],
                "snapshot_date": first["snapshot_date"],
            }
        )
    out = pd.DataFrame(rows, columns=RACE_TABLE_COLUMNS)
    return out.sort_values(["cycle", "office", "state_po", "race_id"]).reset_index(drop=True)
