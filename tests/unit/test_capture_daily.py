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
    monkeypatch.setitem(state_fetchers.FETCHERS, "YY", _broken)
    catalog = pd.DataFrame(
        {
            "state_po": ["MA", "ZZ", "YY"],
            "extraction_status": ["parser_tested_2024", "parser_cross_checked_2026", "manual_review_pending"],
        }
    )
    monkeypatch.setattr(capture_daily.results_sources, "load_catalog", lambda: catalog)
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
    assert saved["states"]["MA"]["releases"][0]["sha256"]


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


def test_a_later_release_replaces_the_same_race_and_keeps_its_own_source(
    env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def two_releases(dest: Path) -> list[state_fetchers.FetchedRelease]:
        out = []
        for i, (dem, tag) in enumerate(((60_000, "general"), (61_000, "recount"))):
            path = dest / f"MA_2026GE_SEN_{tag}_{i}.csv"
            path.write_text(
                'City/Town,,,"Ann A","Bob B","All Others",Blanks,"Total Votes Cast"\n'
                ",,,Democratic,Republican\n"
                f'TOTALS,,,"{dem}","40,000",10,500,"1"\n'
            )
            out.append(
                state_fetchers.FetchedRelease(
                    "MA",
                    path,
                    f"https://electionstats.state.ma.us/{tag}",
                    datetime.now(UTC).isoformat(),
                    "unknown",
                )
            )
        return out

    monkeypatch.setitem(state_fetchers.FETCHERS, "MA", two_releases)
    report = capture_daily.run(states=["MA"], certified={}, dry_run=False, **env)
    snap = pd.read_csv(env["ledger_dir"] / f"snapshot={TODAY}.csv")
    assert len(snap) == 1 and snap.loc[0, "dem_votes"] == 61_000
    assert snap.loc[0, "source_url"].endswith("/recount")
    assert len(report["states"]["MA"]["releases"]) == 2


def test_a_parser_without_a_recorded_check_is_not_captured(env: dict) -> None:
    report = capture_daily.run(states=["MA", "YY"], certified={}, dry_run=False, **env)
    assert set(report["states"]) == {"MA"} and "no recorded test" in report["failures"]["YY"]
    assert report["states"]["MA"]["parser_status"] == "parser_tested_2024"


def test_an_attested_certification_carries_into_later_captures(env: dict, tmp_path: Path) -> None:
    book = tmp_path / "certifications.csv"
    first = capture_daily.run(
        states=["MA"],
        certified={"MA": "https://example.gov/canvass"},
        dry_run=False,
        observed_on="2026-11-20",
        attestations=book,
        **env,
    )
    assert first["certified_seats"] == 1 and not first["states"]["MA"]["certification_carried_forward"]
    assert pd.read_csv(book).to_dict("records") == [
        {
            "state_po": "MA",
            "certification_evidence": "https://example.gov/canvass",
            "first_captured_on": "2026-11-20",
        }
    ]
    # The next day's plain run must not record the seat as uncertified (a revocation).
    later = capture_daily.run(
        states=["MA"], certified={}, dry_run=False, observed_on="2026-11-21", attestations=book, **env
    )
    assert later["certified_seats"] == 1 and later["states"]["MA"]["certification_carried_forward"]
    snap = pd.read_csv(env["ledger_dir"] / "snapshot=2026-11-21.csv")
    assert str(snap.loc[0, "certified"]) == "True"
    assert len(pd.read_csv(book)) == 1


def test_a_dry_run_or_failed_state_records_no_attestation(env: dict, tmp_path: Path) -> None:
    book = tmp_path / "certifications.csv"
    capture_daily.run(
        states=["MA"], certified={"MA": "https://example.gov/canvass"}, dry_run=True, attestations=book, **env
    )
    assert not book.exists()
    capture_daily.run(
        states=["MA", "ZZ"],
        certified={"ZZ": "https://example.gov/zz"},
        dry_run=False,
        attestations=book,
        **env,
    )
    assert not book.exists()


def test_the_committed_attestations_cover_every_state_a_capture_index_certified() -> None:
    book = capture_daily.load_attestations(capture_daily.ATTESTATIONS)
    indexed = {
        state
        for path in Path("reports/captures").glob("capture_*.json")
        for state, info in json.loads(path.read_text())["states"].items()
        if info["certified"]
    }
    assert indexed and indexed <= set(book.state_po)
