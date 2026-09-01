"""Polling schema, weighting, blending, simulation-output, and model-card tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from election_prediction.models import simulation
from election_prediction.polling import (
    average_polls,
    blend_with_fundamentals,
    standardize_polls,
    validate_polls,
)
from election_prediction.reporting.model_cards import ModelCard, render_model_card


def _raw_polls() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "poll_id": "recent-lv",
                "pollster": "Transparent Polling",
                "sponsor": "Newsroom",
                "sponsor_partisan": "NONE",
                "internal": False,
                "office": "president",
                "cycle": 2024,
                "geography_id": "state:51",
                "state_po": "VA",
                "field_start": "2024-10-26",
                "field_end": "2024-10-29",
                "sample_size": 600,
                "population": "likely voters",
                "mode": "online",
                "dem_pct": 52,
                "rep_pct": 48,
                "source_url": "https://example.com/recent",
            },
            {
                "poll_id": "older-rv",
                "pollster": "Historical Polling",
                "sponsor": "University",
                "sponsor_partisan": "NONE",
                "internal": False,
                "office": "president",
                "cycle": 2024,
                "geography_id": "state:51",
                "state_po": "VA",
                "field_start": "2024-09-28",
                "field_end": "2024-10-01",
                "sample_size": 2_000,
                "population": "RV",
                "mode": "phone",
                "dem_pct": 48,
                "rep_pct": 52,
                "source_url": "https://example.com/older",
            },
        ]
    )


@pytest.fixture
def polls() -> pd.DataFrame:
    return standardize_polls(_raw_polls(), source_id="test_polls", snapshot_date="2024-11-01")


def test_poll_schema_standardizes_percentages_and_metadata(polls):
    checks = validate_polls(polls)
    assert checks["ok"], checks
    assert polls["population"].tolist() == ["RV", "LV"]  # sorted by field end
    assert polls["two_party_dem_share"].between(0, 1).all()
    assert polls["source_id"].eq("test_polls").all()


def test_poll_validation_rejects_duplicate_ids(polls):
    duplicated = pd.concat([polls, polls.iloc[[0]]], ignore_index=True)
    assert not validate_polls(duplicated)["ok"]
    assert not validate_polls(duplicated)["poll_id_unique"]


def test_poll_validation_rejects_missing_required_text():
    raw = _raw_polls()
    raw.loc[0, "pollster"] = None
    standardized = standardize_polls(raw, source_id="test_polls", snapshot_date="2024-11-01")
    assert not validate_polls(standardized)["required_values_present"]


def test_poll_average_uses_time_sample_and_population_weights(polls):
    average = average_polls(polls, reference_date="2024-11-01")
    assert len(average) == 1
    row = average.iloc[0]
    assert 0.50 < row["poll_mean_dem_share"] < 0.52
    assert row["n_polls"] == 2
    assert 1 < row["effective_polls"] <= 2
    assert row["poll_sigma"] >= 0.025


def test_poll_average_excludes_future_information(polls):
    polls = polls.copy()
    future = polls["poll_id"] == "recent-lv"
    polls.loc[future, "field_start"] = pd.Timestamp("2024-11-02")
    polls.loc[future, "field_end"] = pd.Timestamp("2024-11-05")
    average = average_polls(polls, reference_date="2024-11-01")
    assert average["n_polls"].iloc[0] == 1
    assert average["poll_mean_dem_share"].iloc[0] == pytest.approx(0.48)


def test_house_effect_is_an_explicit_adjustment(polls):
    adjusted = polls.iloc[[1]].copy()
    adjusted["house_effect_dem"] = 0.02
    average = average_polls(adjusted, reference_date="2024-11-01")
    assert average["poll_mean_dem_share"].iloc[0] == pytest.approx(0.50)
    assert bool(average["house_effects_applied"].iloc[0])


def test_blend_preserves_unpolled_state_and_moves_polled_state(polls):
    average = average_polls(polls, reference_date="2024-11-01")
    fundamentals = pd.DataFrame(
        [
            {"state_po": "VA", "pred_dem_share": 0.48, "resid_sigma": 0.05},
            {"state_po": "MD", "pred_dem_share": 0.60, "resid_sigma": 0.04},
        ]
    )
    blended = blend_with_fundamentals(fundamentals, average)
    va = blended[blended["state_po"] == "VA"].iloc[0]
    md = blended[blended["state_po"] == "MD"].iloc[0]
    assert 0.48 < va["pred_dem_share"] < average["poll_mean_dem_share"].iloc[0]
    assert va["poll_weight"] > 0
    assert md["pred_dem_share"] == pytest.approx(0.60)
    assert md["signal_mode"] == "fundamentals_only"


def test_unit_distributions_separate_share_intervals_and_probability():
    shares = simulation.simulate_shares(
        np.array([0.49, 0.55]),
        np.array([0.03, 0.04]),
        ["South", "South"],
        n_sims=2_000,
    )
    summary = simulation.unit_distributions(shares, ["VA", "MD"])
    assert list(summary["unit"]) == ["VA", "MD"]
    assert summary["dem_win_prob"].between(0, 1).all()
    assert (summary["dem_share_5th"] <= summary["mean_dem_share"]).all()
    assert (summary["mean_dem_share"] <= summary["dem_share_95th"]).all()


def test_reusable_model_card_contains_governance_sections():
    card = ModelCard(
        name="test_model",
        version="v0",
        office_geography="President · state",
        model_type="transparent test",
        target="two-party share",
        training_cycles="2020–2024",
        sources=["Tier 0 fixture"],
        features=["past vote"],
        exclusions=["personal data"],
        assumptions=["historical relationship persists"],
        failure_modes=["realignment"],
        intended_use="Testing only.",
    )
    rendered = render_model_card(card, synthetic=True)
    for section in ("Identity", "Data and target", "Features", "Exclusions", "Assumptions", "Evaluation"):
        assert f"## {section}" in rendered
    assert "SYNTHETIC DATA" in rendered
