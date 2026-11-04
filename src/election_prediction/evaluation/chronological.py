"""Expanding-window benchmarks with an estimated, rather than realised, national input."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..models.baseline.presidential import OLSModel
from . import forecast_eval


def national_history_forecast(history: pd.DataFrame, *, cycle: int, penalty: float = 0.0) -> float:
    """Persistence plus the mean earlier national swing for the same midterm sign.

    Each cycle receives one observation regardless of its number of district rows.
    This is a benchmark; it is not a replacement for the live specials band.
    """
    past = history[history["cycle"] < cycle].sort_values("cycle")
    national = past.groupby("cycle")["national_dem_share"].first().sort_index()
    if national.empty:
        raise ValueError("no earlier national environment")
    if "midterm_penalty" not in past or penalty == 0:
        return float(national.iloc[-1])
    signs = past.groupby("cycle")["midterm_penalty"].first()
    shifts = national.diff().loc[signs[signs == penalty].index].dropna()
    return float(np.clip(national.iloc[-1] + (shifts.mean() if len(shifts) else 0.0), 0, 1))


def backtest(
    panel: pd.DataFrame,
    *,
    features: list[str],
    naive_feature: str,
    min_training_cycles: int = 4,
) -> tuple[pd.DataFrame, dict]:
    """Every fitted parameter and national estimate uses only earlier cycles.

    Demographics are deliberately excluded until historical release vintages exist.
    Callers must provide lagged presidential references for Senate races. Candidate
    availability is reconstructed from historical ballots, not archived pre-election
    rosters; this remaining limitation is stated in the output.
    """
    if any(f in features for f in ("college_share", "median_household_income", "median_age")):
        raise ValueError("chronological evaluation requires release-vintaged demographic features")
    usable = panel.dropna(subset=[*features, "two_party_dem_share", naive_feature]).copy()
    if "uncontested_flag" in usable:
        usable = usable[~usable["uncontested_flag"].fillna(False)]
    # A minor-party opponent can make n_candidates > 1 without both major parties running.
    usable = usable[usable["two_party_dem_share"].between(0, 1, inclusive="neither")]
    predictions = []
    national_errors: list[float] = []
    for cycle in sorted(usable["cycle"].unique()):
        train = usable[usable["cycle"] < cycle]
        test = usable[usable["cycle"] == cycle].copy()
        if train["cycle"].nunique() < min_training_cycles or len(train) < len(features) + 2:
            continue
        model = OLSModel(features).fit(train)
        national_sigma = 0.0
        if "national_dem_share" in features:
            actual_national = float(test["national_dem_share"].iloc[0])
            penalty = float(test["midterm_penalty"].iloc[0]) if "midterm_penalty" in test else 0.0
            estimate = national_history_forecast(panel, cycle=int(cycle), penalty=penalty)
            test["national_dem_share"] = estimate
            if len(national_errors) >= 3:
                national_sigma = float(np.std(national_errors, ddof=1))
            national_errors.append(estimate - actual_national)
        beta = 0.0
        if "national_dem_share" in features and model.coef_ is not None:
            beta = float(model.coef_[1 + features.index("national_dem_share")])
        test["pred_dem_share"] = model.predict(test)
        test["resid_sigma"] = math.hypot(model.resid_sigma_, beta * national_sigma)
        test["error"] = test["pred_dem_share"] - test["two_party_dem_share"]
        test["train_through"] = int(train["cycle"].max())
        predictions.append(test)
    if not predictions:
        return pd.DataFrame(), {"n": 0, "status": "insufficient_history"}
    out = pd.concat(predictions, ignore_index=True)
    by_cycle = []
    for cycle, group in out.groupby("cycle"):
        by_cycle.append(
            {
                "cycle": int(cycle),
                **forecast_eval.evaluate_backtest(group),
                "naive_mae": float((group[naive_feature] - group["two_party_dem_share"]).abs().mean()),
            }
        )
    return out, {
        "status": "evaluated",
        "training": "expanding window; train_cycle < predicted_cycle",
        "national_environment": "earlier-cycle persistence plus historical midterm penalty",
        "demographics": "excluded: historical release vintages unavailable",
        "candidate_availability": "reconstructed from historical ballots; not an archived as-of roster",
        "one_sided_major_party_outcomes": "excluded even if a minor-party opponent made the race contested",
        "n": len(out),
        "n_cycles": len(by_cycle),
        "features": features,
        "metrics": forecast_eval.evaluate_backtest(out),
        "naive_mae": float((out[naive_feature] - out["two_party_dem_share"]).abs().mean()),
        "by_cycle": by_cycle,
    }


def lag_senate_presidential_reference(
    senate_panel: pd.DataFrame, presidential_panel: pd.DataFrame
) -> pd.DataFrame:
    """Same-year presidential results are unavailable before a Senate general election."""
    out = senate_panel.drop(
        columns=["state_pres_lean", "pres_dem_share_state", "national_pres_dem_share"], errors="ignore"
    )
    pres = presidential_panel[["cycle", "state_po", "two_party_dem_share", "national_dem_share"]].rename(
        columns={
            "cycle": "pres_reference_cycle",
            "two_party_dem_share": "pres_dem_share_state",
            "national_dem_share": "national_pres_dem_share",
        }
    )
    out = pd.merge_asof(
        out.sort_values("cycle"),
        pres.sort_values("pres_reference_cycle"),
        left_on="cycle",
        right_on="pres_reference_cycle",
        by="state_po",
        direction="backward",
        allow_exact_matches=False,
    )
    out["state_pres_lean"] = out["pres_dem_share_state"] - out["national_pres_dem_share"]
    return out
