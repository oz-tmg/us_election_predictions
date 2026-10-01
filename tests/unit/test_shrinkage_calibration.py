"""Shrinkage calibration (NE-002): a bound, and never anything that could be used as a fit.

The single most important property is negative — this module must never hand back a scalar
shrinkage factor, because the moment one exists someone will put it in a chart.
"""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.models.baseline import shrinkage_calibration as sc

BASE = {
    "pair_id": "2017_2018",
    "specials_cycle": 2017,
    "general_cycle": 2018,
    "chamber": "us_house",
    "specials_overperformance": 0.10,
    "specials_n": 12,
    "general_margin_swing": 0.06,
    "source_url": "https://example.gov/returns",
    "retrieved_on": "2026-09-30",
    "verified_by": "AO",
    "notes": "",
}


def _pairs(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{**BASE, **r} for r in rows])[sc.PAIR_COLUMNS]


def _four(ratios=(0.6, 0.5, 0.8, 0.4)) -> pd.DataFrame:
    return _pairs(
        [
            {"pair_id": p, "specials_overperformance": 0.10, "general_margin_swing": 0.10 * r}
            for p, r in zip(sc.EXPECTED_PAIRS, ratios, strict=True)
        ]
    )


# ---- the negative property, first --------------------------------------------------------


def test_a_bound_is_an_interval_and_never_a_scalar():
    bound = sc.band_from_pairs(_four())
    assert bound.status == sc.STATUS_BOUND
    assert bound.low != bound.high
    assert not hasattr(bound, "shrinkage")
    assert not hasattr(bound, "point_estimate")


def test_as_factors_returns_a_sweep_not_a_number():
    factors = sc.band_from_pairs(_four()).as_factors(n=5)
    assert isinstance(factors, tuple) and len(factors) == 5
    assert factors[0] == pytest.approx(0.4) and factors[-1] == pytest.approx(0.8)


def test_the_bound_is_the_observed_range_not_a_confidence_interval():
    """Four observations cannot support a distributional claim; the range can."""
    bound = sc.band_from_pairs(_four(ratios=(0.6, 0.5, 0.8, 0.4)))
    assert bound.low == pytest.approx(0.4)
    assert bound.high == pytest.approx(0.8)
    assert any("not a confidence interval" in a for a in bound.assumptions)


def test_the_bound_says_out_loud_that_a_future_cycle_can_escape_it():
    bound = sc.band_from_pairs(_four())
    assert any("fall outside this" in c for c in bound.caveats)


# ---- insufficient data must not become a bound -------------------------------------------


def test_no_pairs_yields_insufficient_and_points_at_the_worklist():
    bound = sc.band_from_pairs(pd.DataFrame(columns=sc.PAIR_COLUMNS))
    assert bound.status == sc.STATUS_INSUFFICIENT
    assert bound.low is None and bound.high is None
    assert any("worklist" in c for c in bound.caveats)


def test_too_few_pairs_yields_insufficient():
    bound = sc.band_from_pairs(_pairs([{"pair_id": "2017_2018"}, {"pair_id": "2019_2020"}]))
    assert bound.status == sc.STATUS_INSUFFICIENT
    assert bound.n_pairs == 2


def test_asking_an_insufficient_bound_for_factors_raises_rather_than_guessing():
    bound = sc.band_from_pairs(pd.DataFrame(columns=sc.PAIR_COLUMNS))
    with pytest.raises(sc.CalibrationError, match="worklist"):
        bound.as_factors()


def test_a_partial_compilation_names_the_pairs_still_missing():
    three = _pairs(
        [
            {"pair_id": p, "general_margin_swing": 0.05}
            for p in ("2017_2018", "2019_2020", "2021_2022")
        ]
    )
    bound = sc.band_from_pairs(three)
    assert bound.status == sc.STATUS_BOUND
    assert any("2023_2024" in c for c in bound.caveats)


# ---- every row sourced, exactly like the plan-version register ----------------------------


@pytest.mark.parametrize("field", ["source_url", "retrieved_on", "verified_by"])
def test_an_unsourced_or_unverified_pair_is_refused(field):
    with pytest.raises(sc.CalibrationError, match=f"empty {field}"):
        sc.calibration_pairs(_pairs([{field: ""}]))


def test_a_zero_overperformance_pair_is_refused_rather_than_dividing_by_zero():
    with pytest.raises(sc.CalibrationError, match="undefined"):
        sc.calibration_pairs(_pairs([{"specials_overperformance": 0.0}]))


def test_a_non_numeric_swing_is_refused():
    with pytest.raises(sc.CalibrationError, match="not numeric"):
        sc.calibration_pairs(_pairs([{"general_margin_swing": "about six points"}]))


# ---- the arithmetic ----------------------------------------------------------------------


def test_realised_shrinkage_is_general_swing_over_specials_overperformance():
    pairs = _pairs([{"specials_overperformance": 0.20, "general_margin_swing": 0.07}])
    assert sc.calibration_pairs(pairs)["realised_shrinkage"].iloc[0] == pytest.approx(0.35)


def test_the_bound_narrows_the_default_sweep_which_is_the_entire_point():
    """0.25-1.00 is the current assumption-driven sweep; a bound should be tighter."""
    bound = sc.band_from_pairs(_four())
    assert bound.low > 0.25 and bound.high < 1.00


def test_to_dict_round_trips_without_losing_the_status():
    d = sc.band_from_pairs(_four()).to_dict()
    assert d["status"] == sc.STATUS_BOUND and d["n_pairs"] == 4
    assert len(d["realised"]) == 4


# ---- the committed, half-compiled table ---------------------------------------------------


def test_the_committed_pairs_table_is_refused_until_the_specials_half_is_compiled():
    """general_margin_swing is derived from certified returns; the other half is a human task."""
    pairs = pd.read_csv("data/reference/shrinkage_calibration_pairs.csv")
    with pytest.raises(sc.CalibrationError, match="not yet compiled"):
        sc.calibration_pairs(pairs)


def test_the_committed_table_already_carries_sourced_general_swings():
    pairs = pd.read_csv("data/reference/shrinkage_calibration_pairs.csv")
    assert list(pairs["pair_id"]) == list(sc.EXPECTED_PAIRS)
    assert pairs["general_margin_swing"].notna().all()
    assert pairs["specials_overperformance"].isna().all()


def test_a_blank_cell_and_a_garbage_cell_are_reported_differently():
    """A to-do and a bug are different problems and must not share an error message."""
    with pytest.raises(sc.CalibrationError, match="not yet compiled"):
        sc.calibration_pairs(_pairs([{"general_margin_swing": ""}]))
    with pytest.raises(sc.CalibrationError, match="not numeric"):
        sc.calibration_pairs(_pairs([{"general_margin_swing": "about six points"}]))
