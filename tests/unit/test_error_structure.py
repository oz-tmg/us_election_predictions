import pandas as pd

from election_prediction.models import error_structure


def test_unidentified_shared_error_cannot_promote_independence():
    data = pd.DataFrame(
        [
            {
                "cycle": y,
                "state_po": s,
                "error": 0.0,
                "resid_sigma": 0.1,
                "pred_dem_share": 0.5,
                "two_party_dem_share": 0.5,
            }
            for y in range(2000, 2016, 2)
            for s in ["CA", "OR", "NY", "MA"]
        ]
    )
    report = error_structure.evaluate(data)
    assert not report["promoted"]
    assert report["selected_parameters"] == {"national": 0.45, "regional": 0.25, "state": 0.30}


def test_success_on_subset_cannot_promote_a_full_chamber_parameter(monkeypatch):
    candidate = {"national": 0.1, "regional": 0.1, "state": 0.8}
    monkeypatch.setattr(
        error_structure,
        "estimate",
        lambda _: {
            "status": "estimated",
            "parameters": candidate,
        },
    )
    monkeypatch.setattr(
        error_structure,
        "_seat_interval",
        lambda group, params: {
            "covered": True,
            "interval_score": 1 if params.national == 0.1 else 2,
        },
    )
    predictions = pd.DataFrame({"cycle": list(range(2000, 2012, 2)), "state_po": ["CA"] * 6})
    report = error_structure.evaluate(predictions, expected_units=435)
    assert report["subset_gate_passed"]
    assert not report["full_universe_verified"]
    assert not report["promoted"]
