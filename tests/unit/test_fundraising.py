"""F-004: the party receipts ratio, its smoothing, and its two leakage guards."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from election_prediction.features import fundraising as fr


def _totals(rows: list[dict]) -> pd.DataFrame:
    base = {
        "candidate_id": "H0GA01001",
        "fec_name": "DOE, JANE",
        "office": "us_house",
        "state_po": "GA",
        "district_num": 1,
        "fec_party": "DEM",
        "election_year": 2024,
        "cycle": 2024,
        "receipts": 1_000_000.0,
        "coverage_end_date": "2024-09-30",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def _pair(d: float, r: float, dem: dict | None = None, rep: dict | None = None) -> pd.DataFrame:
    return _totals(
        [
            {"candidate_id": "D1", "fec_party": "DEM", "receipts": d, **(dem or {})},
            {"candidate_id": "R1", "fec_party": "REP", "receipts": r, **(rep or {})},
        ]
    )


# --------------------------------------------------------------------- election day
@pytest.mark.parametrize(
    "cycle,expected",
    [
        (1988, dt.date(1988, 11, 8)),
        (2020, dt.date(2020, 11, 3)),
        (2022, dt.date(2022, 11, 8)),
        (2024, dt.date(2024, 11, 5)),
        (2026, dt.date(2026, 11, 3)),
    ],
)
def test_election_day_is_the_tuesday_after_the_first_monday(cycle, expected):
    assert fr.election_day(cycle) == expected


def test_a_november_first_monday_does_not_become_election_day():
    """2021-11-01 is itself a Monday; the answer is the 2nd, not the 1st."""
    assert fr.election_day(2021) == dt.date(2021, 11, 2)


# ------------------------------------------------------------------------ the ratio
def test_an_equal_race_has_a_zero_log_ratio_and_a_half_share():
    out = fr.build_fundraising(_pair(1_000_000, 1_000_000))
    assert out.iloc[0]["log_receipt_ratio"] == pytest.approx(0.0)
    assert out.iloc[0]["dem_receipt_share"] == pytest.approx(0.5)


def test_the_encoding_is_symmetric_under_swapping_the_parties():
    """A 2:1 Democratic edge and a 2:1 Republican one must be equal and opposite."""
    d = fr.build_fundraising(_pair(2_000_000, 1_000_000)).iloc[0]["log_receipt_ratio"]
    r = fr.build_fundraising(_pair(1_000_000, 2_000_000)).iloc[0]["log_receipt_ratio"]
    assert d == pytest.approx(-r)
    assert d > 0, "the Democratic advantage is the positive direction"


def test_the_feature_is_scale_free_across_eras():
    """Nominal dollars are not comparable across 1980-2026; the ratio is the point."""
    small = fr.build_fundraising(_pair(200_000, 100_000)).iloc[0]["log_receipt_ratio"]
    large = fr.build_fundraising(_pair(20_000_000, 10_000_000)).iloc[0]["log_receipt_ratio"]
    assert small == pytest.approx(large, abs=0.05)


def test_a_shutout_race_stays_finite_rather_than_infinite():
    out = fr.build_fundraising(_pair(5_000_000, 0.0))
    assert np.isfinite(out.iloc[0]["log_receipt_ratio"])
    assert out.iloc[0]["log_receipt_ratio"] == pytest.approx(np.log(5_010_000 / fr.RECEIPTS_SMOOTHING))


def test_a_trivially_funded_opponent_cannot_dominate_the_feature():
    """$200 raised must not read as a 5000:1 advantage; smoothing caps it."""
    tiny = fr.build_fundraising(_pair(1_000_000, 200.0)).iloc[0]["log_receipt_ratio"]
    assert tiny < np.log(1_000_000 / 200)


# ------------------------------------------------------------- the nominee proxy
def test_the_nominee_is_proxied_by_the_partys_top_fundraiser():
    """The endpoint lists primary losers too, so a party sum overstates the nominee."""
    out = fr.build_fundraising(
        _totals(
            [
                {"candidate_id": "D1", "fec_party": "DEM", "receipts": 900_000},
                {"candidate_id": "D2", "fec_party": "DEM", "receipts": 300_000},
                {"candidate_id": "R1", "fec_party": "REP", "receipts": 1_000_000},
            ]
        )
    )
    row = out.iloc[0]
    assert row["dem_top_candidate_id"] == "D1"
    assert row["dem_top_receipts"] == 900_000
    assert row["dem_receipts"] == 1_200_000, "the party sum stays for audit"
    assert row["dem_candidates"] == 2
    assert row["log_receipt_ratio"] < 0, "the ratio uses the proxy, not the sum"


def test_a_minor_party_filer_does_not_enter_either_side():
    out = fr.build_fundraising(
        _totals(
            [
                {"candidate_id": "D1", "fec_party": "DEM", "receipts": 1_000_000},
                {"candidate_id": "R1", "fec_party": "REP", "receipts": 1_000_000},
                {"candidate_id": "L1", "fec_party": "LIB", "receipts": 50_000},
            ]
        )
    )
    assert out.iloc[0]["dem_candidates"] == 1 and out.iloc[0]["rep_candidates"] == 1
    assert out.iloc[0]["log_receipt_ratio"] == pytest.approx(0.0)


# ---------------------------------------------------------------------- usability
def test_a_one_party_race_is_unusable_with_a_stated_reason():
    out = fr.build_fundraising(_totals([{"candidate_id": "D1", "fec_party": "DEM"}]))
    assert not out.iloc[0]["usable"]
    assert "no filer" in out.iloc[0]["unusable_reason"]


def test_misaligned_coverage_windows_make_a_race_unusable():
    """coverage_end_date is per candidate: December receipts vs September receipts."""
    out = fr.build_fundraising(
        _pair(1_000_000, 1_000_000, dem={"coverage_end_date": "2024-12-31"}, rep={"coverage_end_date": "2024-06-30"})
    )
    row = out.iloc[0]
    assert row["coverage_gap_days"] > fr.MAX_COVERAGE_GAP_DAYS
    assert not row["coverage_aligned"] and not row["usable"]
    assert "coverage windows differ" in row["unusable_reason"]


def test_a_missing_coverage_window_is_unusable_not_assumed_aligned():
    out = fr.build_fundraising(_pair(1_000_000, 1_000_000, rep={"coverage_end_date": ""}))
    assert not out.iloc[0]["usable"]
    assert "coverage window is missing" in out.iloc[0]["unusable_reason"]


def test_post_election_coverage_is_flagged_because_it_leaks_the_outcome():
    """Winners raise after election day to retire debt; that inflates a backtest only."""
    out = fr.build_fundraising(
        _pair(1_000_000, 1_000_000, dem={"coverage_end_date": "2024-12-31"}, rep={"coverage_end_date": "2024-12-31"})
    )
    assert out.iloc[0]["post_election_coverage"]
    assert fr.validate_fundraising(out)["coverage.rows_post_election"] == 1


def test_a_pre_election_window_is_not_flagged():
    out = fr.build_fundraising(_pair(1_000_000, 1_000_000))
    assert not out.iloc[0]["post_election_coverage"]
    assert out.iloc[0]["usable"]


# ------------------------------------------------------------------------- shape
def test_a_senate_race_carries_no_district():
    """Keeping FEC's 00 would distinguish a state's two Senate classes by nothing."""
    out = fr.build_fundraising(
        _pair(1_000_000, 1_000_000, dem={"office": "us_senate", "district_num": 0}, rep={"office": "us_senate", "district_num": 0})
    )
    assert pd.isna(out.iloc[0]["district_num"])


def test_one_row_per_seat_cycle():
    frames = pd.concat(
        [
            _pair(1_000_000, 1_000_000),
            _pair(1_000_000, 1_000_000, dem={"district_num": 2}, rep={"district_num": 2}),
            _pair(1_000_000, 1_000_000, dem={"election_year": 2022}, rep={"election_year": 2022}),
        ],
        ignore_index=True,
    )
    out = fr.build_fundraising(frames)
    rep = fr.validate_fundraising(out)
    assert rep["ok"] and rep["rows"] == 3 and rep["keys.one_row_per_seat"]


def test_the_summary_carries_the_endogeneity_caveat():
    """The feature must not travel without the warning that it partly measures the outcome."""
    s = fr.fundraising_summary(fr.build_fundraising(_pair(2_000_000, 1_000_000)))
    assert s["usable_rows"] == 1 and s["cycles"] == [2024]
    assert any("endogenous" in c for c in s["caveats"])
    assert any("post_election_coverage" in c for c in s["caveats"])


def test_validation_catches_a_proxy_larger_than_its_party_total():
    out = fr.build_fundraising(_pair(1_000_000, 1_000_000))
    out.loc[0, "dem_top_receipts"] = 9_000_000.0
    assert not fr.validate_fundraising(out)["receipts.top_within_party_total"]
