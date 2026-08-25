"""Correlated simulation layer (P1-005).

Turns race-level expected vote + uncertainty into win probabilities and seat/Electoral
College distributions — the step that separates vote share from win probability
(CLAUDE.md §2 rule 7). Crucially, states are NOT simulated independently (§2 rule 6): a
draw shares a national component and a regional component, so a miss in one state is
informative about demographically similar states. Independent-error models fail exactly
when it matters (close, correlated years).

Error decomposition for each simulated election e and unit i:
    err_i = sqrt(a_nat)   * z_nat[e]
          + sqrt(a_reg)   * z_reg[e, region_i]
          + sqrt(a_state) * z_state[e, i]
with a_nat + a_reg + a_state = 1, scaled by the unit's sigma. The shared components
induce positive cross-unit correlation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..geography import reference as ref

# 2020-cycle Electoral College allocation (state -> electors). DC = 3.
ELECTORAL_VOTES = {
    "AL": 9,
    "AK": 3,
    "AZ": 11,
    "AR": 6,
    "CA": 55,
    "CO": 9,
    "CT": 7,
    "DE": 3,
    "DC": 3,
    "FL": 29,
    "GA": 16,
    "HI": 4,
    "ID": 4,
    "IL": 20,
    "IN": 11,
    "IA": 6,
    "KS": 6,
    "KY": 8,
    "LA": 8,
    "ME": 4,
    "MD": 10,
    "MA": 11,
    "MI": 16,
    "MN": 10,
    "MS": 6,
    "MO": 10,
    "MT": 3,
    "NE": 5,
    "NV": 6,
    "NH": 4,
    "NJ": 14,
    "NM": 5,
    "NY": 29,
    "NC": 15,
    "ND": 3,
    "OH": 18,
    "OK": 7,
    "OR": 7,
    "PA": 20,
    "RI": 4,
    "SC": 9,
    "SD": 3,
    "TN": 11,
    "TX": 38,
    "UT": 6,
    "VT": 3,
    "VA": 13,
    "WA": 12,
    "WV": 5,
    "WI": 10,
    "WY": 3,
}
EC_MAJORITY = 270


@dataclass
class CorrelationParams:
    national: float = 0.45  # share of variance that is a common national shock
    regional: float = 0.25  # share that is shared within a Census region
    state: float = 0.30  # idiosyncratic

    def normalized(self) -> CorrelationParams:
        total = self.national + self.regional + self.state
        return CorrelationParams(self.national / total, self.regional / total, self.state / total)


def simulate_shares(
    means: np.ndarray,
    sigmas: np.ndarray,
    regions: list[str],
    *,
    n_sims: int = 10_000,
    params: CorrelationParams | None = None,
    seed: int = 7,
) -> np.ndarray:
    """Return an (n_sims, n_units) array of simulated two-party Dem shares."""
    params = (params or CorrelationParams()).normalized()
    rng = np.random.default_rng(seed)
    n = len(means)
    means = np.asarray(means, float)
    sigmas = np.asarray(sigmas, float)

    reg_index = {r: k for k, r in enumerate(sorted(set(regions)))}
    reg_ids = np.array([reg_index[r] for r in regions])

    z_nat = rng.standard_normal((n_sims, 1))
    z_reg_all = rng.standard_normal((n_sims, len(reg_index)))
    z_reg = z_reg_all[:, reg_ids]
    z_state = rng.standard_normal((n_sims, n))

    err = (
        np.sqrt(params.national) * z_nat + np.sqrt(params.regional) * z_reg + np.sqrt(params.state) * z_state
    )
    shares = means[None, :] + sigmas[None, :] * err
    return np.clip(shares, 0.0, 1.0)


def win_probabilities(sim_shares: np.ndarray, units: list[str]) -> pd.DataFrame:
    """P(Dem two-party share > 0.5) per unit from simulated shares."""
    p = (sim_shares > 0.5).mean(axis=0)
    return pd.DataFrame({"unit": units, "dem_win_prob": p})


def electoral_college_distribution(sim_shares: np.ndarray, states: list[str]) -> dict:
    """Distribution of Democratic electoral votes across simulations."""
    ev = np.array([ELECTORAL_VOTES.get(s, 0) for s in states])
    dem_ev = ((sim_shares > 0.5) * ev[None, :]).sum(axis=1)
    return {
        "mean_dem_ev": float(dem_ev.mean()),
        "median_dem_ev": float(np.median(dem_ev)),
        "p_dem_majority": float((dem_ev >= EC_MAJORITY).mean()),
        "ev_5th": float(np.percentile(dem_ev, 5)),
        "ev_95th": float(np.percentile(dem_ev, 95)),
    }


def seat_distribution(sim_shares: np.ndarray, units: list[str], *, total_seats: int | None = None) -> dict:
    """Distribution of Democratic seats + chamber-control probability (majority)."""
    n_units = sim_shares.shape[1]
    total = total_seats or n_units
    dem_seats = (sim_shares > 0.5).sum(axis=1)
    majority = total / 2
    return {
        "n_units": n_units,
        "mean_dem_seats": float(dem_seats.mean()),
        "median_dem_seats": float(np.median(dem_seats)),
        "p_dem_control": float((dem_seats > majority).mean()),
        "seats_5th": float(np.percentile(dem_seats, 5)),
        "seats_95th": float(np.percentile(dem_seats, 95)),
    }


def simulate_presidential(
    panel_preds: pd.DataFrame, *, n_sims: int = 10_000, params: CorrelationParams | None = None
) -> dict:
    """Full presidential sim from a frame with state_po, pred mean, sigma.

    Expects columns: ``state_po``, ``pred_dem_share``, ``resid_sigma``.
    """
    df = panel_preds.dropna(subset=["pred_dem_share", "resid_sigma"]).copy()
    regions = [ref.by_postal(s).census_region for s in df["state_po"]]
    sim = simulate_shares(
        df["pred_dem_share"].to_numpy(), df["resid_sigma"].to_numpy(), regions, n_sims=n_sims, params=params
    )
    wp = win_probabilities(sim, df["state_po"].tolist())
    ec = electoral_college_distribution(sim, df["state_po"].tolist())
    return {"win_probabilities": wp, "electoral_college": ec}
