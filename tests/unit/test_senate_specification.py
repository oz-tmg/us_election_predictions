"""Senate open-seat holder specification and its promotion gate (2026-10-29)."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.models.baseline import projection, senate
from election_prediction.models.baseline.presidential import OLSModel


def _evaluations(**v1: float | None) -> dict:
    base = {"mae": 0.080, "open_seat_mae": 0.078, "coverage_90": 0.90, "n": 500, "n_open_seats": 150}
    return {"v0_incumbent_running": base, "v1_open_seat_holder": {**base, **v1}}


def test_gate_promotes_a_candidate_that_wins_every_check() -> None:
    out = senate.select_specification(_evaluations(mae=0.079, open_seat_mae=0.075))
    assert out["selected"] == "v1_open_seat_holder"
    assert out["features"] == senate.HOLDER_FEATURES


@pytest.mark.parametrize(
    ("v1", "failed"),
    [
        ({"mae": 0.081, "open_seat_mae": 0.075}, "lower overall MAE"),
        ({"mae": 0.079, "open_seat_mae": 0.079}, "lower open-seat MAE"),
        ({"mae": 0.079, "open_seat_mae": 0.075, "coverage_90": 0.87}, "90% coverage"),
        ({"mae": 0.079, "open_seat_mae": None}, "lower open-seat MAE"),
    ],
)
def test_gate_keeps_the_baseline_and_names_the_failed_check(v1: dict, failed: str) -> None:
    out = senate.select_specification(_evaluations(**v1))
    assert out["selected"] == senate.BASELINE_SPECIFICATION
    assert failed in out["reasons"][0]


def test_open_seat_mae_uses_open_rows_only() -> None:
    preds = pd.DataFrame({"open_seat": [True, False, True], "error": [0.02, 0.50, -0.04]})
    assert senate.open_seat_mae(preds) == pytest.approx(0.03)
    assert senate.open_seat_mae(pd.DataFrame()) is None


def _universe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "office": ["us_senate"] * 4,
            "state_po": ["TX", "KY", "GA", "MI"],
            "geography_id": ["s48", "s21", "s13", "s26"],
            "incumbent_party": ["REPUBLICAN", "REPUBLICAN", "DEMOCRAT", "DEMOCRAT"],
            "incumbent_name": ["A", "B", "C", "D"],
            # TX/KY/MI: incumbent not on the ballot; GA: running.
            "incumbent_running": [False, False, True, False],
            "boundary_confidence": ["n/a"] * 4,
        }
    )


def test_projection_marks_the_holder_of_each_open_seat() -> None:
    terms = projection._incumbency_terms(_universe()).set_index("state_po")
    assert terms.loc["TX", ["incumbent_rep", "open_rep_held", "open_dem_held"]].tolist() == [0, 1, 0]
    assert terms.loc["GA", ["incumbent_dem", "open_dem_held"]].tolist() == [1, 0]
    assert terms.loc["MI", ["incumbent_dem", "open_dem_held"]].tolist() == [0, 1]


def test_holder_term_moves_an_open_seat_toward_its_holder() -> None:
    train = pd.DataFrame(
        {
            "state_pres_lean": [-0.1, -0.1, -0.1, 0.1, 0.1, 0.1, 0.0, 0.0],
            "incumbent_dem": [0, 0, 0, 1, 0, 0, 0, 0],
            "incumbent_rep": [1, 0, 0, 0, 0, 0, 0, 0],
            "open_dem_held": [0, 0, 0, 0, 1, 0, 0, 0],
            "open_rep_held": [0, 1, 0, 0, 0, 0, 1, 0],
            "midterm_penalty": [1, 1, 1, 1, 1, 1, 0, 0],
            "two_party_dem_share": [0.35, 0.40, 0.45, 0.62, 0.58, 0.55, 0.46, 0.50],
        }
    )
    ref = pd.DataFrame({"state_po": ["TX", "KY", "GA", "MI"], "state_pres_lean": [-0.06] * 4})
    v0 = OLSModel(senate.DEFAULT_FEATURES).fit(train)
    v1 = OLSModel(senate.HOLDER_FEATURES).fit(train)
    p0, _ = projection.project_senate(_universe(), v0, ref, midterm_penalty=1.0)
    p1, _ = projection.project_senate(_universe(), v1, ref, midterm_penalty=1.0)
    tx0 = p0.set_index("state_po").loc["TX", "mean_dem_share"]
    tx1 = p1.set_index("state_po").loc["TX", "mean_dem_share"]
    assert tx1 < tx0  # a Republican-held open seat keeps some Republican advantage
