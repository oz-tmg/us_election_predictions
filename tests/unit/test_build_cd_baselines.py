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
    monkeypatch.setattr(
        bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (pd.DataFrame(), [])
    )
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
    _, report = bcb.build(Path("data/raw"), 2020, panel_path=tmp_path / "none.parquet")
    assert report["files_errored"] == 2
    assert {e["state"] for e in report["errors"]} == {"CA", "TX"}


def test_states_that_read_without_error_but_produced_no_rows_are_still_reported(monkeypatch, tmp_path):
    """The quiet failure: a file parses, yields nothing, and shortens the table unnoticed."""
    df = pd.DataFrame({"state_po": ["AZ"], "baseline_quality": ["ok"]})
    monkeypatch.setattr(
        bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (df, _stats(["AZ", "NV"], []))
    )
    _, report = bcb.build(Path("data/raw"), 2020, panel_path=tmp_path / "none.parquet")
    assert report["files_errored"] == 0
    assert report["states_missing"] == ["NV"]


def test_baseline_quality_is_carried_into_the_report(monkeypatch, tmp_path):
    df = pd.DataFrame(
        {"state_po": ["AZ", "AZ", "NV"], "baseline_quality": ["ok", "under_covered", "ok"]}
    )
    monkeypatch.setattr(
        bcb.cd_baseline, "build_cd_baselines", lambda *a, **k: (df, _stats(["AZ", "NV"], []))
    )
    _, report = bcb.build(Path("data/raw"), 2020, panel_path=tmp_path / "none.parquet")
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
    return pd.DataFrame(
        [{"cycle": cycle, "state_po": s, "two_party_dem_share": v} for s, v in rows]
    )


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


def test_a_state_absent_from_the_certified_panel_fails_rather_than_passing_by_default():
    """Unknown must never read as fine."""
    df, rep = bcb.reconcile(_cd("XX", 50, 100), _panel([("AZ", 0.50)]), 2020)
    assert rep["states_failing"] == ["XX"]
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
    _, report = bcb.build(Path("data/raw"), 2020, panel_path=tmp_path / "nope.parquet")
    assert "UNRECONCILED" in report["reconciliation"]["skipped"]
