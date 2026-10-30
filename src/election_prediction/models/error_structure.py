"""Estimate shared error from earlier out-of-sample residuals, then test seat intervals."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..geography import reference
from .simulation import CorrelationParams, simulate_shares


def estimate(predictions: pd.DataFrame, *, min_cycles: int = 4) -> dict:
    data = predictions.dropna(subset=["cycle", "error", "resid_sigma", "state_po"]).copy()
    data = data[data["resid_sigma"] > 0]
    if data["cycle"].nunique() < min_cycles:
        return {"status": "insufficient_history", "n_cycles": int(data["cycle"].nunique())}
    data["region"] = data["state_po"].map(lambda s: reference.by_postal(s).census_region)
    data["z"] = data["error"] / data["resid_sigma"]
    bias = float(data.groupby("cycle")["z"].mean().mean())
    data["z"] -= bias
    across, within, variances = [], [], []
    for _, cycle in data.groupby("cycle"):
        moments = cycle.groupby("region")["z"].agg(["sum", "count"])
        squared = cycle.assign(z2=cycle["z"] ** 2).groupby("region")["z2"].sum()
        n = len(cycle)
        cross_pairs = n * n - float((moments["count"] ** 2).sum())
        same_pairs = float((moments["count"] * (moments["count"] - 1)).sum())
        if cross_pairs <= 0 or same_pairs <= 0:
            continue
        across.append(float((cycle["z"].sum() ** 2 - (moments["sum"] ** 2).sum()) / cross_pairs))
        within.append(float(((moments["sum"] ** 2 - squared).sum()) / same_pairs))
        variances.append(float((cycle["z"] ** 2).mean()))
    if len(across) < min_cycles:
        return {"status": "insufficient_regional_coverage", "n_cycles": len(across)}
    national = max(float(np.mean(across)), 0.0)
    regional = max(float(np.mean(within)) - national, 0.0)
    independent = max(float(np.mean(variances)) - national - regional, 0.0)
    total = national + regional + independent
    if total <= 0 or national + regional <= 0:
        return {"status": "shared_error_unidentified", "n_cycles": len(across)}
    params = CorrelationParams(national / total, regional / total, independent / total)
    return {
        "status": "estimated",
        "n_cycles": len(across),
        "parameters": vars(params),
        "standardized_bias": bias,
        "method": "equal-cycle pair covariance: cross-region, within-region, unit residual",
        "limitations": [
            "Census regions; final component is per-seat, not a shared state shock",
            "variance components clipped at zero; few independent cycles",
            "residuals include the benchmark national estimator's error",
        ],
    }


def _seat_interval(group: pd.DataFrame, params: CorrelationParams) -> dict:
    draws = simulate_shares(
        group["pred_dem_share"].to_numpy(),
        group["resid_sigma"].to_numpy(),
        [reference.by_postal(s).census_region for s in group["state_po"]],
        n_sims=5000,
        params=params,
        seed=7,
    )
    counts = (draws > 0.5).sum(axis=1)
    lo, hi = np.quantile(counts, [0.05, 0.95])
    actual = (
        int(group["actual_dem_win"].sum())
        if "actual_dem_win" in group
        else int(group["two_party_dem_share"].gt(0.5).sum())
    )
    interval_score = hi - lo + 20 * max(lo - actual, 0) + 20 * max(actual - hi, 0)
    result = {
        "low": float(lo),
        "high": float(hi),
        "actual": actual,
        "covered": bool(lo <= actual <= hi),
        "interval_score": float(interval_score),
    }
    if len(group) == 435 and "actual_dem_win" in group:
        probability = float(np.mean(counts >= 218))
        outcome = float(actual >= 218)
        bounded = float(np.clip(probability, 1e-6, 1 - 1e-6))
        result.update(
            {
                "control_probability": probability,
                "control_brier": (probability - outcome) ** 2,
                "control_log_loss": -outcome * np.log(bounded) - (1 - outcome) * np.log(1 - bounded),
            }
        )
    return result


def evaluate(predictions: pd.DataFrame, *, expected_units: int | None = None) -> dict:
    folds = []
    for cycle, group in predictions.groupby("cycle"):
        fitted = estimate(predictions[predictions["cycle"] < cycle])
        if fitted["status"] != "estimated":
            continue
        folds.append(
            {
                "cycle": int(cycle),
                "n_seats": len(group),
                "train_through": int(cycle) - 2,
                "parameters": fitted["parameters"],
                "asserted": _seat_interval(group, CorrelationParams()),
                "estimated": _seat_interval(group, CorrelationParams(**fitted["parameters"])),
            }
        )
    fitted = estimate(predictions)
    summary = {}
    for model in ("asserted", "estimated"):
        if folds:
            summary[model] = {
                "coverage_90": float(np.mean([f[model]["covered"] for f in folds])),
                "mean_interval_score": float(np.mean([f[model]["interval_score"] for f in folds])),
            }
    subset_gate_passed = bool(
        len(folds) >= 4
        and summary["estimated"]["coverage_90"] >= 0.85
        and summary["estimated"]["mean_interval_score"] < summary["asserted"]["mean_interval_score"]
    )
    full_universe_verified = (
        expected_units is not None
        and bool(folds)
        and all(fold["n_seats"] == expected_units for fold in folds)
    )
    promote = subset_gate_passed and full_universe_verified and fitted["status"] == "estimated"
    return {
        "estimated": fitted,
        "held_out_cycles": folds,
        "summary": summary,
        "evaluation_universe": "covered contested seats only; fallback and unopposed seats are not validated",
        "subset_gate_passed": subset_gate_passed,
        "full_universe_verified": full_universe_verified,
        "promotion_gate": (
            "full forecast universe; at least 4 held-out cycles, coverage >= .85, lower interval score"
        ),
        "promoted": promote,
        "selected_parameters": fitted["parameters"] if promote else vars(CorrelationParams()),
        "selection_reason": "passed chronological interval gate"
        if promote
        else "retained asserted split: full-universe chronological gate not met",
    }
