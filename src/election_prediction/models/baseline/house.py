"""House district fundamentals baseline and seat universe (P1-002 forecast layer).

P1-002 produced a district *partisanship score* — a descriptive lean. This turns that
into a forecasting model: predict each district's two-party Democratic share from its
lagged lean, the national environment, and incumbency, then hand a complete chamber to
the correlated simulation layer.

Three things this module is careful about, each of which was wrong or missing when the
seat simulation ran off the raw partisanship score:

* **The chamber has 435 seats, not every district number that ever existed.** Averaging
  a district's lean over 1976-2024 produces one row per historical district *number*,
  and states have gained and lost seats throughout, so the score table holds 505 rows.
  Simulating 505 seats and reporting a majority probability from it is meaningless. The
  seat universe is therefore built from a single cycle within one redistricting era.
* **A quarantined or uncontested district still holds a seat.** Dropping races that fail
  reconciliation is right for *estimation* but wrong for *seat counting* — 27 of 2024's
  435 districts are quarantined, and silently simulating a 408-seat House would understate
  uncertainty and misstate control. Districts without a usable model prediction fall back
  to their partisanship prior with widened uncertainty and are reported as fallbacks,
  never dropped.
* **Uncontested races are excluded from training, not from the chamber.** A 100-0 race
  carries no information about the vote-share relationship and would badly bias the
  coefficients, but the seat is real and near-certainly held (CLAUDE.md §6).

**Backtest interpretation.** ``national_dem_share`` is contemporaneous, so the backtest
conditions on the true national environment and answers "given a correct national call,
how well are districts predicted?" — not "how well is the House predicted?". That split
is deliberate: forecasting the national environment is P1-004's job, and its estimated
swing ratio and residual are what carry that uncertainty. The same convention is already
used by the presidential baseline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ...features.incumbency import build_incumbency, plan_era
from .presidential import OLSModel, backtest_leave_one_cycle_out

HOUSE_PANEL_COLUMNS = [
    "race_id",
    "geography_id",
    "cycle",
    "plan_era",
    "state_po",
    "district_num",
    "two_party_dem_share",
    "lag_dem_share",
    "district_lean",
    "national_dem_share",
    "incumbent_dem",
    "incumbent_rep",
    "open_seat",
    "midterm_penalty",
    "uncontested_flag",
]

DEFAULT_FEATURES = [
    "district_lean",
    "national_dem_share",
    "incumbent_dem",
    "incumbent_rep",
]

NAIVE_FEATURE = "lag_dem_share"

# How much wider a fallback district's uncertainty is than a modelled one. A district
# carried on its prior alone is genuinely less well known; 2x is a deliberately blunt,
# documented choice rather than an estimated quantity.
FALLBACK_SIGMA_MULTIPLIER = 2.0

# Jurisdictions that elect a non-voting Delegate or Resident Commissioner rather than a
# voting Representative. MEDSL includes them in the House returns (DC's delegate race
# appears in 2024), so counting them would put 436 seats in a 435-seat chamber and let a
# non-voting member move a majority probability.
NON_VOTING_JURISDICTIONS = frozenset({"DC", "PR", "AS", "GU", "MP", "VI"})

# Voting members of the U.S. House, fixed by statute since 1913.
VOTING_SEATS = 435

# Fallback district-level uncertainty when no model residual is available at all.
DEFAULT_SIGMA = 0.05


def _national_by_cycle(house: pd.DataFrame) -> pd.Series:
    """Vote-weighted national two-party Dem share of contested House races per cycle."""
    contested = house[~house["uncontested_flag"].fillna(False)]
    return (
        contested.groupby("cycle")
        .apply(
            lambda g: (g["two_party_dem_share"] * g["total_votes"]).sum() / g["total_votes"].sum(),
            include_groups=False,
        )
        .rename("national_dem_share")
    )


def build_house_panel(race_table: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """District x cycle panel: lagged lean, national environment, and incumbency."""
    house = race_table[race_table["office"] == "us_house"].dropna(subset=["two_party_dem_share"]).copy()
    house["plan_era"] = house["cycle"].map(plan_era)

    national = _national_by_cycle(house)
    house = house.merge(national, on="cycle", how="left")

    # Lag only within a plan era and only across consecutive cycles: a district number
    # does not survive a redraw.
    house = house.sort_values(["geography_id", "cycle"])
    grp = house.groupby(["geography_id", "plan_era"])
    house["lag_dem_share"] = grp["two_party_dem_share"].shift(1)
    house["prev_cycle"] = grp["cycle"].shift(1)
    house.loc[house["cycle"] - house["prev_cycle"] != 2, "lag_dem_share"] = np.nan

    # District lean is measured against the *lagged* national environment, so the
    # predictor contains no information from the cycle being predicted.
    lagged_national = house["prev_cycle"].map(national)
    house["district_lean"] = house["lag_dem_share"] - lagged_national

    inc = build_incumbency(returns, "us_house")
    house = house.merge(
        inc[["race_id", "incumbent_running", "incumbent_party", "open_seat"]], on="race_id", how="left"
    )
    running = house["incumbent_running"].fillna(False)
    house["incumbent_dem"] = (running & (house["incumbent_party"] == "DEMOCRAT")).astype(float)
    house["incumbent_rep"] = (running & (house["incumbent_party"] == "REPUBLICAN")).astype(float)
    house["open_seat"] = house["open_seat"].fillna(False).astype(bool)

    # Midterms punish the president's party; sign is toward the out-party, zero otherwise.
    from .senate import _white_house_party

    wh = _white_house_party(race_table)
    midterm = (house["cycle"] % 4 == 2).astype(float)
    wh_at = house["cycle"].map(
        lambda c: wh.reindex(wh.index[wh.index <= c]).iloc[-1] if (wh.index <= c).any() else None
    )
    house["midterm_penalty"] = midterm * wh_at.map({"DEMOCRAT": -1.0, "REPUBLICAN": 1.0}).fillna(0.0)

    return house.reindex(columns=HOUSE_PANEL_COLUMNS).reset_index(drop=True)


def backtest(panel: pd.DataFrame, features: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Leave-one-cycle-out backtest on contested districts only.

    Uncontested races are excluded from fitting and scoring: their share is an artefact
    of having no opponent, not a measurement of district preference.
    """
    contested = panel[~panel["uncontested_flag"].fillna(False)]
    return backtest_leave_one_cycle_out(contested, features or DEFAULT_FEATURES, naive_feature=NAIVE_FEATURE)


def fit_full(panel: pd.DataFrame, features: list[str] | None = None) -> OLSModel:
    contested = panel[~panel["uncontested_flag"].fillna(False)]
    return OLSModel(features=list(features or DEFAULT_FEATURES)).fit(contested)


def build_seat_universe(
    race_table: pd.DataFrame,
    panel: pd.DataFrame,
    predictions: pd.DataFrame,
    *,
    cycle: int,
    partisanship_score: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Every seat contested in ``cycle``, with a mean share and sigma for simulation.

    Returns ``(universe, coverage)``. ``coverage`` records how many seats came from the
    model versus a fallback, so a chamber simulation can never quietly run on a partial
    House.
    """
    era = plan_era(cycle)
    # The full seat roster for this era: every district that appears in any of its cycles,
    # so districts missing from one cycle (quarantined) are still counted as seats.
    era_rows = race_table[
        (race_table["office"] == "us_house")
        & (race_table["cycle"].map(plan_era) == era)
        & (~race_table["state_po"].isin(NON_VOTING_JURISDICTIONS))
    ]
    seats = (
        era_rows[["geography_id", "state_po", "district_num"]]
        .drop_duplicates("geography_id")
        .reset_index(drop=True)
    )

    # There may be no predictions at all — the first cycle of a plan era has no
    # within-era lag, so every seat falls back. That is a valid state, not an error.
    pred_cols = {"geography_id", "pred_dem_share", "resid_sigma"}
    has_preds = pred_cols.issubset(predictions.columns) and len(predictions)
    if has_preds:
        preds = predictions[predictions["cycle"] == cycle][sorted(pred_cols)]
        sigma_model = float(predictions["resid_sigma"].median())
    else:
        preds = pd.DataFrame(columns=sorted(pred_cols))
        sigma_model = DEFAULT_SIGMA
    universe = seats.merge(preds, on="geography_id", how="left")

    # Fallback 1: the district's own partisanship prior, if one exists.
    if partisanship_score is not None and len(partisanship_score):
        prior = partisanship_score[["geography_id", "mean_dem_share"]].rename(
            columns={"mean_dem_share": "prior_dem_share"}
        )
        universe = universe.merge(prior, on="geography_id", how="left")
    else:
        universe["prior_dem_share"] = np.nan

    # Fallback 2: the seat's most recent observed result in this era.
    recent = (
        era_rows.dropna(subset=["two_party_dem_share"])
        .sort_values("cycle")
        .groupby("geography_id")["two_party_dem_share"]
        .last()
        .rename("recent_dem_share")
    )
    universe = universe.merge(recent, on="geography_id", how="left")

    universe["source"] = np.where(
        universe["pred_dem_share"].notna(),
        "model",
        np.where(universe["prior_dem_share"].notna(), "partisanship_prior", "recent_result"),
    )
    universe["mean_dem_share"] = (
        universe["pred_dem_share"].fillna(universe["prior_dem_share"]).fillna(universe["recent_dem_share"])
    )
    universe["sigma"] = np.where(
        universe["source"] == "model",
        universe["resid_sigma"].fillna(sigma_model),
        sigma_model * FALLBACK_SIGMA_MULTIPLIER,
    )
    universe = universe.dropna(subset=["mean_dem_share"]).reset_index(drop=True)

    coverage = {
        "cycle": int(cycle),
        "plan_era": int(era),
        "seats": int(len(universe)),
        "expected_voting_seats": VOTING_SEATS,
        # Surfaced rather than asserted: MEDSL coverage varies by cycle, and a chamber
        # simulation quietly short of 435 seats would misstate control.
        "seats_complete": bool(len(universe) == VOTING_SEATS),
        "by_source": universe["source"].value_counts().to_dict(),
        "model_coverage": (float((universe["source"] == "model").mean()) if len(universe) else float("nan")),
    }
    return universe, coverage
