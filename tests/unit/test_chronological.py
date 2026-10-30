import numpy as np
import pandas as pd
import pytest

from election_prediction.evaluation import chronological
from election_prediction.models import error_structure


def _panel():
    return pd.DataFrame(
        [
            {
                "cycle": year,
                "state_po": state,
                "lag_dem_share": 0.4 + i * 0.05,
                "national_dem_share": 0.48 + (year % 4) * 0.01,
                "two_party_dem_share": 0.41 + i * 0.05 + (year % 4) * 0.01,
            }
            for year in range(1980, 2004, 2)
            for i, state in enumerate(["VA", "CA", "TX", "NY"])
        ]
    )


def test_future_elections_and_held_out_national_truth_cannot_change_predictions():
    original = _panel()
    features = ["lag_dem_share", "national_dem_share"]
    pred, _ = chronological.backtest(original, features=features, naive_feature="lag_dem_share")
    changed = original.copy()
    changed.loc[changed.cycle >= 2000, "two_party_dem_share"] = 0.99
    changed.loc[changed.cycle == 2000, "national_dem_share"] = 0.01
    rerun, _ = chronological.backtest(changed, features=features, naive_feature="lag_dem_share")
    np.testing.assert_allclose(
        pred.loc[pred.cycle <= 2000, "pred_dem_share"], rerun.loc[rerun.cycle <= 2000, "pred_dem_share"]
    )
    assert (pred.train_through < pred.cycle).all()


def test_unvintaged_demographics_are_refused():
    with pytest.raises(ValueError, match="vintaged"):
        chronological.backtest(_panel(), features=["college_share"], naive_feature="lag_dem_share")


def test_minor_party_opponent_does_not_make_one_sided_major_party_outcome_usable():
    panel = _panel()
    panel["uncontested_flag"] = False
    panel.loc[panel.cycle.eq(2000) & panel.state_po.eq("VA"), "two_party_dem_share"] = 1.0
    pred, _ = chronological.backtest(
        panel, features=["lag_dem_share", "national_dem_share"], naive_feature="lag_dem_share"
    )
    assert pred.two_party_dem_share.between(0, 1, inclusive="neither").all()


def test_senate_uses_the_previous_presidential_election_even_in_presidential_years():
    panel = pd.DataFrame([{"cycle": y, "state_po": "VA"} for y in [2020, 2022, 2024]])
    presidential = pd.DataFrame(
        [
            {"cycle": y, "state_po": "VA", "two_party_dem_share": v, "national_dem_share": 0.5}
            for y, v in [(2016, 0.52), (2020, 0.55), (2024, 0.57)]
        ]
    )
    out = chronological.lag_senate_presidential_reference(panel, presidential)
    assert out.pres_reference_cycle.tolist() == [2016, 2020, 2020]


def test_correlation_is_estimated_from_known_shared_synthetic_shocks():
    rng = np.random.default_rng(19)
    rows = []
    states = ["CA", "OR", "NY", "MA", "TX", "VA", "IA", "MI"]
    for cycle in range(500):
        national = rng.normal(scale=np.sqrt(0.45))
        regions = rng.normal(scale=np.sqrt(0.25), size=4)
        for i, state in enumerate(states):
            for _ in range(12):
                error = national + regions[i // 2] + rng.normal(scale=np.sqrt(0.30))
                rows.append({"cycle": cycle, "state_po": state, "resid_sigma": 1.0, "error": error})
    fit = error_structure.estimate(pd.DataFrame(rows))
    assert fit["status"] == "estimated"
    assert fit["parameters"]["national"] == pytest.approx(0.45, abs=0.10)
    assert sum(fit["parameters"].values()) == pytest.approx(1.0)
    assert error_structure.estimate(pd.DataFrame(rows).query("cycle < 2"))["status"] == "insufficient_history"
