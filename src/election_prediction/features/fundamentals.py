"""Gold fundamentals feature tables.

Assembles model-ready rows from the gold race table + ACS demographics, encoding the
transparent-baseline predictors called out in the modeling backlog:

  F-002  past presidential two-party vote (lagged one cycle, like-for-like geography)
  F-006  demographics (college share, race/ethnicity, income, age)
  F-001  incumbency / open-seat (party of the previous winner as a proxy here)

The presidential panel is state x cycle with the current two-party Democratic share as
the target and the previous cycle's share + the national environment as predictors —
the classic fundamentals setup (CLAUDE.md §2 rule 5, §6 two-party basis).
"""
from __future__ import annotations

import pandas as pd

PRES_PANEL_COLUMNS = [
    "race_id", "cycle", "office", "state_po", "state_fips", "geoid",
    "two_party_dem_share", "lag_dem_share", "national_dem_share", "national_swing",
    "prev_winner_party", "college_share", "pct_white", "pct_black", "pct_hispanic",
    "median_household_income", "median_age",
]


def build_presidential_panel(race_table: pd.DataFrame, acs: pd.DataFrame | None = None) -> pd.DataFrame:
    """State x cycle presidential fundamentals panel with lagged vote + demographics."""
    pres = race_table[race_table["office"] == "president"].copy()
    pres = pres.dropna(subset=["two_party_dem_share"])
    pres = pres.sort_values(["state_po", "cycle"])
    pres["geoid"] = pres["state_fips"]  # state GEOID == state FIPS

    # lag within state (previous presidential cycle)
    pres["lag_dem_share"] = pres.groupby("state_po")["two_party_dem_share"].shift(1)
    pres["prev_winner_party"] = pres.groupby("state_po")["winner_party"].shift(1)

    # national environment = population-weighted mean two-party Dem share that cycle
    nat = (pres.assign(w=pres["total_votes"])
           .groupby("cycle")[["two_party_dem_share", "w"]]
           .apply(lambda g: (g["two_party_dem_share"] * g["w"]).sum() / g["w"].sum())
           .rename("national_dem_share"))
    pres = pres.merge(nat, on="cycle", how="left")
    # national swing vs previous cycle
    nat_lag = nat.shift(1).rename("national_dem_share_lag")
    pres = pres.merge(nat_lag, on="cycle", how="left")
    pres["national_swing"] = pres["national_dem_share"] - pres["national_dem_share_lag"]

    if acs is not None:
        cols = ["geoid", "college_share", "pct_white", "pct_black", "pct_hispanic",
                "median_household_income", "median_age"]
        pres = pres.merge(acs[cols], on="geoid", how="left")
    else:
        for c in ["college_share", "pct_white", "pct_black", "pct_hispanic",
                  "median_household_income", "median_age"]:
            pres[c] = pd.NA

    return pres[PRES_PANEL_COLUMNS].reset_index(drop=True)


def build_house_partisanship_input(race_table: pd.DataFrame) -> pd.DataFrame:
    """District x cycle two-party Dem share for the House partisanship score (F-003)."""
    house = race_table[race_table["office"] == "us_house"].copy()
    house = house.dropna(subset=["two_party_dem_share"])
    keep = ["race_id", "cycle", "state_po", "state_fips", "district_num", "geography_id",
            "two_party_dem_share", "winner_party", "uncontested_flag", "total_votes"]
    return house[keep].sort_values(["state_po", "district_num", "cycle"]).reset_index(drop=True)
