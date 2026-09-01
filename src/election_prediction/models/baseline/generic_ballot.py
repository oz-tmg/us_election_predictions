"""National environment to district swing (P1-004).

The backlog question is "how should the national environment affect districts?", and
the acceptance criterion is a *historical relationship, estimated and documented*. That
relationship is estimable entirely from certified returns: regress each district's
cycle-over-cycle swing on the national House swing.

    district_swing = alpha + beta * national_swing + e

``beta`` is the **swing ratio**. Uniform national swing — the textbook assumption that
a 1-point national move shifts every district by 1 point — is the null hypothesis
beta = 1. ``e``'s standard deviation is the district-specific swing that no national
signal explains, and it is what a seat simulation needs in order not to be overconfident.

**Why this needs no polling data, and what the generic ballot is actually for.** A
generic-ballot poll is a *forecast of next cycle's national swing*; it is an input to
this relationship, not part of estimating it. Separating the two means the adjustment is
built from Tier 0 certified returns with no redistribution question attached, and a poll
average can be plugged in later through the existing P2 layer via
:func:`apply_national_swing`. Until governed poll toplines are registered
(``docs/dataset-registry.md``), the national swing must be supplied explicitly by the
caller rather than silently defaulted.

Two exclusions keep the estimate honest (CLAUDE.md §6):

* **Redistricting.** A district number does not refer to the same territory across a
  redraw, so swings are computed only within a plan era.
* **Uncontested races.** A seat going from unopposed to contested produces an enormous
  fake swing that has nothing to do with the national environment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ...features.incumbency import plan_era

SWING_PANEL_COLUMNS = [
    "geography_id",
    "state_po",
    "district_num",
    "cycle",
    "plan_era",
    "two_party_dem_share",
    "lag_dem_share",
    "district_swing",
    "national_dem_share",
    "national_swing",
]


def build_swing_panel(race_table: pd.DataFrame, *, exclude_uncontested: bool = True) -> pd.DataFrame:
    """District x cycle swings, paired with the national House swing for that cycle."""
    house = race_table[race_table["office"] == "us_house"].dropna(subset=["two_party_dem_share"]).copy()
    if exclude_uncontested and "uncontested_flag" in house.columns:
        house = house[~house["uncontested_flag"].fillna(False)]

    national = (
        house.groupby("cycle")
        .apply(
            lambda g: (g["two_party_dem_share"] * g["total_votes"]).sum() / g["total_votes"].sum(),
            include_groups=False,
        )
        .rename("national_dem_share")
    )
    house = house.merge(national, on="cycle", how="left")
    house["national_swing"] = house["cycle"].map(national.diff())
    house["plan_era"] = house["cycle"].map(plan_era)

    house = house.sort_values(["geography_id", "cycle"])
    grp = house.groupby(["geography_id", "plan_era"])
    house["lag_dem_share"] = grp["two_party_dem_share"].shift(1)
    house["prev_cycle"] = grp["cycle"].shift(1)
    # Only consecutive cycles within one plan era form a valid swing.
    consecutive = house["cycle"] - house["prev_cycle"] == 2
    house = house[consecutive & house["lag_dem_share"].notna()]
    house["district_swing"] = house["two_party_dem_share"] - house["lag_dem_share"]

    return house.reindex(columns=SWING_PANEL_COLUMNS).reset_index(drop=True)


def estimate_swing_ratio(panel: pd.DataFrame) -> dict:
    """Fit district_swing ~ national_swing and describe the fitted relationship."""
    d = panel.dropna(subset=["district_swing", "national_swing"])
    if len(d) < 3:
        return {"status": "insufficient_data", "n": int(len(d))}

    # The slope is only identified if the national swing actually varies. A plan era
    # holding a single cycle of swings gives every district the same national swing,
    # which is collinear with the intercept: least squares still returns a number, but
    # it is arbitrary. This matters most for the newest era, which is the one a live
    # forecast would reach for.
    if d["national_swing"].nunique() < 2:
        return {
            "status": "unidentified",
            "reason": "national swing does not vary — needs at least two cycles of swings",
            "n": int(len(d)),
            "cycles": sorted(int(c) for c in d["cycle"].unique()),
        }

    x = d["national_swing"].to_numpy(dtype=float)
    y = d["district_swing"].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = max(len(y) - 2, 1)
    ss_tot = float(((y - y.mean()) ** 2).sum())

    return {
        "status": "ok",
        "n": int(len(d)),
        "cycles": sorted(int(c) for c in d["cycle"].unique()),
        "intercept": float(coef[0]),
        "swing_ratio": float(coef[1]),
        "residual_sigma": float(np.sqrt((resid @ resid) / dof)),
        "r_squared": float(1 - (resid @ resid) / ss_tot) if ss_tot > 0 else float("nan"),
        # Uniform swing is the classic assumption; report how far the data sits from it.
        "uniform_swing_null": 1.0,
        "deviation_from_uniform": float(coef[1] - 1.0),
    }


def estimate_by_plan_era(panel: pd.DataFrame) -> pd.DataFrame:
    """Swing ratio per redistricting era — the relationship is not assumed stable."""
    rows = []
    for era, g in panel.groupby("plan_era"):
        est = estimate_swing_ratio(g)
        rows.append(
            {
                "plan_era": int(era),
                "n": est.get("n", 0),
                "status": est["status"],
                # An unidentified era reports no ratio rather than an arbitrary one.
                "swing_ratio": est.get("swing_ratio", float("nan")),
                "residual_sigma": est.get("residual_sigma", float("nan")),
                "r_squared": est.get("r_squared", float("nan")),
            }
        )
    return pd.DataFrame(rows)


def apply_national_swing(
    district_baseline: pd.DataFrame,
    *,
    national_swing: float,
    swing_ratio: float,
    baseline_column: str = "two_party_dem_share",
) -> pd.DataFrame:
    """Shift district baselines by an expected national swing.

    ``national_swing`` is the caller's expectation for the coming cycle — from a
    governed generic-ballot average once one is registered, or from an explicit
    scenario. It is a required argument precisely so that no forecast can quietly
    assume a national environment nobody chose.
    """
    out = district_baseline.copy()
    out["national_swing_applied"] = national_swing
    out["swing_ratio_applied"] = swing_ratio
    out["adjusted_dem_share"] = (out[baseline_column] + swing_ratio * national_swing).clip(0.0, 1.0)
    return out
