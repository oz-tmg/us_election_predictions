"""Small, pre-specified incumbent-party regressions; midterm cross-checks only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .national_environment import NationalEnvironment
from .presidential import OLSModel

SPECIFICATIONS = {
    "income": ["income_growth", "president_on_ballot", "consecutive_terms"],
    "unemployment_alternative": ["unemployment_change", "president_on_ballot", "consecutive_terms"],
    "inflation_alternative": ["inflation", "president_on_ballot", "consecutive_terms"],
}


def _fit(frame: pd.DataFrame, features: list[str]) -> OLSModel:
    return OLSModel(features=features).fit(frame.assign(two_party_dem_share=frame.incumbent_share))


def evaluate(panel: pd.DataFrame, *, min_training_cycles: int = 6) -> dict:
    reports = {}
    for name, features in SPECIFICATIONS.items():
        usable = panel.dropna(subset=[*features, "incumbent_share"]).sort_values("cycle")
        predictions = []
        for row in usable.to_dict(orient="records"):
            train = usable[usable.cycle < row["cycle"]]
            if len(train) < max(min_training_cycles, len(features) + 2):
                continue
            test = pd.DataFrame([row])
            model = _fit(train, features)
            mean = float(model.predict(test)[0])
            last = train.iloc[-1]
            last_dem = (
                last.incumbent_share if last.white_house_party == "DEMOCRAT" else 1 - last.incumbent_share
            )
            persistence = last_dem if row["white_house_party"] == "DEMOCRAT" else 1 - last_dem
            midterm = float(_fit(train, ["midterm"]).predict(test)[0])
            predictions.append(
                {
                    "cycle": int(row["cycle"]),
                    "train_through": int(train.cycle.max()),
                    "data_vintage": row["data_vintage"],
                    "actual": float(row["incumbent_share"]),
                    "prediction": mean,
                    "sigma": float(model.resid_sigma_),
                    "persistence": float(persistence),
                    "midterm_only": midterm,
                }
            )
        pred = pd.DataFrame(predictions)
        metrics = {}
        if not pred.empty:
            for field in ("prediction", "persistence", "midterm_only"):
                metrics[f"{field}_mae"] = float((pred[field] - pred.actual).abs().mean())
            metrics["coverage_90"] = float(
                ((pred.prediction - pred.actual).abs() <= 1.644854 * pred.sigma).mean()
            )
            metrics["out_of_sample_rmse"] = float(np.sqrt(((pred.prediction - pred.actual) ** 2).mean()))
        reports[name] = {
            "features": features,
            "n_cycles_with_vintages": len(usable),
            "n_held_out_cycles": len(pred),
            "metrics": metrics,
            "predictions": predictions,
            "promotion_eligible": bool(
                len(pred) >= 8
                and metrics["coverage_90"] >= 0.85
                and metrics["prediction_mae"] < min(metrics["persistence_mae"], metrics["midterm_only_mae"])
            ),
        }
    return reports


def estimate(panel: pd.DataFrame, live: pd.DataFrame, evaluation: dict) -> NationalEnvironment:
    features = SPECIFICATIONS["income"]
    usable = panel.dropna(subset=[*features, "incumbent_share"])
    if len(usable) < 6 or live.empty or live[features].isna().any().any():
        return NationalEnvironment(
            estimator="fundamentals",
            status="unavailable",
            national_dem_share=None,
            band=None,
            identified=False,
            caveats=["Insufficient actual historical vintages or current income observation"],
            provenance={"n_cycles": len(usable)},
        )
    fitted = _fit(usable, features)
    incumbent = float(fitted.predict(live)[0])
    dem = incumbent if live.white_house_party.iloc[0] == "DEMOCRAT" else 1 - incumbent
    check = evaluation["income"]
    sigma = max(float(check["metrics"].get("out_of_sample_rmse", fitted.resid_sigma_)), fitted.resid_sigma_)
    return NationalEnvironment(
        estimator="fundamentals",
        status="point",
        national_dem_share=float(np.clip(dem, 0.01, 0.99)),
        band=None,
        identified=False,
        assumptions=["Pre-specified income growth + incumbent president on ballot + consecutive terms"],
        caveats=[
            "Midterm cross-check only; never precision-blended with specials or polls",
            "Target is all-race two-party House vote, not the contested total-vote-weighted model input",
            "Few cycles/incomplete vintage archive; alternatives reported separately",
        ],
        provenance={
            "source_id": "fred_bea_income_vintages",
            "data_vintage": live.data_vintage.iloc[0],
            "share_std_error": sigma,
            "n_cycles": len(usable),
            "features": features,
            "fit_parameters": fitted.coef_.tolist() if fitted.coef_ is not None else None,
            "promotion_eligible": False,
            "historical_gate_passed": check["promotion_eligible"],
        },
    )
