"""Complete-House chronological diagnostics, explicitly distinct from a real-time replay."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..models import error_structure, simulation
from ..models.baseline import house
from ..models.baseline.presidential import OLSModel
from .chronological import national_history_forecast


def house_predictions(
    panel: pd.DataFrame,
    presidential: pd.DataFrame,
    races: pd.DataFrame,
    *,
    canonical_winners: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """Use available district lags, lagged state presidential fallbacks and the entire chamber.

    Ballot availability is reconstructed from final returns, not archived pre-election
    ballots. Missing or duplicate districts invalidate a cycle; never fabricate outcomes.
    """
    outputs, omitted = [], []
    national_errors: list[float] = []
    universe = races[races.office.eq("us_house") & ~races.state_po.isin(house.NON_VOTING_JURISDICTIONS)]
    for cycle, actual in universe.groupby("cycle", sort=True):
        if len(actual) != 435 or actual.geography_id.nunique() != 435:
            omitted.append(
                {
                    "cycle": int(cycle),
                    "reason": "not exactly 435 unique voting districts",
                    "n_rows": len(actual),
                    "n_unique": actual.geography_id.nunique(),
                }
            )
            continue
        actual = actual.copy()
        if canonical_winners is not None:
            if canonical_winners.race_id.duplicated().any():
                raise ValueError("canonical winners must be unique by race")
            mapping = canonical_winners.set_index("race_id").ballot_party
            actual["winner_party"] = actual.race_id.map(mapping)
        if not actual.winner_party.isin(["DEMOCRAT", "REPUBLICAN"]).all():
            omitted.append(
                {"cycle": int(cycle), "reason": "non-major-party winner needs historical caucus facts"}
            )
            continue
        columns = ["race_id", "geography_id", "state_po", "cycle", "two_party_dem_share"]
        features = ["race_id", *house.DEFAULT_FEATURES, "lag_dem_share", "midterm_penalty"]
        test = actual[columns].merge(
            panel.loc[panel.cycle.eq(cycle), features], on="race_id", how="left", validate="one_to_one"
        )
        train = panel[
            panel.cycle.lt(cycle)
            & ~panel.uncontested_flag
            & panel.two_party_dem_share.between(0, 1, inclusive="neither")
        ]
        train = train.dropna(subset=[*house.DEFAULT_FEATURES, "two_party_dem_share"])
        if train.cycle.nunique() < 4:
            continue
        fitted = OLSModel(house.DEFAULT_FEATURES).fit(train)
        national = national_history_forecast(
            panel, cycle=int(cycle), penalty=float(test.midterm_penalty.dropna().iloc[0])
        )
        true_national = float(test.national_dem_share.dropna().iloc[0])
        national_sigma = float(np.std(national_errors, ddof=1)) if len(national_errors) >= 3 else 0.03
        test["national_dem_share"] = national
        test["pred_dem_share"] = np.nan
        test["prediction_source"] = "lagged_state_presidential_fallback"
        ready = test[house.DEFAULT_FEATURES].notna().all(axis=1)
        test.loc[ready, "pred_dem_share"] = fitted.predict(test.loc[ready])
        test.loc[ready, "prediction_source"] = "district_model"
        past_pres = (
            presidential[presidential.cycle.lt(cycle)].sort_values("cycle").groupby("state_po").tail(1)
        )
        lean = past_pres.two_party_dem_share - past_pres.national_dem_share
        fallback = past_pres.assign(lean=lean).set_index("state_po").lean
        test["pred_dem_share"] = test.pred_dem_share.fillna(national + test.state_po.map(fallback)).clip(0, 1)
        assert fitted.coef_ is not None
        beta = float(fitted.coef_[1 + house.DEFAULT_FEATURES.index("national_dem_share")])
        test["resid_sigma"] = math.hypot(float(fitted.resid_sigma_), abs(beta) * national_sigma)
        test.loc[~ready, "resid_sigma"] *= house.FALLBACK_SIGMA_MULTIPLIER
        one_sided = test.two_party_dem_share.isin([0.0, 1.0])
        test.loc[one_sided, "pred_dem_share"] = test.loc[one_sided, "two_party_dem_share"]
        test.loc[one_sided, "resid_sigma"] = 0.0
        test.loc[one_sided, "prediction_source"] = "reconstructed_one_sided_ballot"
        if test.pred_dem_share.isna().any():
            omitted.append({"cycle": int(cycle), "reason": "missing lagged fallback"})
            continue
        winners = actual.set_index("race_id").winner_party.eq("DEMOCRAT")
        test["actual_dem_win"] = test.race_id.map(winners)
        if test.actual_dem_win.isna().any():
            raise ValueError("complete-chamber outcomes must join one-to-one")
        test["train_through"] = int(train.cycle.max())
        test["error"] = test.pred_dem_share - test.two_party_dem_share
        outputs.append(test)
        national_errors.append(national - true_national)
    return (pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()), omitted


def evaluate(predictions: pd.DataFrame, omitted: list[dict]) -> dict:
    """Report interval coverage and chamber-control scores for asserted/earlier-fitted splits."""
    folds = []
    for cycle, group in predictions.groupby("cycle", sort=True):
        if len(group) != 435 or group.geography_id.nunique() != 435:
            raise ValueError("chamber diagnostic refuses a partial or duplicate House")
        fitted = error_structure.estimate(predictions[predictions.cycle.lt(cycle)])
        if fitted["status"] != "estimated":
            continue
        fold = {
            "cycle": int(cycle),
            "n_seats": 435,
            "prediction_sources": group.prediction_source.value_counts().to_dict(),
            "correlation_train_through": int(predictions.loc[predictions.cycle.lt(cycle), "cycle"].max()),
        }
        for name, params in [
            ("asserted", simulation.CorrelationParams()),
            ("estimated", simulation.CorrelationParams(**fitted["parameters"])),
        ]:
            result = error_structure._seat_interval(group, params)
            fold[name] = result
        folds.append(fold)
    summary = {}
    for name in ("asserted", "estimated"):
        summary[name] = {
            key: float(np.mean([f[name][field] for f in folds])) if folds else None
            for key, field in [
                ("coverage_90", "covered"),
                ("mean_interval_score", "interval_score"),
                ("control_brier", "control_brier"),
                ("control_log_loss", "control_log_loss"),
            ]
        }
    return {
        "evaluation_universe": "435 unique voting House districts per retained cycle",
        "folds": folds,
        "summary": summary,
        "omitted_cycles": omitted,
        "senate_status": "blocked: no governed historical 100-seat class/holdover/caucus roster",
        "promoted": False,
        "reason": "Retrospective ballots/missing map vintages prevent live promotion",
    }
