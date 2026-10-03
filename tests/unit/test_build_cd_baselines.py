"""CD presidential baselines as a build (F-002 at CD grain).

The module existed and had no caller, so the one gold file covered 8 states. These pin the
properties that stop a partial build from looking like a complete one.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from election_prediction import build_cd_baselines as bcb


def test_a_midterm_vintage_is_refused_rather_than_returning_nothing():
    """A midterm precinct drop has no president rows; an empty table would look like a hole."""
    with pytest.raises(ValueError, match="not a presidential cycle"):
        bcb.build(Path("data/raw"), 2022)


@pytest.mark.parametrize("vintage", bcb.PRESIDENTIAL_VINTAGES)
def test_presidential_vintages_are_accepted(vintage, monkeypatch):
    monkeypatch.setattr(bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (pd.DataFrame(), []))
    df, report = bcb.build(Path("data/raw"), vintage)
    assert report["vintage"] == vintage


def test_the_report_names_the_district_lines_the_build_is_on():
    """A 2020 build is on 2012-era lines by construction; a consumer needing 2022 is told."""
    import election_prediction.build_cd_baselines as m

    orig = m.cd_baseline.build_cd_baselines
    m.cd_baseline.build_cd_baselines = lambda *a, **k: (pd.DataFrame(), [])
    try:
        _, r2020 = m.build(Path("data/raw"), 2020)
        _, r2024 = m.build(Path("data/raw"), 2024)
    finally:
        m.cd_baseline.build_cd_baselines = orig
    assert r2020["district_lines"] == 2012
    assert r2024["district_lines"] == 2022


def _stats(ok_states, error_states):
    return [{"status": "ok", "state": s} for s in ok_states] + [
        {"status": "error", "state": s, "error": "ValueError: boom"} for s in error_states
    ]


def test_errored_states_are_named_not_merely_counted(monkeypatch, tmp_path):
    """A state missing from a national baseline is a silent join failure downstream."""
    df = pd.DataFrame({"state_po": ["AZ"], "baseline_quality": ["ok"]})
    monkeypatch.setattr(
        bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (df, _stats(["AZ"], ["CA", "TX"]))
    )
    _, report = bcb.build(
        Path("data/raw"),
        2020,
        panel_path=tmp_path / "none.parquet",
        house_path=tmp_path / "none.parquet",
    )
    assert report["files_errored"] == 2
    assert {e["state"] for e in report["errors"]} == {"CA", "TX"}


def test_states_that_read_without_error_but_produced_no_rows_are_still_reported(monkeypatch, tmp_path):
    """The quiet failure: a file parses, yields nothing, and shortens the table unnoticed."""
    df = pd.DataFrame({"state_po": ["AZ"], "baseline_quality": ["ok"]})
    monkeypatch.setattr(bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (df, _stats(["AZ", "NV"], [])))
    _, report = bcb.build(
        Path("data/raw"),
        2020,
        panel_path=tmp_path / "none.parquet",
        house_path=tmp_path / "none.parquet",
    )
    assert report["files_errored"] == 0
    assert report["states_missing"] == ["NV"]


def test_baseline_quality_is_carried_into_the_report(monkeypatch, tmp_path):
    df = pd.DataFrame({"state_po": ["AZ", "AZ", "NV"], "baseline_quality": ["ok", "under_covered", "ok"]})
    monkeypatch.setattr(bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (df, _stats(["AZ", "NV"], [])))
    _, report = bcb.build(
        Path("data/raw"),
        2020,
        panel_path=tmp_path / "none.parquet",
        house_path=tmp_path / "none.parquet",
    )
    assert report["baseline_quality"] == {"ok": 2, "under_covered": 1}
    assert report["districts"] == 3
    assert report["states_covered"] == 2


# ---- reconciliation gate ------------------------------------------------------------------
# This gate exists because a national run shipped MN and ND at 0.000 Democratic and the
# build reported "50 files ok". Counting rows is not validation.


def _cd(state, dem, two, quality="ok"):
    return pd.DataFrame(
        {"state_po": [state], "dem_votes": [dem], "two_party_votes": [two], "baseline_quality": [quality]}
    )


def _panel(rows, cycle=2020):
    return pd.DataFrame([{"cycle": cycle, "state_po": s, "two_party_dem_share": v} for s, v in rows])


def test_a_state_that_reconciles_keeps_its_quality_flag():
    df, rep = bcb.reconcile(_cd("AZ", 50, 100), _panel([("AZ", 0.50)]), 2020)
    assert rep["states_failing"] == []
    assert df["baseline_quality"].iloc[0] == "ok"
    assert bool(df["reconciles"].iloc[0]) is True


def test_the_minnesota_failure_mode_is_caught():
    """Zero Democratic votes against a certified 0.536 must not pass as data."""
    df, rep = bcb.reconcile(_cd("MN", 0, 100), _panel([("MN", 0.5364)]), 2020)
    assert rep["states_failing"] == ["MN"]
    assert df["baseline_quality"].iloc[0] == bcb.QUALITY_FAILS_RECONCILIATION


def test_failing_states_are_flagged_rather_than_dropped():
    """A short table invites a silent join; a flagged one forces a decision."""
    cd = pd.concat([_cd("AZ", 50, 100), _cd("MN", 0, 100)], ignore_index=True)
    df, _ = bcb.reconcile(cd, _panel([("AZ", 0.50), ("MN", 0.5364)]), 2020)
    assert len(df) == 2
    assert set(df["state_po"]) == {"AZ", "MN"}


def test_a_small_discrepancy_inside_tolerance_passes():
    """Split precincts are excluded rather than allocated, so exact equality is not the bar."""
    df, rep = bcb.reconcile(_cd("VA", 505, 1000), _panel([("VA", 0.50)]), 2020)
    assert rep["states_failing"] == []


def test_a_discrepancy_outside_tolerance_fails():
    df, rep = bcb.reconcile(_cd("WA", 526, 1000), _panel([("WA", 0.599)]), 2020)
    assert rep["states_failing"] == ["WA"]


def test_a_state_absent_from_the_certified_panel_does_not_pass_by_default():
    """Unknown must never read as fine -- but it is not the same claim as "disagrees".

    New York 2024 is the live case and it is nobody's bug. `data/quarantine.py` excludes a
    race whose candidate votes do not *exactly* equal its reported total, and New York's
    2024 files carry a `BLANK` ballot row the total excludes -- 874 votes in 8,381,429, or
    0.010%. So New York has no 2024 presidential row in silver and this gate has nothing to
    compare against, while its precinct file reconciles to 1.0025 of its own raw total.
    Calling that `fails_reconciliation` reads as an accusation against the precinct data.
    """
    df, rep = bcb.reconcile(_cd("XX", 50, 100), _panel([("AZ", 0.50)]), 2020)
    assert rep["states_failing"] == [], "absent is not disagreement"
    assert rep["states_without_a_comparator"] == ["XX"]
    assert df["baseline_quality"].iloc[0] == bcb.QUALITY_NO_COMPARATOR
    assert df["baseline_quality"].iloc[0] != "ok"


def test_a_state_that_disagrees_is_still_called_a_failure():
    """The distinction must not become an excuse: Indiana's gap is a real failure."""
    df, rep = bcb.reconcile(_cd("IN", 445, 1000), _panel([("IN", 0.418)]), 2020)
    assert rep["states_failing"] == ["IN"]
    assert rep["states_without_a_comparator"] == []
    assert df["baseline_quality"].iloc[0] == bcb.QUALITY_FAILS_RECONCILIATION


def test_the_report_names_the_worst_offenders_with_both_numbers():
    cd = pd.concat([_cd("AZ", 50, 100), _cd("MN", 0, 100)], ignore_index=True)
    _, rep = bcb.reconcile(cd, _panel([("AZ", 0.50), ("MN", 0.5364)]), 2020)
    worst = rep["worst"][0]
    assert worst["state_po"] == "MN"
    assert worst["cd_aggregate_share"] == 0.0
    assert worst["state_certified_share"] == 0.5364


def test_build_without_a_certified_panel_says_the_table_is_unreconciled(monkeypatch, tmp_path):
    monkeypatch.setattr(
        bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (_cd("AZ", 50, 100), _stats(["AZ"], []))
    )
    _, report = bcb.build(
        Path("data/raw"),
        2020,
        panel_path=tmp_path / "nope.parquet",
        house_path=tmp_path / "nope.parquet",
    )
    assert "UNRECONCILED" in report["reconciliation"]["skipped"]


# ---- under-coverage, measured against each district's own certified House return -----------
# This replaced an inference from the state median that produced four false positives
# (AZ-07, CA-21, TX-29, TX-33, all of which recover 99-102% of their certified House vote)
# and missed two real holes (NY-07 at 0.838, NJ-04 at 0.663).


def _house(rows, cycle=2020):
    return pd.DataFrame(
        [
            {
                "office": "us_house",
                "cycle": cycle,
                "state_po": s,
                "district_num": d,
                "candidatevotes": v,
            }
            for s, d, v in rows
        ]
    )


def _baseline(rows):
    return pd.DataFrame(
        [
            {"state_po": s, "district_num": d, "two_party_votes": v, "baseline_quality": q}
            for s, d, v, q in rows
        ]
    )


def test_a_district_short_of_its_certified_house_vote_is_flagged():
    df, rep = bcb.flag_under_covered(_baseline([("NJ", 4, 281373, "ok")]), _house([("NJ", 4, 424368)]), 2020)
    assert rep["districts_under_covered"] == 1
    assert df["baseline_quality"].iloc[0] == bcb.QUALITY_UNDER_COVERED
    assert df["coverage_vs_house_vote"].iloc[0] == pytest.approx(0.663, abs=1e-3)


def test_a_district_matching_its_certified_house_vote_is_left_alone():
    """TX-29's 0.525 of the state median was turnout, not a hole."""
    df, rep = bcb.flag_under_covered(
        _baseline([("TX", 29, 159166, "ok")]), _house([("TX", 29, 156473)]), 2020
    )
    assert rep["districts_under_covered"] == 0
    assert df["baseline_quality"].iloc[0] == "ok"


def test_an_uncontested_house_race_is_not_mistaken_for_missing_vote():
    """A low House total gives a *high* ratio, so the check is safe by direction."""
    df, rep = bcb.flag_under_covered(_baseline([("FL", 25, 300000, "ok")]), _house([("FL", 25, 100)]), 2020)
    assert rep["districts_under_covered"] == 0
    assert df["coverage_vs_house_vote"].iloc[0] > 1


def test_a_district_with_no_certified_house_return_is_not_condemned():
    """Unjudgeable is reported as unjudgeable, not as a failure."""
    df, rep = bcb.flag_under_covered(_baseline([("XX", 1, 1000, "ok")]), _house([("NJ", 4, 400000)]), 2020)
    assert rep["districts_unjudgeable"] == 1
    assert rep["districts_under_covered"] == 0
    assert df["baseline_quality"].iloc[0] == "ok"


def test_a_worse_flag_is_not_overwritten_by_under_coverage():
    """A state failing reconciliation is wrong at a scale that makes its districts moot."""
    df, _ = bcb.flag_under_covered(
        _baseline([("IN", 4, 114851, bcb.QUALITY_FAILS_RECONCILIATION)]),
        _house([("IN", 4, 338515)]),
        2020,
    )
    assert df["baseline_quality"].iloc[0] == bcb.QUALITY_FAILS_RECONCILIATION


def test_an_uncontested_seat_absent_from_the_drop_is_named():
    """FL-25 2020: Diaz-Balart ran unopposed, so no House rows, so no precinct resolved."""
    cov = bcb.district_coverage(
        _baseline([("FL", 24, 1, "ok"), ("FL", 26, 1, "ok")]),
        _house([("FL", 24, 1), ("FL", 25, 1), ("FL", 26, 1)]),
        2020,
    )
    assert cov["districts_missing"] == 1
    assert cov["missing_by_state"] == {"FL": [25]}


def test_the_dc_delegate_is_not_counted_as_a_missing_district():
    cov = bcb.district_coverage(_baseline([("FL", 24, 1, "ok")]), _house([("FL", 24, 1), ("DC", 0, 1)]), 2020)
    assert cov["districts_missing"] == 0


def test_a_district_with_zero_certified_house_vote_does_not_crash_the_build():
    """Louisiana 2024's all-party primary leaves a district with no certified House vote.

    Pandas evaluates nullable-integer arithmetic on the underlying data *including masked
    slots*, so `Int64.where(> 0)` still carries a literal 0 into the division and raises
    ZeroDivisionError. It killed the 2024 national build after forty minutes of work.
    """
    house = _house([("LA", 1, 0), ("NJ", 4, 424368)], cycle=2024)
    house["candidatevotes"] = house["candidatevotes"].astype("Int64")
    df, rep = bcb.flag_under_covered(
        _baseline([("LA", 1, 300000, "ok"), ("NJ", 4, 281373, "ok")]), house, 2024
    )
    assert rep["districts_unjudgeable"] == 1
    assert rep["districts_under_covered"] == 1
    by_state = df.set_index("state_po")["baseline_quality"]
    assert by_state["LA"] == "ok", "unjudgeable is not a failure"
    assert by_state["NJ"] == bcb.QUALITY_UNDER_COVERED


# ---- vote-total reconciliation, which the share gate cannot do ----------------------------
# New Jersey 2024 is why this exists. Its file mixes two geographic levels -- Bergen County
# publishes 562 real precinct rows with mode breakdowns and a matching TOTAL, plus 144
# municipality rows carrying only a TOTAL, the same 241,958 votes again -- so the state lands
# 13.4% over certified while its *share* is within 0.4%. A share-only gate passes it.


def _pres(rows, cycle=2024):
    return pd.DataFrame(
        [
            {
                "office": "president",
                "cycle": cycle,
                "state_po": s,
                "party_simplified": p,
                "candidatevotes": v,
            }
            for s, p, v in rows
        ]
    )


def test_a_proportional_duplication_is_caught_by_the_total_and_missed_by_the_share():
    """Both parties doubled: the share is identical, the total is twice what it should be."""
    cd = pd.DataFrame(
        [
            {
                "state_po": "NJ",
                "district_num": 1,
                "dem_votes": 1060.0,
                "rep_votes": 940.0,
                "two_party_votes": 2000.0,
                "baseline_quality": "ok",
            }
        ]
    )
    certified = _pres([("NJ", "DEMOCRAT", 530), ("NJ", "REPUBLICAN", 470)])

    # The share gate sees nothing wrong.
    _, share_rep = bcb.reconcile(cd, _panel([("NJ", 0.53)], cycle=2024), 2024)
    assert share_rep["states_failing"] == []

    # The total gate does.
    out, rep = bcb.flag_vote_total_mismatch(cd, certified, 2024)
    assert rep["states_failing"] == ["NJ"]
    assert out["baseline_quality"].iloc[0] == bcb.QUALITY_FAILS_VOTE_TOTAL
    assert out["vote_total_ratio"].iloc[0] == pytest.approx(2.0)


def test_a_state_within_tolerance_keeps_its_flag():
    """New York 2020's 0.25% is the largest benign deviation measured; it must pass."""
    cd = pd.DataFrame(
        [
            {
                "state_po": "NY",
                "district_num": 1,
                "dem_votes": 602.0,
                "rep_votes": 400.0,
                "two_party_votes": 1002.0,
                "baseline_quality": "ok",
            }
        ]
    )
    out, rep = bcb.flag_vote_total_mismatch(
        cd, _pres([("NY", "DEMOCRAT", 600), ("NY", "REPUBLICAN", 400)]), 2024
    )
    assert rep["states_failing"] == []
    assert out["baseline_quality"].iloc[0] == "ok"


def test_a_state_with_no_certified_total_keeps_what_reconcile_already_said():
    cd = pd.DataFrame(
        [
            {
                "state_po": "NY",
                "district_num": 1,
                "dem_votes": 1.0,
                "rep_votes": 1.0,
                "two_party_votes": 2.0,
                "baseline_quality": bcb.QUALITY_NO_COMPARATOR,
            }
        ]
    )
    out, rep = bcb.flag_vote_total_mismatch(cd, _pres([("NJ", "DEMOCRAT", 1), ("NJ", "REPUBLICAN", 1)]), 2024)
    assert rep["states_failing"] == []
    assert out["baseline_quality"].iloc[0] == bcb.QUALITY_NO_COMPARATOR


def test_a_share_failure_outranks_a_total_failure():
    """If the share is wrong the baseline itself is wrong, which is the worse claim."""
    cd = pd.DataFrame(
        [
            {
                "state_po": "IN",
                "district_num": 1,
                "dem_votes": 2000.0,
                "rep_votes": 2000.0,
                "two_party_votes": 4000.0,
                "baseline_quality": bcb.QUALITY_FAILS_RECONCILIATION,
            }
        ]
    )
    out, _ = bcb.flag_vote_total_mismatch(
        cd, _pres([("IN", "DEMOCRAT", 500), ("IN", "REPUBLICAN", 500)]), 2024
    )
    assert out["baseline_quality"].iloc[0] == bcb.QUALITY_FAILS_RECONCILIATION


def test_the_total_gate_is_skipped_rather_than_guessed_without_certified_returns():
    cd = pd.DataFrame(
        [
            {
                "state_po": "NJ",
                "district_num": 1,
                "dem_votes": 1.0,
                "rep_votes": 1.0,
                "two_party_votes": 2.0,
                "baseline_quality": "ok",
            }
        ]
    )
    out, rep = bcb.flag_vote_total_mismatch(cd, _pres([], cycle=2024), 2024)
    assert "skipped" in rep
    assert out["baseline_quality"].iloc[0] == "ok"
