"""Pre-registration: the properties that make a sealed forecast worth sealing.

A pre-registration is only evidence if it cannot be quietly revised and if the scoring
rules were fixed before the outcome was known. These tests pin both.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from election_prediction.reporting import preregistration as prereg


def _band() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"assumption": "shrinkage=0.25", "shrinkage": 0.25, "house_p_dem": 0.536},
            {"assumption": "shrinkage=1", "shrinkage": 1.0, "house_p_dem": 0.770},
        ]
    )


def _seats() -> pd.DataFrame:
    rows = []
    for a in ("shrinkage=0.25", "shrinkage=1"):
        for i, (src, conf) in enumerate([("model", "unchanged"), ("fallback_state_lean", "redrawn")]):
            rows.append(
                {
                    "assumption": a,
                    "office": "us_house",
                    "geography_id": f"g{i}",
                    "state_po": "GA",
                    "district_num": float(i + 1),
                    "mean_dem_share": 0.52,
                    "sigma": 0.11,
                    "dem_win_prob": 0.6,
                    "source": src,
                    "boundary_confidence": conf,
                    "litigation_risk": "none",
                }
            )
    return pd.DataFrame(rows)


def _payload(**over):
    kwargs = dict(
        election_date="2026-11-03",
        band=_band(),
        seats=_seats(),
        environment={"identified": False, "status": "band"},
        house_coverage={"seats_projected": 2},
        senate_coverage={"seats_projected": 0},
        conclusions=["House: favoured at every assumption."],
        declared_defects=["173 seats on a state-lean fallback."],
        data_snapshots={"MEDSL": "2026-09-30"},
    )
    kwargs.update(over)
    return prereg.build(**kwargs)


def test_every_registered_assumption_is_carried_so_none_can_be_chosen_later():
    """Registering a band and reporting only the lucky row afterwards is forking paths."""
    payload = _payload()
    registered = {r["assumption"] for r in payload["predictions"]["band"]}
    assert registered == {"shrinkage=0.25", "shrinkage=1"}
    assert "forbidden" in payload["evaluation_plan"]["every_assumption_is_scored"]


def test_per_seat_probabilities_are_registered_not_just_chamber_totals():
    """Calibration cannot be scored from a seat count; the per-seat probabilities must be sealed."""
    seats = _payload()["predictions"]["seats"]
    assert all("dem_win_prob" in row for row in seats)
    assert len(seats) == 4


def test_the_digest_changes_if_any_prediction_changes():
    base = _payload()
    nudged = _seats()
    nudged.loc[0, "dem_win_prob"] = 0.61
    assert _payload(seats=nudged)["predictions_sha256"] != base["predictions_sha256"]


def test_the_digest_is_stable_for_identical_predictions():
    assert _payload()["predictions_sha256"] == _payload()["predictions_sha256"]


def test_the_digest_covers_predictions_only_not_commentary():
    """Fixing a typo in a caveat must not look like tampering with the forecast."""
    a = _payload()
    b = _payload(conclusions=["House: favoured at every assumption in the band."])
    assert a["predictions_sha256"] == b["predictions_sha256"]


def test_defects_and_a_failure_condition_are_declared_in_advance():
    payload = _payload()
    assert payload["declared_defects"]
    assert "too narrow" in payload["evaluation_plan"]["failure_condition"]
    assert payload["evaluation_plan"]["comparators_fixed_in_advance"]


def test_split_evaluation_is_required_so_the_fallback_seats_cannot_hide():
    plan = _payload()["evaluation_plan"]["split_evaluation_required"]
    assert "separately" in plan and "fallback" in plan


def test_writing_refuses_to_overwrite_a_sealed_registration(tmp_path):
    payload = _payload()
    prereg.write(payload, tmp_path)
    with pytest.raises(FileExistsError, match="sealed by definition"):
        prereg.write(payload, tmp_path)


def test_the_written_pair_round_trips_and_renders(tmp_path):
    payload = _payload()
    json_path, md_path = prereg.write(payload, tmp_path)
    assert json.loads(json_path.read_text())["predictions_sha256"] == payload["predictions_sha256"]
    md = md_path.read_text()
    assert "NOT PUBLISHED AS A FORECAST" in md
    assert "What I expect to be wrong" in md


def test_the_committed_registration_is_internally_consistent():
    """The real artefact: its stored digest must match its own predictions."""
    path = "reports/preregistration_2026-11-03.json"
    payload = json.loads(open(path).read())
    assert payload["predictions_sha256"] == prereg._digest(payload["predictions"])
    assert payload["election_date"] == "2026-11-03"
    house = [s for s in payload["predictions"]["seats"] if s["office"] == "us_house"]
    per_assumption = len(house) // len({s["assumption"] for s in house})
    assert per_assumption == 435
