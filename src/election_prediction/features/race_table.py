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
    "race_id", "cycle", "office", "state_po", "state_fips", "district_num",
    "geography_id", "geog_level", "n_candidates", "total_votes",
    "winner", "winner_party", "winner_votes", "winner_share",
    "runner_up", "runner_up_party", "runner_up_votes",
    "margin_votes", "margin_share",
    "dem_votes", "rep_votes", "other_votes",
    "two_party_dem_share", "uncontested_flag", "certified_flag",
    "source_id", "snapshot_date",
]


def build_race_table(returns: pd.DataFrame) -> pd.DataFrame:
    """Build the gold race table from silver election returns.

    ``returns`` must carry the silver schema (see data.medsl.SILVER_COLUMNS).
    """
    rows = []
    for race_id, g in returns.groupby("race_id", sort=False):
        g = g.sort_values("candidatevotes", ascending=False)
        first = g.iloc[0]
        total = int(g["candidatevotes"].sum())
        n_cand = int((g["candidatevotes"] > 0).sum())

        dem = int(g.loc[g["party_simplified"] == "DEMOCRAT", "candidatevotes"].sum())
        rep = int(g.loc[g["party_simplified"] == "REPUBLICAN", "candidatevotes"].sum())
        other = total - dem - rep
        two_party = dem + rep
        two_party_dem = (dem / two_party) if two_party > 0 else np.nan

        if len(g) > 1:
            second = g.iloc[1]
            ru = second["candidate"]
            ru_party = second["party_simplified"]
            ru_votes = int(second["candidatevotes"])
        else:
            ru, ru_party, ru_votes = None, None, 0

        margin_votes = int(first["candidatevotes"]) - ru_votes
        rows.append({
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
            "winner_votes": int(first["candidatevotes"]),
            "winner_share": (int(first["candidatevotes"]) / total) if total else np.nan,
            "runner_up": ru,
            "runner_up_party": ru_party,
            "runner_up_votes": ru_votes,
            "margin_votes": margin_votes,
            "margin_share": (margin_votes / total) if total else np.nan,
            "dem_votes": dem,
            "rep_votes": rep,
            "other_votes": other,
            "two_party_dem_share": two_party_dem,
            "uncontested_flag": bool(first["uncontested_flag"]),
            "certified_flag": bool(first["certified_flag"]),
            "source_id": first["source_id"],
            "snapshot_date": first["snapshot_date"],
        })
    out = pd.DataFrame(rows, columns=RACE_TABLE_COLUMNS)
    return out.sort_values(["cycle", "office", "state_po", "race_id"]).reset_index(drop=True)
