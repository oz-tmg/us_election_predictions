"""Scoring a sealed forecast: proven against invented worlds, before the real one exists.

The point of writing these now is that every judgement the scorer makes can be checked
against outcomes we control. A perfect forecast must score perfectly; a reversed one must
score terribly; the pre-specified exclusions must behave identically whichever way the
result went. Once that holds across made-up elections, nothing is left to decide in
November except pressing go.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from election_prediction.evaluation import score_preregistration as sp
from election_prediction.reporting import preregistration as prereg

N = 20


def _registration(win_probs=None, shares=None) -> dict:
    """Two assumptions over N House seats, so 'every assumption is scored' is testable."""
    rng = np.random.default_rng(1)
    base_share = np.linspace(0.35, 0.65, N) if shares is None else np.asarray(shares)
    base_prob = base_share if win_probs is None else np.asarray(win_probs)
    rows = []
    for a in ("shrinkage=0.25", "shrinkage=1"):
        for i in range(N):
            rows.append(
                {
                    "assumption": a,
                    "office": "us_house",
                    "geography_id": f"g{i}",
                    "state_po": "GA",
                    "district_num": float(i),
                    "mean_dem_share": float(base_share[i]),
                    "sigma": 0.11,
                    "dem_win_prob": float(np.clip(base_prob[i], 0.01, 0.99)),
                    "source": "model" if i % 2 else "fallback_state_lean",
                    "boundary_confidence": "unchanged" if i % 2 else "redrawn",
                    "litigation_risk": "none",
                }
            )
    band = [
        {"assumption": "shrinkage=0.25", "house_mean_seats": 10.0, "house_5th": 4, "house_95th": 16},
        {"assumption": "shrinkage=1", "house_mean_seats": 12.0, "house_5th": 6, "house_95th": 18},
    ]
    rng.random()
    return prereg.build(
        election_date="2026-11-03",
        band=pd.DataFrame(band),
        seats=pd.DataFrame(rows),
        environment={"identified": False},
        house_coverage={},
        senate_coverage={},
        conclusions=[],
        declared_defects=["fallback seats are the least informed"],
        data_snapshots={},
    )


def _actual(dem_share, certified="2026-11-20", n=N) -> pd.DataFrame:
    share = np.full(n, dem_share) if np.isscalar(dem_share) else np.asarray(dem_share)
    return pd.DataFrame(
        {
            "geography_id": [f"g{i}" for i in range(n)],
            "office": "us_house",
            "actual_dem_share": share,
            "certified_on": certified,
        }
    )


def _inputs(reg, actual, as_of="2026-12-01", void=None) -> sp.ScoringInputs:
    return sp.ScoringInputs(registration=reg, actual=actual, as_of=as_of, void_geographies=void or {})


# ---- the seal ---------------------------------------------------------------------------


def test_a_tampered_registration_cannot_be_scored():
    reg = _registration()
    reg["predictions"]["seats"][0]["dem_win_prob"] = 0.999
    with pytest.raises(sp.SealBroken, match="modified since sealing"):
        sp.score(_inputs(reg, _actual(0.5)))


def test_an_intact_registration_verifies():
    out = sp.score(_inputs(_registration(), _actual(0.52)))
    assert out["registration"]["seal_verified"] is True


# ---- behaviour across invented worlds ---------------------------------------------------


def test_a_perfect_forecast_scores_perfectly():
    """Predicted share == actual share, probabilities at the extremes that match outcomes."""
    shares = np.linspace(0.35, 0.65, N)
    probs = (shares > 0.5).astype(float)
    reg = _registration(win_probs=probs, shares=shares)
    res = sp.score(_inputs(reg, _actual(shares)))["results"]["shrinkage=0.25"]["overall"]
    assert res["mae_vote_share"] == pytest.approx(0.0)
    assert res["winner_accuracy"] == pytest.approx(1.0)
    assert res["brier"] < 0.001


def test_a_reversed_forecast_scores_terribly():
    shares = np.linspace(0.35, 0.65, N)
    probs = (shares > 0.5).astype(float)
    reg = _registration(win_probs=probs, shares=shares)
    res = sp.score(_inputs(reg, _actual(1 - shares)))["results"]["shrinkage=0.25"]["overall"]
    assert res["winner_accuracy"] == pytest.approx(0.0)
    assert res["brier"] > 0.9


def test_a_coin_flip_forecast_lands_in_between():
    reg = _registration(win_probs=np.full(N, 0.5))
    res = sp.score(_inputs(reg, _actual(0.6)))["results"]["shrinkage=0.25"]["overall"]
    assert res["brier"] == pytest.approx(0.25, abs=0.01)


def test_every_registered_assumption_is_scored_and_none_is_singled_out():
    out = sp.score(_inputs(_registration(), _actual(0.52)))
    assert out["every_assumption_scored"] == ["shrinkage=0.25", "shrinkage=1"]
    assert set(out["results"]) == {"shrinkage=0.25", "shrinkage=1"}
    assert "best_assumption" not in out and "selected" not in out


# ---- the four pre-specified exclusions --------------------------------------------------


def test_uncertified_seats_are_excluded_and_counted_never_dropped():
    actual = _actual(0.52)
    actual.loc[:4, "certified_on"] = "2026-12-20"  # certified after as_of
    out = sp.score(_inputs(_registration(), actual, as_of="2026-12-01"))
    assert out["audit"]["unscored_not_certified"] == 5
    assert out["audit"]["scored"] == N - 5
    assert out["results"]["shrinkage=0.25"]["overall"]["n"] == N - 5


def test_the_as_of_date_is_reported_so_it_cannot_become_a_free_parameter():
    out = sp.score(_inputs(_registration(), _actual(0.52), as_of="2026-11-10"))
    assert out["audit"]["as_of"] == "2026-11-10"


def test_a_map_that_moved_after_sealing_voids_those_seats_with_a_source():
    void = {"g0": "https://example.gov/order", "g1": "https://example.gov/order"}
    out = sp.score(_inputs(_registration(), _actual(0.52), void=void))
    assert out["audit"]["void_map_changed_after_sealing"] == 2
    assert out["audit"]["void_sources"] == void
    assert out["results"]["shrinkage=0.25"]["overall"]["n"] == N - 2


def test_void_and_uncertified_are_reported_separately_not_merged():
    actual = _actual(0.52)
    actual.loc[:2, "certified_on"] = "2026-12-20"
    out = sp.score(_inputs(_registration(), actual, as_of="2026-12-01", void={"g10": "src"}))
    assert out["audit"]["void_map_changed_after_sealing"] == 1
    assert out["audit"]["unscored_not_certified"] == 3


def test_there_is_no_carve_out_for_retirements_or_primary_losses():
    """The forecast assumed renomination and declared it; excusing it would void the test."""
    out = sp.score(_inputs(_registration(), _actual(0.52)))
    assert "no_carve_out_for" in out["audit"]
    assert "retirements" in out["audit"]["no_carve_out_for"]


def test_uncontested_seats_are_reported_both_ways_so_neither_can_be_chosen_later():
    """Both numbers always, so the flattering one cannot be selected in November."""
    actual = _actual(0.52)
    actual["uncontested"] = [i < 4 for i in range(N)]
    out = sp.score(_inputs(_registration(), actual))
    unc = out["results"]["shrinkage=0.25"]["uncontested"]
    assert unc["included"]["n"] == N
    assert unc["excluded"]["n"] == N - 4
    # They must be genuinely different numbers, not the same metric twice.
    assert unc["included"]["n"] != unc["excluded"]["n"]


def test_without_an_uncontested_column_the_two_variants_match_rather_than_dropping_rows():
    unc = sp.score(_inputs(_registration(), _actual(0.52)))["results"]["shrinkage=0.25"]["uncontested"]
    assert unc["included"]["n"] == unc["excluded"]["n"] == N


# ---- splits and comparability -----------------------------------------------------------


def test_fallback_and_modelled_seats_are_scored_separately():
    """A pooled number would hide which half of the chamber the model understood."""
    out = sp.score(_inputs(_registration(), _actual(0.52)))
    by_source = out["results"]["shrinkage=0.25"]["house_by_source"]
    assert set(by_source) == {"model", "fallback_state_lean"}
    assert by_source["model"]["n"] + by_source["fallback_state_lean"]["n"] == N


def test_metrics_come_from_the_same_module_the_backtest_used():
    """A holdout graded by different machinery is not comparable to the backtest."""
    out = sp.score(_inputs(_registration(), _actual(0.52)))["results"]["shrinkage=0.25"]["overall"]
    assert {"brier", "log_score", "ece", "coverage_90", "coverage_95", "calibration_curve"} <= set(out)


def test_the_backtest_reference_is_carried_as_a_fixed_comparator():
    out = sp.score(_inputs(_registration(), _actual(0.52)))
    assert out["results"]["shrinkage=0.25"]["comparators"]["backtest_reference_house_mae"] == 0.078694


# ---- the pre-declared failure condition -------------------------------------------------


def test_the_failure_condition_triggers_only_when_every_interval_missed():
    """Realised 20 of 20 seats Democratic; both registered intervals top out at 16 and 18."""
    out = sp.score(_inputs(_registration(), _actual(0.90)))
    assert out["chamber"]["realised_dem_seats_among_scored"] == N
    assert out["failure_condition"]["triggered"] is True


def test_the_failure_condition_does_not_trigger_when_an_interval_contained_the_truth():
    shares = np.where(np.arange(N) < 10, 0.6, 0.4)  # exactly 10 Democratic seats
    out = sp.score(_inputs(_registration(), _actual(shares)))
    assert out["chamber"]["realised_dem_seats_among_scored"] == 10
    assert out["failure_condition"]["triggered"] is False
    assert out["chamber"]["shrinkage=0.25"]["inside_90_interval"] is True


def test_seat_count_error_is_reported_per_assumption():
    shares = np.where(np.arange(N) < 10, 0.6, 0.4)
    ch = sp.score(_inputs(_registration(), _actual(shares)))["chamber"]
    assert ch["shrinkage=0.25"]["absolute_error"] == pytest.approx(0.0)
    assert ch["shrinkage=1"]["absolute_error"] == pytest.approx(2.0)


# ---- the exclusions must not depend on which way the result went -------------------------


def test_exclusion_counts_are_identical_whichever_way_the_election_went():
    """The whole reason to write this now: the rules cannot react to the outcome."""
    reg = _registration()
    void = {"g0": "src"}
    landslide_d = _actual(0.95)
    landslide_r = _actual(0.05)
    landslide_d.loc[:1, "certified_on"] = "2026-12-20"
    landslide_r.loc[:1, "certified_on"] = "2026-12-20"

    a = sp.score(_inputs(reg, landslide_d, as_of="2026-12-01", void=void))["audit"]
    b = sp.score(_inputs(copy.deepcopy(reg), landslide_r, as_of="2026-12-01", void=void))["audit"]
    assert a["scored"] == b["scored"]
    assert a["unscored_not_certified"] == b["unscored_not_certified"]
    assert a["void_map_changed_after_sealing"] == b["void_map_changed_after_sealing"]


def test_the_committed_registration_can_be_loaded_and_its_seal_verified():
    reg = sp.load_registration("reports/preregistration_2026-11-03.json")
    sp.verify_seal(reg)  # must not raise
    assert reg["election_date"] == "2026-11-03"
