"""The one-command daily capture, with a fake fetcher (no network, no production ledger)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from election_prediction.data import state_fetchers

SPEC = importlib.util.spec_from_file_location("capture_daily", Path("scripts/capture_daily.py"))
assert SPEC and SPEC.loader
capture_daily = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture_daily)

TODAY = datetime.now(UTC).date().isoformat()


def _fake_ma(labelled: str = "unknown"):
    def fetch(dest: Path) -> state_fetchers.FetchedRelease:
        path = dest / "MA_2026GE_SEN_1_by_town.csv"
        path.write_text(
            'City/Town,,,"Ann A","Bob B","All Others",Blanks,"Total Votes Cast"\n'
            ",,,Democratic,Republican\n"
            'TOTALS,,,"60,000","40,000",10,500,"100,510"\n'
        )
        return state_fetchers.FetchedRelease(
            "MA", path, "https://electionstats.state.ma.us/x", datetime.now(UTC).isoformat(), labelled
        )

    return fetch


def _broken(dest: Path) -> state_fetchers.FetchedRelease:
    raise RuntimeError("HTTP 403")


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setitem(state_fetchers.FETCHERS, "MA", _fake_ma())
    monkeypatch.setitem(state_fetchers.FETCHERS, "ZZ", _broken)
    universe = tmp_path / "seats.csv"
    pd.DataFrame(
        {"state_po": ["MA"], "office": ["us_senate"], "geography_id": ["state:25"], "district_num": [None]}
    ).to_csv(universe, index=False)
    return {
        "ledger_dir": tmp_path / "ledger",
        "evidence_dir": tmp_path / "evidence",
        "report_dir": tmp_path / "reports",
        "universe": universe,
    }


def test_capture_writes_one_snapshot_and_a_report(env: dict) -> None:
    report = capture_daily.run(states=["MA"], certified={}, dry_run=False, **env)
    assert report["seats"] == 1 and report["certified_seats"] == 0 and not report["failures"]
    snap = pd.read_csv(env["ledger_dir"] / f"snapshot={TODAY}.csv")
    assert snap.loc[0, "dem_votes"] == 60_000 and snap.loc[0, "certified"] in (False, "False")
    saved = json.loads((env["report_dir"] / f"capture_{TODAY}.json").read_text())
    assert saved["states"]["MA"]["sha256"]


def test_the_day_slot_is_checked_before_fetching(env: dict) -> None:
    capture_daily.run(states=["MA"], certified={}, dry_run=False, **env)
    with pytest.raises(SystemExit, match="slot is taken"):
        capture_daily.run(states=["MA"], certified={}, dry_run=False, **env)


def test_dry_run_leaves_the_ledger_and_reports_alone(env: dict) -> None:
    report = capture_daily.run(states=["MA"], certified={}, dry_run=True, **env)
    assert report["dry_run"] and not env["ledger_dir"].exists() and not env["report_dir"].exists()


def test_one_failing_state_does_not_lose_the_others(env: dict) -> None:
    report = capture_daily.run(states=["MA", "ZZ"], certified={}, dry_run=False, **env)
    assert set(report["states"]) == {"MA"} and "403" in report["failures"]["ZZ"]


def test_certified_needs_an_operator_flag_and_a_non_unofficial_release(
    env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = capture_daily.run(
        states=["MA"], certified={"MA": "https://sec.example/cert.pdf"}, dry_run=True, **env
    )
    assert report["certified_seats"] == 1
    monkeypatch.setitem(state_fetchers.FETCHERS, "MA", _fake_ma(labelled="unofficial"))
    with pytest.raises(SystemExit, match="nothing captured"):
        capture_daily.run(
            states=["MA"], certified={"MA": "https://sec.example/cert.pdf"}, dry_run=True, **env
        )


def test_incomplete_coverage_is_refused(env: dict) -> None:
    pd.DataFrame(
        {
            "state_po": ["MA", "MA"],
            "office": ["us_senate", "us_house"],
            "geography_id": ["state:25", "state:25|district:cong_01"],
            "district_num": [None, 1],
        }
    ).to_csv(env["universe"], index=False)
    with pytest.raises(SystemExit, match="coverage mismatch"):
        capture_daily.run(states=["MA"], certified={}, dry_run=True, **env)


def test_parse_certified_requires_https_evidence() -> None:
    assert capture_daily.parse_certified(["nc=https://ncsbe.gov/c"]) == {"NC": "https://ncsbe.gov/c"}
    with pytest.raises(SystemExit):
        capture_daily.parse_certified(["NC"])
