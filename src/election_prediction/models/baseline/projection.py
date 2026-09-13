"""Forward projection of a live cycle from fitted baselines (House and Senate, 2026).

Everything else in the baseline stack is retrospective: it fits and scores on cycles whose
results are known. This module runs the same fitted models *forward* onto a cycle that has
not happened, which needs three inputs the backtest gets for free:

* **The seat roster** — from ``race_universe_<cycle>.parquet`` (P0-001), not from returns.
* **The national environment** — the backtest conditions on the true contemporaneous
  value, which a live cycle does not have. For 2026 it comes from special-election
  overperformance (``data/special_elections.implied_national_dem_share``), and it is the
  single largest source of error in the projection: the House model's coefficient on
  ``national_dem_share`` is +0.884, so a 1-point error in the national call moves nearly
  every district by 0.9 points.
* **Incumbency** — from the seat roster's ``incumbent_party``, under the assumption that
  the sitting member both runs and is renominated. ``features.filings`` now verifies the
  first half of that from FEC filings (``incumbent_status = "filed"``); the second half is
  still unverified, because renomination needs primary results and FEC does not publish
  them. Projections therefore keep ``incumbency_assumed`` so a consumer cannot mistake the
  assumption for a finding, and ``filings_summary`` reports how much of the roster the
  filing evidence covers.

The Senate model takes **no national-environment feature** (its terms are state
presidential lean, incumbency, and the midterm penalty), so the specials estimate does not
reach it through the model. Applying it there requires an explicit uniform-swing scenario,
which ``project_senate`` exposes as ``uniform_swing`` rather than smuggling in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .house import DEFAULT_SIGMA, NON_VOTING_JURISDICTIONS, OLSModel

PROJECTION_COLUMNS = [
    "geography_id",
    "state_po",
    "district_num",
    "office",
    "mean_dem_share",
    "sigma",
    "source",
    "incumbent_party",
    "incumbency_assumed",
]


# P0-003 replaced the hand-kept ``INCUMBENT_PARTY_OVERRIDES`` table that used to live here.
# The one entry it held -- Cynthia Lummis, labelled OTHER in the 2026 roster because
# Wyoming's 2020 Senate returns carry a null party for every candidate -- is now resolved
# from the FEC roster, which records her as ``REP``. Any seat whose party the returns cannot
# supply is filled the same way, so the table has nothing left to hold.
#
# ``filings.resolve_incumbent_status`` writes this column from
# ``filings.resolved_incumbent_party``; ``_incumbency_terms`` prefers it when present and
# falls back to the raw ``incumbent_party`` otherwise, so a projection still runs before
# the FEC layer is built. The producer and this constant must agree on the name --
# ``test_filings`` pins that, because a silent mismatch would leave the fallback running
# forever while every unit test still passed.
RESOLVED_PARTY_COLUMN = "incumbent_party_resolved"

# Senators elected as independents who caucus with the Democrats. Two-party vote share
# cannot see them -- Sanders's 2024 race records a Democratic share of 0.000 and King's
# 0.238 -- so counting Senate control from returns alone hands both seats to Republicans
# and understates Democratic holdovers by two.
INDEPENDENT_DEM_CAUCUS = frozenset({("ME", 2024), ("VT", 2024)})


def _incumbency_terms(universe: pd.DataFrame) -> pd.DataFrame:
    out = universe.copy()
    party = out["incumbent_party"].fillna("").astype(str).str.upper()
    if RESOLVED_PARTY_COLUMN in out.columns:
        # A resolved label only ever *fills* a gap -- it never overwrites a party the
        # returns already state -- so preferring it cannot silently reclassify a seat.
        resolved = out[RESOLVED_PARTY_COLUMN].fillna("").astype(str).str.upper()
        party = party.where(party.isin(["DEMOCRAT", "REPUBLICAN"]), resolved)
    # An open seat is one with no identified incumbent; both indicators go to zero, which
    # is exactly how the fitted models encode it.
    out["incumbent_dem"] = (party == "DEMOCRAT").astype(float)
    out["incumbent_rep"] = (party == "REPUBLICAN").astype(float)
    return out


def project_house(
    universe: pd.DataFrame,
    model: OLSModel,
    *,
    national_dem_share: float,
    lagged_national_dem_share: float,
    resid_sigma: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Project every 2026 House seat from its 2024 result and a national environment.

    ``lagged_national_dem_share`` is the national share the *prior* cycle's district
    results are measured against, matching how ``district_lean`` is constructed in
    training — the lean must not contain information from the cycle being predicted.
    """
    seats = universe[
        (universe["office"] == "us_house") & (~universe["state_po"].isin(NON_VOTING_JURISDICTIONS))
    ].copy()
    seats = _incumbency_terms(seats)

    seats["lag_dem_share"] = pd.to_numeric(seats["prior_dem_share"], errors="coerce")
    seats["district_lean"] = seats["lag_dem_share"] - lagged_national_dem_share
    seats["national_dem_share"] = float(national_dem_share)

    usable = seats["district_lean"].notna()
    seats.loc[usable, "mean_dem_share"] = model.predict(seats[usable])
    seats["source"] = np.where(usable, "model", "no_prior_result")

    sigma = float(resid_sigma) if resid_sigma else DEFAULT_SIGMA
    seats["sigma"] = sigma
    seats["incumbency_assumed"] = True
    out = seats.dropna(subset=["mean_dem_share"]).reindex(columns=PROJECTION_COLUMNS).reset_index(drop=True)

    coverage = {
        "seats_projected": int(len(out)),
        "seats_in_roster": int(len(seats)),
        "seats_without_prior": int((~usable).sum()),
        "national_dem_share": float(national_dem_share),
        "resid_sigma": sigma,
        "incumbency_verified": False,
    }
    return out, coverage


def project_senate(
    universe: pd.DataFrame,
    model: OLSModel,
    pres_reference: pd.DataFrame,
    *,
    midterm_penalty: float,
    resid_sigma: float | None = None,
    uniform_swing: float = 0.0,
) -> tuple[pd.DataFrame, dict]:
    """Project the Senate seats on the ballot from state presidential lean and incumbency.

    ``pres_reference`` supplies ``state_pres_lean`` per state from the most recent
    presidential cycle. ``midterm_penalty`` is +1 when a Republican holds the White House
    and -1 when a Democrat does, matching the fitted sign convention.

    ``uniform_swing`` is a **scenario** knob in two-party share points, added after
    prediction. The Senate model has no national-environment term, so this is the only way
    a specials-derived environment can reach it, and keeping it separate from the model
    prediction is deliberate: it is an assumption laid on top, not an estimate.
    """
    seats = universe[universe["office"] == "us_senate"].copy()
    seats = _incumbency_terms(seats)
    seats = seats.merge(pres_reference[["state_po", "state_pres_lean"]], on="state_po", how="left")
    seats["midterm_penalty"] = float(midterm_penalty)

    usable = seats["state_pres_lean"].notna()
    seats.loc[usable, "mean_dem_share"] = model.predict(seats[usable])
    seats["mean_dem_share"] = seats["mean_dem_share"] + float(uniform_swing)
    seats["source"] = np.where(usable, "model", "no_pres_reference")

    sigma = float(resid_sigma) if resid_sigma else DEFAULT_SIGMA
    seats["sigma"] = sigma
    seats["incumbency_assumed"] = True
    seats["district_num"] = np.nan
    out = seats.dropna(subset=["mean_dem_share"]).reindex(columns=PROJECTION_COLUMNS).reset_index(drop=True)

    coverage = {
        "seats_projected": int(len(out)),
        "seats_in_roster": int(len(seats)),
        "midterm_penalty": float(midterm_penalty),
        "uniform_swing": float(uniform_swing),
        "resid_sigma": sigma,
        "incumbency_verified": False,
    }
    return out, coverage
