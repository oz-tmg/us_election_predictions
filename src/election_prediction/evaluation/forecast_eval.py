"""Forecast evaluation (P1-006).

Calibration-first scoring of probabilistic forecasts against realized outcomes
(CLAUDE.md §6 evaluation standards): Brier score and log score for win probabilities,
a binned calibration (reliability) curve, interval coverage for vote-share intervals,
and MAE/RMSE for vote share. Close races should look close and probabilities should be
honest — these metrics are how we check that.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_EPS = 1e-12


def brier_score(prob: np.ndarray, outcome: np.ndarray) -> float:
    prob = np.asarray(prob, float)
    outcome = np.asarray(outcome, float)
    return float(np.mean((prob - outcome) ** 2))


def log_score(prob: np.ndarray, outcome: np.ndarray) -> float:
    """Mean negative log-likelihood (lower is better)."""
    prob = np.clip(np.asarray(prob, float), _EPS, 1 - _EPS)
    outcome = np.asarray(outcome, float)
    return float(-np.mean(outcome * np.log(prob) + (1 - outcome) * np.log(1 - prob)))


def calibration_curve(prob: np.ndarray, outcome: np.ndarray, *, n_bins: int = 10) -> pd.DataFrame:
    """Binned reliability curve: predicted vs observed frequency per probability bin."""
    prob = np.asarray(prob, float)
    outcome = np.asarray(outcome, float)
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(prob, bins) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        rows.append({
            "bin_low": bins[b], "bin_high": bins[b + 1],
            "n": int(m.sum()),
            "mean_pred": float(prob[m].mean()),
            "observed_freq": float(outcome[m].mean()),
        })
    return pd.DataFrame(rows)


def expected_calibration_error(prob: np.ndarray, outcome: np.ndarray, *, n_bins: int = 10) -> float:
    """ECE: sample-weighted mean gap between predicted and observed frequency."""
    cc = calibration_curve(prob, outcome, n_bins=n_bins)
    if cc.empty:
        return float("nan")
    w = cc["n"] / cc["n"].sum()
    return float((w * (cc["mean_pred"] - cc["observed_freq"]).abs()).sum())


def interval_coverage(pred_mean: np.ndarray, sigma: np.ndarray, actual: np.ndarray,
                      *, level: float = 0.90) -> float:
    """Fraction of actual vote shares falling in the predicted central interval."""

    z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600}.get(round(level, 2), 1.6449)
    pred_mean = np.asarray(pred_mean, float)
    sigma = np.asarray(sigma, float)
    actual = np.asarray(actual, float)
    lo, hi = pred_mean - z * sigma, pred_mean + z * sigma
    return float(np.mean((actual >= lo) & (actual <= hi)))


def win_prob_from_normal(pred_mean: np.ndarray, sigma: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Analytic P(share > threshold) under a Normal(mean, sigma) approximation."""
    from math import erf, sqrt

    pred_mean = np.asarray(pred_mean, float)
    sigma = np.clip(np.asarray(sigma, float), _EPS, None)
    z = (pred_mean - threshold) / sigma
    # Phi(z) via erf
    return 0.5 * (1 + np.vectorize(lambda x: erf(x / sqrt(2)))(z))


def evaluate_backtest(preds: pd.DataFrame, *, target: str = "two_party_dem_share") -> dict:
    """Full evaluation from a backtest frame with pred mean, sigma, and actual share.

    Expects columns: ``pred_dem_share``, ``resid_sigma``, and ``target``.
    """
    mean = preds["pred_dem_share"].to_numpy()
    sigma = preds["resid_sigma"].to_numpy()
    actual = preds[target].to_numpy()
    dem_win = (actual > 0.5).astype(float)
    win_prob = win_prob_from_normal(mean, sigma)

    cc = calibration_curve(win_prob, dem_win)
    return {
        "n": int(len(preds)),
        "mae_vote_share": float(np.abs(mean - actual).mean()),
        "rmse_vote_share": float(np.sqrt(((mean - actual) ** 2).mean())),
        "brier": brier_score(win_prob, dem_win),
        "log_score": log_score(win_prob, dem_win),
        "ece": expected_calibration_error(win_prob, dem_win),
        "coverage_90": interval_coverage(mean, sigma, actual, level=0.90),
        "coverage_95": interval_coverage(mean, sigma, actual, level=0.95),
        "calibration_curve": cc.to_dict("records"),
    }
