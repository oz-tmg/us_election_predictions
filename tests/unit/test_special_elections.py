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
        "contest_format": "single_round",
        "dem_votes": 5000,
        "rep_votes": 4000,
        "other_votes": 0,
        "baseline_dem_share": 0.40,
        "baseline_source": "tracker X",
        "baseline_cycle": 2024,
        "baseline_two_party_votes": None,
        "include_in_metric": "Y",
        "exclusion_reason": "",
        "source_url": "https://sos.example.gov/r",
        "retrieved_on": "2026-09-01",
        "results_updated_on": "",
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


def test_a_same_party_runoff_cannot_enter_the_metric():
    """D-vs-D runoff: rep_votes is zero by ballot construction, so the margin is +1
    regardless of preference. TX-18 scored +59.6 points of fake overperformance."""
    rep = se.validate_specials(_frame([_row(dem_votes=61845, rep_votes=0, baseline_dem_share=0.702)]))
    assert not rep["ok"]
    assert not rep["votes.both_parties_contested"]
    assert rep["votes.rows_one_sided_but_included"] == 1


def test_a_one_sided_row_may_be_recorded_if_explicitly_excluded():
    row = _row(dem_votes=61845, rep_votes=0, include_in_metric="N", exclusion_reason="D-vs-D runoff")
    assert se.validate_specials(_frame([row]))["ok"]


def test_an_exclusion_without_a_reason_is_rejected():
    rep = se.validate_specials(_frame([_row(include_in_metric="N", exclusion_reason="")]))
    assert not rep["ok"]
    assert not rep["exclusion.reason_given"]


def test_an_unknown_contest_format_is_rejected():
    assert not se.validate_specials(_frame([_row(contest_format="jungle")]))["ok"]


def test_excluded_rows_are_dropped_from_the_estimate_and_reported():
    rows = [_row(special_id=f"s{i}", dem_votes=5000 + 100 * i) for i in range(6)]
    rows.append(_row(special_id="drop", dem_votes=9999, include_in_metric="N", exclusion_reason="runoff"))
    est = se.national_environment_estimate(se.compute_overperformance(_frame(rows)))
    assert est["n"] == 6, "the excluded row must not be averaged"
    assert est["excluded"] == {"drop": "runoff"}


def test_turnout_ratio_compares_the_special_to_presidential_turnout():
    out = se.compute_overperformance(_frame([_row(baseline_two_party_votes=90000)]))
    assert out.iloc[0]["turnout_ratio"] == pytest.approx(9000 / 90000)


def test_a_table_predating_the_governance_columns_still_loads():
    """with_defaults keeps older compilations readable rather than failing the schema."""
    legacy = pd.DataFrame([_row()]).drop(columns=["contest_format", "include_in_metric", "exclusion_reason"])
    assert se.validate_specials(legacy)["ok"]


def test_one_seat_cannot_feed_the_metric_twice():
    """GA-14 filed a first round and a runoff. Both are valid rows; only one may average."""
    rounds = [
        _row(special_id="ga14-r1", state_po="GA", district="14", contest_format="all_party_first_round"),
        _row(special_id="ga14-runoff", state_po="GA", district="14", contest_format="runoff"),
    ]
    rep = se.validate_specials(_frame(rounds))
    assert not rep["ok"]
    assert not rep["keys.one_included_row_per_seat"]
    assert rep["keys.seats_double_counted"] == ["GA|state_house|14"]


def test_recording_the_superseded_round_is_allowed():
    rounds = [
        _row(special_id="ga14-r1", district="14", include_in_metric="N", exclusion_reason="superseded"),
        _row(special_id="ga14-runoff", district="14", contest_format="runoff"),
    ]
    assert se.validate_specials(_frame(rounds))["ok"]


def test_results_updated_on_must_not_predate_its_election():
    """The live slip: a runoff row inherited the first round's revision date."""
    rep = se.validate_specials(_frame([_row(election_date="2026-04-07", results_updated_on="2026-03-19")]))
    assert not rep["ok"]
    assert not rep["dates.results_updated_after_election"]


def test_results_updated_on_is_optional_but_must_parse():
    assert se.validate_specials(_frame([_row(results_updated_on="")]))["ok"]
    assert not se.validate_specials(_frame([_row(results_updated_on="last Tuesday")]))["ok"]


def test_the_implied_national_share_is_never_presented_as_calibrated():
    """shrinkage is an assumption; the status must stop a consumer treating it as fitted."""
    rows = [_row(special_id=f"s{i}", dem_votes=5000 + 100 * i) for i in range(8)]
    est = se.national_environment_estimate(se.compute_overperformance(_frame(rows)))
    out = se.implied_national_dem_share(est, baseline_national_dem_share=0.4922, shrinkage=0.5)
    assert out["status"] == "uncalibrated"
    assert any("shrinkage is an assumption" in c for c in out["caveats"])


def test_overperformance_is_halved_because_it_is_a_margin():
    est = {"status": "ok", "n": 8, "mean_overperformance": 0.20, "std_error": 0.02}
    out = se.implied_national_dem_share(est, baseline_national_dem_share=0.50, shrinkage=1.0)
    assert out["national_dem_share"] == pytest.approx(0.60)


def test_the_sensitivity_sweep_spans_the_shrinkage_band():
    est = {"status": "ok", "n": 8, "mean_overperformance": 0.1877, "std_error": 0.022}
    sweep = se.shrinkage_sensitivity(est, baseline_national_dem_share=0.4922)
    assert len(sweep) == len(se.SHRINKAGE_SENSITIVITY)
    assert sweep["national_dem_share"].is_monotonic_increasing


def test_an_unusable_estimate_does_not_yield_a_national_share():
    out = se.implied_national_dem_share(
        {"status": "insufficient_data", "reason": "too few"}, baseline_national_dem_share=0.49
    )
    assert out["status"] == "unavailable"
    assert "national_dem_share" not in out
