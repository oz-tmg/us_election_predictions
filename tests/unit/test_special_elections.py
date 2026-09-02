"""Hand-compiled special elections: provenance gates and the overperformance metric."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.data import special_elections as se


def _row(**over) -> dict:
    base = {
        "special_id": "s1",
        "election_date": "2025-03-11",
        "state_po": "GA",
        "office": "state_house",
        "district": "017",
        "dem_votes": 5000,
        "rep_votes": 4000,
        "other_votes": 0,
        "baseline_dem_share": 0.40,
        "baseline_source": "tracker X",
        "baseline_cycle": 2024,
        "source_url": "https://sos.example.gov/r",
        "retrieved_on": "2026-09-01",
        "notes": "",
    }
    return {**base, **over}


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=se.SPECIAL_COLUMNS)


def test_a_clean_table_validates():
    assert se.validate_specials(_frame([_row()]))["ok"]


def test_an_empty_table_validates_as_structurally_clean():
    """Empty is not invalid — it is the starting state of a compilation."""
    assert se.validate_specials(se.empty_frame())["ok"]


@pytest.mark.parametrize("field", ["source_url", "retrieved_on", "baseline_source"])
def test_a_row_without_provenance_is_rejected(field):
    """Hand-entered data has no upstream checksum; the citation is the only control."""
    rep = se.validate_specials(_frame([_row(**{field: ""})]))
    assert not rep["ok"]


def test_duplicate_ids_and_implausible_totals_are_rejected():
    assert not se.validate_specials(_frame([_row(), _row()]))["ok"]
    assert not se.validate_specials(_frame([_row(dem_votes=5, rep_votes=4)]))["ok"]


def test_future_dated_and_unknown_office_rows_are_rejected():
    assert not se.validate_specials(_frame([_row(election_date="2099-01-01")]))["ok"]
    assert not se.validate_specials(_frame([_row(office="dogcatcher")]))["ok"]


def test_overperformance_is_margin_relative_to_the_presidential_baseline():
    """D wins 5000-4000 (margin +0.111) in a seat Trump-era baseline puts at 40% D."""
    out = se.compute_overperformance(_frame([_row()]))
    r = out.iloc[0]
    assert r["special_margin"] == pytest.approx((5000 - 4000) / 9000)
    assert r["baseline_margin"] == pytest.approx(-0.20)  # 0.40 two-party share
    assert r["overperformance"] == pytest.approx(r["special_margin"] + 0.20)
    assert r["overperformance"] > 0, "running ahead of baseline is positive overperformance"


def test_a_seat_matching_its_baseline_shows_zero_overperformance():
    out = se.compute_overperformance(_frame([_row(dem_votes=4000, rep_votes=6000, baseline_dem_share=0.40)]))
    assert out.iloc[0]["overperformance"] == pytest.approx(0.0)


def test_environment_estimate_refuses_to_average_too_few_specials():
    out = se.compute_overperformance(_frame([_row(special_id=f"s{i}") for i in range(3)]))
    est = se.national_environment_estimate(out)
    assert est["status"] == "insufficient_data"
    assert "mean_overperformance" not in est


def test_environment_estimate_reports_spread_and_caveats():
    rows = [_row(special_id=f"s{i}", dem_votes=5000 + 100 * i) for i in range(8)]
    est = se.national_environment_estimate(se.compute_overperformance(_frame(rows)))
    assert est["status"] == "ok" and est["n"] == 8
    assert est["std_error"] > 0
    assert any("non-random" in c for c in est["caveats"])
