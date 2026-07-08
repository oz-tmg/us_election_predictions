"""Unit tests for P0-006/P0-007 ingestion and the P1 baseline stack."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from election_prediction.data import acs, medsl, synthetic
from election_prediction.evaluation import forecast_eval
from election_prediction.features import fundamentals
from election_prediction.features.race_table import build_race_table
from election_prediction.geography import tiger
from election_prediction.models import simulation
from election_prediction.models.baseline import house_partisanship, presidential


@pytest.fixture(scope="module")
def race_table():
    parts = []
    for office in ("president", "us_senate", "us_house"):
        raw = synthetic.build_fixture(office)
        raw.columns = [c.lower() for c in raw.columns]
        raw["source_id"] = "test"
        raw["snapshot_date"] = "2026-07-08"
        parts.append(medsl.standardize_silver(raw, office))
    return build_race_table(pd.concat(parts, ignore_index=True))


@pytest.fixture(scope="module")
def acs_features():
    raw = acs.build_synthetic_acs(2020)
    return acs.standardize_acs(raw, vintage=2020, source_id="acs_test")


# ------------------------------------------------------------------- ACS (P0-006)
def test_acs_schema_and_signal(acs_features):
    assert list(acs_features.columns) == acs.ACS_FEATURE_COLUMNS
    assert len(acs_features) == 51  # 50 + DC
    assert acs_features["college_share"].between(0, 1).all()
    # college share correlates with the synthetic partisan lean
    lean = acs_features["state_po"].map(synthetic.STATE_BASE_DEM_LEAN)
    assert np.corrcoef(acs_features["college_share"], lean)[0, 1] > 0.5


# ----------------------------------------------------------------- TIGER (P0-007)
def test_tiger_synthetic_boundaries_valid():
    gdf = tiger.build_synthetic_boundaries("state")
    chk = tiger.validate_boundaries(gdf)
    assert chk["ok"]
    assert chk["geoid_unique"]


def test_tiger_url_pattern():
    assert tiger.tiger_url(2022, "cd").endswith("tl_2022_us_cd118.zip")
    assert "STATE" in tiger.tiger_url(2022, "state")


# ------------------------------------------------------------- panel (fundamentals)
def test_presidential_panel_has_lags(race_table, acs_features):
    panel = fundamentals.build_presidential_panel(race_table, acs_features)
    assert (panel["office"] == "president").all()
    assert panel["lag_dem_share"].notna().sum() > 0
    assert panel["college_share"].notna().sum() > 0


# ----------------------------------------------------------- baseline (P1-001/002)
def test_presidential_backtest_beats_or_matches_persistence(race_table, acs_features):
    panel = fundamentals.build_presidential_panel(race_table, acs_features)
    preds, metrics = presidential.backtest_leave_one_cycle_out(panel)
    assert metrics["n"] > 0
    assert metrics["mae"] < 0.10  # sensible on structured data
    # should not be dramatically worse than naive persistence
    assert metrics["mae"] <= metrics["naive_persistence_mae"] + 0.01
    assert 0 <= metrics["winner_accuracy"] <= 1


def test_house_partisanship_score(race_table):
    hi = fundamentals.build_house_partisanship_input(race_table)
    score = house_partisanship.build_partisanship_score(hi)
    assert score["geography_id"].is_unique
    assert score["partisanship_score"].abs().max() < 0.6
    assert score["lean_label"].str.match(r"^(D|R)\+\d+|EVEN$").all()


# ------------------------------------------------------------- simulation (P1-005)
def test_simulation_is_correlated():
    # two units in the same region should have positively correlated draws
    means = np.array([0.5, 0.5])
    sigmas = np.array([0.05, 0.05])
    sim = simulation.simulate_shares(means, sigmas, ["South", "South"], n_sims=5000)
    corr = np.corrcoef(sim[:, 0], sim[:, 1])[0, 1]
    assert corr > 0.4  # shared national + regional error induces correlation


def test_electoral_college_distribution_ranges():
    means = np.full(51, 0.5)
    sigmas = np.full(51, 0.04)
    states = list(simulation.ELECTORAL_VOTES.keys())
    sim = simulation.simulate_shares(means, sigmas, ["South"] * 51, n_sims=2000)
    ec = simulation.electoral_college_distribution(sim, states)
    assert 0 <= ec["p_dem_majority"] <= 1
    assert ec["ev_5th"] <= ec["mean_dem_ev"] <= ec["ev_95th"]


# ------------------------------------------------------------- evaluation (P1-006)
def test_calibration_and_scores():
    rng = np.random.default_rng(0)
    prob = rng.uniform(0, 1, 500)
    outcome = (rng.uniform(0, 1, 500) < prob).astype(float)  # well-calibrated by construction
    assert 0 <= forecast_eval.brier_score(prob, outcome) <= 1
    assert forecast_eval.expected_calibration_error(prob, outcome) < 0.15
    cc = forecast_eval.calibration_curve(prob, outcome)
    assert {"mean_pred", "observed_freq", "n"}.issubset(cc.columns)


def test_win_prob_from_normal_monotonic():
    p_low = forecast_eval.win_prob_from_normal(np.array([0.45]), np.array([0.03]))[0]
    p_high = forecast_eval.win_prob_from_normal(np.array([0.55]), np.array([0.03]))[0]
    assert p_low < 0.5 < p_high
