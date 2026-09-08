"""Forward projection of a live cycle (2026) from fitted baselines."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.models.baseline import projection
from election_prediction.models.baseline.presidential import OLSModel


def _fitted_house_model() -> OLSModel:
    train = pd.DataFrame(
        {
            "district_lean": [-0.2, -0.1, 0.0, 0.1, 0.2, 0.05],
            "national_dem_share": [0.49, 0.50, 0.51, 0.52, 0.53, 0.50],
            "incumbent_dem": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
            "incumbent_rep": [1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
            "two_party_dem_share": [0.30, 0.42, 0.50, 0.62, 0.70, 0.55],
        }
    )
    return OLSModel(
        features=list(
            projection.__dict__.get("_", [])
            or ["district_lean", "national_dem_share", "incumbent_dem", "incumbent_rep"]
        )
    ).fit(train)


def _roster() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "office": ["us_house", "us_house", "us_house", "us_senate"],
            "state_po": ["GA", "GA", "DC", "WY"],
            "district_num": [1.0, 2.0, 0.0, None],
            "geography_id": ["g1", "g2", "gdc", "swy"],
            "incumbent_party": ["DEMOCRAT", "REPUBLICAN", "DEMOCRAT", "OTHER"],
            "incumbent_name": ["A", "B", "C", "CYNTHIA M. LUMMIS"],
            "prior_dem_share": [0.55, 0.45, 0.90, 0.24],
        }
    )


def test_non_voting_delegates_are_excluded_from_the_projected_chamber():
    """DC elects a Delegate; counting it would put 436 seats in a 435-seat House."""
    out, cov = projection.project_house(
        _roster(), _fitted_house_model(), national_dem_share=0.52, lagged_national_dem_share=0.49
    )
    assert set(out["state_po"]) == {"GA"}
    assert cov["seats_in_roster"] == 2


def test_a_stronger_national_environment_moves_every_district_up():
    model = _fitted_house_model()
    low, _ = projection.project_house(
        _roster(), model, national_dem_share=0.49, lagged_national_dem_share=0.49
    )
    high, _ = projection.project_house(
        _roster(), model, national_dem_share=0.55, lagged_national_dem_share=0.49
    )
    assert (high["mean_dem_share"].to_numpy() > low["mean_dem_share"].to_numpy()).all()


def test_the_party_crosswalk_override_restores_a_mislabelled_incumbent():
    """An OTHER incumbent would otherwise be encoded as an open seat (P0-003 stopgap)."""
    terms = projection._incumbency_terms(_roster())
    lummis = terms[terms["state_po"] == "WY"].iloc[0]
    assert lummis["incumbent_rep"] == 1.0
    assert lummis["incumbent_dem"] == 0.0


def test_projections_never_claim_verified_incumbency():
    """Every 2026 seat has incumbent_status 'unknown'; primaries are not compiled."""
    out, cov = projection.project_house(
        _roster(), _fitted_house_model(), national_dem_share=0.52, lagged_national_dem_share=0.49
    )
    assert cov["incumbency_verified"] is False
    assert out["incumbency_assumed"].all()


def test_uniform_swing_is_additive_and_separate_from_the_senate_model():
    train = pd.DataFrame(
        {
            "state_pres_lean": [-0.2, -0.1, 0.0, 0.1, 0.2, 0.05],
            "incumbent_dem": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
            "incumbent_rep": [1.0, 0.0, 1.0, 0.0, 1.0, 0.0],
            "midterm_penalty": [1.0, 1.0, 0.0, 0.0, -1.0, 1.0],
            "two_party_dem_share": [0.30, 0.42, 0.50, 0.62, 0.70, 0.55],
        }
    )
    model = OLSModel(features=["state_pres_lean", "incumbent_dem", "incumbent_rep", "midterm_penalty"]).fit(
        train
    )
    ref = pd.DataFrame({"state_po": ["WY"], "state_pres_lean": [-0.25]})
    flat, _ = projection.project_senate(_roster(), model, ref, midterm_penalty=1.0)
    swung, cov = projection.project_senate(_roster(), model, ref, midterm_penalty=1.0, uniform_swing=0.03)
    assert swung.iloc[0]["mean_dem_share"] == pytest.approx(flat.iloc[0]["mean_dem_share"] + 0.03)
    assert cov["uniform_swing"] == 0.03
