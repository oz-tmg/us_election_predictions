"""Presidential fundamentals baseline (P1-001).

A transparent, polls-free baseline for state two-party Democratic vote share, built
on the predictors that "should be hard to beat" (CLAUDE.md §2 rule 5): the previous
cycle's state result and the national environment, optionally demographics. Fit by
ordinary least squares (numpy — no heavy deps).

The model separates *expected vote* from *win probability* (CLAUDE.md §7): it returns a
mean prediction plus a residual standard deviation, which the correlated simulation
layer turns into win probabilities. Evaluation is leave-one-cycle-out backtesting with
MAE on vote share (calibration/Brier live in evaluation.forecast_eval).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_FEATURES = ["lag_dem_share", "national_dem_share"]


@dataclass
class OLSModel:
    """Minimal OLS with intercept, fit via least squares."""

    features: list[str]
    coef_: np.ndarray | None = None
    resid_sigma_: float = float("nan")
    _cols: list[str] = field(default_factory=list)

    def fit(self, df: pd.DataFrame, target: str = "two_party_dem_share") -> OLSModel:
        d = df.dropna(subset=self.features + [target])
        X = self._design(d)
        y = d[target].to_numpy(dtype=float)
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        self.coef_ = coef
        resid = y - X @ coef
        # unbiased residual sd (guard small samples)
        dof = max(len(y) - X.shape[1], 1)
        self.resid_sigma_ = float(np.sqrt((resid @ resid) / dof))
        return self

    def _design(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self.features].to_numpy(dtype=float)
        return np.column_stack([np.ones(len(df)), X])

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("model not fit")
        return np.clip(self._design(df) @ self.coef_, 0.0, 1.0)


def backtest_leave_one_cycle_out(
    panel: pd.DataFrame,
    features: list[str] | None = None,
    target: str = "two_party_dem_share",
) -> tuple[pd.DataFrame, dict]:
    """Leave-one-cycle-out backtest. Returns (predictions, metrics).

    For each cycle with a usable lag, train on all *other* cycles and predict it.
    """
    features = features or DEFAULT_FEATURES
    usable = panel.dropna(subset=features + [target]).copy()
    preds = []
    for cycle in sorted(usable["cycle"].unique()):
        train = usable[usable["cycle"] != cycle]
        test = usable[usable["cycle"] == cycle]
        if len(train) < len(features) + 2 or test.empty:
            continue
        model = OLSModel(features=list(features)).fit(train, target)
        p = test.copy()
        p["pred_dem_share"] = model.predict(test)
        p["resid_sigma"] = model.resid_sigma_
        p["error"] = p["pred_dem_share"] - p[target]
        preds.append(p)

    if not preds:
        return pd.DataFrame(), {"n": 0, "mae": float("nan")}

    out = pd.concat(preds, ignore_index=True)
    # naive baseline: predict the lag directly (persistence)
    naive_mae = (
        float((out["lag_dem_share"] - out[target]).abs().mean()) if "lag_dem_share" in out else float("nan")
    )
    metrics = {
        "n": int(len(out)),
        "mae": float(out["error"].abs().mean()),
        "rmse": float(np.sqrt((out["error"] ** 2).mean())),
        "naive_persistence_mae": naive_mae,
        "winner_accuracy": float(((out["pred_dem_share"] > 0.5) == (out[target] > 0.5)).mean()),
        "features": list(features),
    }
    return out, metrics


def fit_full(panel: pd.DataFrame, features: list[str] | None = None) -> OLSModel:
    """Fit on all usable rows (for forward forecasting / simulation inputs)."""
    features = features or DEFAULT_FEATURES
    return OLSModel(features=list(features)).fit(panel)
