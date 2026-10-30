"""Cycle-level macro features with one explicit historical information set per row."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..models.baseline.senate import _white_house_party

# Incumbent presidents on the November ballot, not merely presidential election years.
# FEC certified candidate returns establish these historical ballot identities.
PRESIDENT_ON_BALLOT = {1976, 1980, 1984, 1992, 1996, 2004, 2012, 2020}


def political_features(races: pd.DataFrame, *, cycle: int) -> dict:
    winners = _white_house_party(races)
    prior = winners[winners.index < cycle]
    if prior.empty:
        raise ValueError("no presidential election before target cycle")
    incumbent = str(prior.iloc[-1])
    terms = 0
    for party in reversed(prior.tolist()):
        if party != incumbent:
            break
        terms += 1
    return {
        "cycle": cycle,
        "white_house_party": incumbent,
        "president_on_ballot": float(cycle in PRESIDENT_ON_BALLOT),
        "consecutive_terms": float(terms),
        "midterm": float(cycle % 4 == 2),
    }


def economic_features(observations: pd.DataFrame, *, cycle: int, vintage: str) -> dict:
    if pd.Timestamp(vintage).year != cycle:
        raise ValueError("economic vintage must belong to predicted election year")
    rows = {"cycle": cycle, "data_vintage": vintage, "release_date_policy": "unknown if not supplied"}
    for series, feature in [
        ("A229RX0", "income_growth"),
        ("UNRATE", "unemployment_change"),
        ("CPIAUCSL", "inflation"),
    ]:
        series_rows = observations[observations.series_id.eq(series)].copy()
        if series_rows.empty:
            rows[feature] = float("nan")
            continue
        if not series_rows.data_vintage.eq(vintage).all():
            raise ValueError("economic observations mix or misstate historical vintages")
        series_rows["date"] = pd.to_datetime(series_rows.observation_date)
        if (series_rows.date > pd.Timestamp(vintage)).any() or series_rows.date.duplicated().any():
            raise ValueError("future or duplicate economic observation")
        values = series_rows.set_index("date").value.sort_index()
        latest = values.index[-1]
        previous = latest - pd.DateOffset(years=1)
        if previous not in values.index:
            rows[feature] = float("nan")
            continue
        first, last = float(values.loc[previous]), float(values.loc[latest])
        if not np.isfinite([first, last]).all() or (series != "UNRATE" and min(first, last) <= 0):
            raise ValueError("nonfinite/nonpositive economic growth inputs")
        rows[feature] = last - first if series == "UNRATE" else float(np.log(last / first))
        rows[f"{feature}_observation_date"] = latest.date().isoformat()
    return rows


def target(races: pd.DataFrame, *, cycle: int, white_house_party: str) -> float:
    house = races[races.cycle.eq(cycle) & races.office.eq("us_house") & ~races.state_po.eq("DC")]
    if house.empty:
        return float("nan")
    two_party = house.dem_votes.sum() + house.rep_votes.sum()
    if two_party <= 0:
        raise ValueError("national House target has no two-party votes")
    dem = float(house.dem_votes.sum() / two_party)
    return dem if white_house_party == "DEMOCRAT" else 1 - dem
