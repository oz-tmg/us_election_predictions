"""Transparent time/sample-weighted polling average (P2-002)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

POPULATION_WEIGHT = {"LV": 1.0, "RV": 0.85, "A": 0.65}
GROUP_COLUMNS = ["office", "cycle", "geography_id", "state_po", "district_num"]


def _poll_weights(
    polls: pd.DataFrame,
    *,
    reference_date: pd.Timestamp,
    half_life_days: float,
) -> pd.DataFrame:
    frame = polls.copy()
    midpoint = frame["field_start"] + (frame["field_end"] - frame["field_start"]) / 2
    frame["age_days"] = (reference_date - midpoint).dt.total_seconds().div(86_400).clip(lower=0)
    frame["time_weight"] = np.exp(-np.log(2) * frame["age_days"] / half_life_days)
    frame["sample_weight"] = np.sqrt(frame["sample_size"].astype(float))
    frame["population_weight"] = frame["population"].map(POPULATION_WEIGHT).astype(float)
    frame["adjusted_dem_share"] = (frame["two_party_dem_share"] - frame["house_effect_dem"].fillna(0.0)).clip(
        0, 1
    )
    frame["weight"] = frame["time_weight"] * frame["sample_weight"] * frame["population_weight"]
    return frame


def average_polls(
    polls: pd.DataFrame,
    *,
    reference_date: str | date,
    half_life_days: float = 21.0,
    poll_error_floor: float = 0.025,
) -> pd.DataFrame:
    """Return one polling estimate per race/geography.

    Weights combine exponential time decay, square-root sample size, and population
    quality (LV > RV > adults). ``house_effect_dem`` is an explicit input placeholder:
    the average corrects supplied effects but does not estimate ratings from this small
    baseline dataset. Uncertainty includes sampling variance, between-poll dispersion,
    and a non-zero historical-error floor.
    """
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    if poll_error_floor <= 0:
        raise ValueError("poll_error_floor must be positive")
    as_of = pd.Timestamp(reference_date).normalize()
    eligible = polls[polls["field_end"] <= as_of].copy()
    if eligible.empty:
        raise ValueError(f"No polls were complete by the {as_of.date()} reference date")
    weighted = _poll_weights(eligible, reference_date=as_of, half_life_days=half_life_days)
    rows = []
    for keys, group in weighted.groupby(GROUP_COLUMNS, dropna=False, sort=True):
        weight = group["weight"].to_numpy(float)
        if not np.isfinite(weight).all() or weight.sum() <= 0:
            raise ValueError(f"Invalid poll weights for group {keys}")
        normalized = weight / weight.sum()
        shares = group["adjusted_dem_share"].to_numpy(float)
        mean = float(np.sum(normalized * shares))
        between_variance = float(np.sum(normalized * (shares - mean) ** 2))
        sample_variance = float(
            np.sum(normalized**2 * shares * (1 - shares) / group["sample_size"].to_numpy(float))
        )
        sigma = float(np.sqrt(sample_variance + between_variance + poll_error_floor**2))
        office, cycle, geography_id, state_po, district_num = keys
        rows.append(
            {
                "office": office,
                "cycle": int(cycle),
                "geography_id": geography_id,
                "state_po": state_po,
                "district_num": district_num,
                "as_of": as_of.date().isoformat(),
                "poll_mean_dem_share": mean,
                "poll_sigma": sigma,
                "n_polls": int(len(group)),
                "n_pollsters": int(group["pollster"].nunique()),
                "effective_polls": float(1 / np.sum(normalized**2)),
                "first_field_start": group["field_start"].min().date().isoformat(),
                "last_field_end": group["field_end"].max().date().isoformat(),
                "house_effects_applied": bool(group["house_effect_dem"].abs().gt(0).any()),
            }
        )
    return pd.DataFrame(rows).sort_values(GROUP_COLUMNS).reset_index(drop=True)


def blend_with_fundamentals(
    fundamentals: pd.DataFrame,
    polling_averages: pd.DataFrame,
    *,
    uncertainty_floor: float = 0.02,
) -> pd.DataFrame:
    """Precision-blend state polling averages with a transparent fundamentals prior."""
    required = {"state_po", "pred_dem_share", "resid_sigma"}
    if not required.issubset(fundamentals.columns):
        raise ValueError(f"Fundamentals input requires {sorted(required)}")
    poll_cols = ["state_po", "poll_mean_dem_share", "poll_sigma", "n_polls", "n_pollsters"]
    if not set(poll_cols).issubset(polling_averages.columns):
        raise ValueError(f"Polling averages require {poll_cols}")
    if uncertainty_floor <= 0:
        raise ValueError("uncertainty_floor must be positive")

    out = fundamentals.copy().rename(
        columns={"pred_dem_share": "fundamental_dem_share", "resid_sigma": "fundamental_sigma"}
    )
    out = out.merge(polling_averages[poll_cols], on="state_po", how="left", validate="one_to_one")
    has_poll = out["poll_mean_dem_share"].notna()
    prior_precision = 1 / out["fundamental_sigma"].clip(lower=1e-6) ** 2
    poll_precision = 1 / out["poll_sigma"].clip(lower=1e-6) ** 2
    total_precision = prior_precision + poll_precision
    blended = (
        prior_precision * out["fundamental_dem_share"] + poll_precision * out["poll_mean_dem_share"]
    ) / total_precision
    posterior_sigma = np.sqrt(1 / total_precision).clip(lower=uncertainty_floor)

    out["pred_dem_share"] = out["fundamental_dem_share"].where(~has_poll, blended).clip(0, 1)
    out["resid_sigma"] = out["fundamental_sigma"].where(~has_poll, posterior_sigma)
    out["poll_weight"] = 0.0
    out.loc[has_poll, "poll_weight"] = (poll_precision / total_precision)[has_poll]
    out["signal_mode"] = np.where(has_poll, "fundamentals+polls", "fundamentals_only")
    return out
