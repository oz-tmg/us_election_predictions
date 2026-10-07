"""Capturing 2026 results as they certify (step 1 of the post-election path).

The registration pre-committed to "a seat with no certified result by ``as_of`` is excluded
and counted". That needs to know *which* seats were certified on a given date, which is
observable only while it happens — a state's canvass page shows today, not last week. These
pin the properties that make the ledger an accumulated observation rather than a
reconstruction.
"""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.data import results_2026 as r26


def _rows(seats, certified=True, retrieved="2026-11-05", url="https://sos.example/canvass"):
    return pd.DataFrame(
        [
            {
                "state_po": s,
                "district_num": d,
                "office": "us_house",
                "dem_votes": dv,
                "rep_votes": rv,
                "other_votes": 0,
                "certified": certified,
                "source_url": url,
                "retrieved_on": retrieved,
            }
            for s, d, dv, rv in seats
        ]
    )


def test_a_row_without_provenance_is_refused():
    """Provenance *is* the validation: there is no upstream checksum for a compiled table."""
    bad = _rows([("VA", 1, 100, 100)])
    bad.loc[0, "source_url"] = ""
    with pytest.raises(r26.SnapshotRejected, match="source_url"):
        r26.validate_snapshot(bad)


def test_a_snapshot_is_never_overwritten(tmp_path):
    """A snapshot records what was true on its date; replacing it rewrites the evidence."""
    r26.write_snapshot(_rows([("VA", 1, 100, 100)]), observed_on="2026-11-05", directory=tmp_path)
    with pytest.raises(r26.SnapshotRejected, match="already exists"):
        r26.write_snapshot(_rows([("VA", 1, 110, 100)]), observed_on="2026-11-05", directory=tmp_path)


def test_certified_on_is_the_earliest_snapshot_that_saw_it_certified(tmp_path):
    """Taking the latest would date every certification to whenever the ledger was last
    touched, which makes ``as_of`` a free parameter by the back door."""
    r26.write_snapshot(
        _rows([("VA", 1, 100, 90)], certified=False), observed_on="2026-11-05", directory=tmp_path
    )
    r26.write_snapshot(
        _rows([("VA", 1, 101, 90)], certified=True), observed_on="2026-11-12", directory=tmp_path
    )
    r26.write_snapshot(
        _rows([("VA", 1, 102, 90)], certified=True), observed_on="2026-11-20", directory=tmp_path
    )
    ledger = r26.certification_ledger(r26.read_snapshots(tmp_path))
    assert len(ledger) == 1
    assert ledger["certified_on"].iloc[0] == "2026-11-12", "first certified, not last observed"
    assert int(ledger["dem_votes"].iloc[0]) == 102, "but the votes are the latest count"


def test_a_seat_never_certified_carries_a_null_so_the_scorer_leaves_it_unscored(tmp_path):
    r26.write_snapshot(
        _rows([("GA", 2, 100, 90)], certified=False), observed_on="2026-11-05", directory=tmp_path
    )
    ledger = r26.certification_ledger(r26.read_snapshots(tmp_path))
    assert pd.isna(ledger["certified_on"].iloc[0])


def test_the_actual_frame_is_two_party_and_keyed_the_way_the_forecast_is():
    ledger = pd.DataFrame(
        [
            {
                "state_po": "VA",
                "district_num": 11,
                "office": "us_house",
                "dem_votes": 70,
                "rep_votes": 30,
                "other_votes": 500,
                "certified_on": "2026-11-16",
            }
        ]
    )
    out = r26.to_actual(ledger, state_fips={"VA": "51"})
    assert out["geography_id"].iloc[0] == "state:51|district:cong_11"
    assert out["actual_dem_share"].iloc[0] == pytest.approx(0.70), "third parties excluded"
    assert set(r26.ACTUAL_COLUMNS) <= set(out.columns)


def test_duplicated_seats_in_one_snapshot_are_refused():
    with pytest.raises(r26.SnapshotRejected, match="duplicated"):
        r26.validate_snapshot(_rows([("VA", 1, 10, 10), ("VA", 1, 20, 20)]))


def test_the_actual_columns_match_what_the_scorer_declares():
    """A parallel vocabulary here would be a join failure on election night."""
    from election_prediction.evaluation import score_preregistration as sp

    assert r26.ACTUAL_COLUMNS == sp.ACTUAL_COLUMNS


def test_a_senate_seat_is_keyed_at_state_level_not_by_district():
    """The seal keys a Senate seat on ``state:02``; building the district form joins to
    nothing, which would silently leave 33 of its 468 seats unscored."""
    ledger = pd.DataFrame(
        [
            {
                "state_po": "AK",
                "district_num": None,
                "office": "us_senate",
                "dem_votes": 40,
                "rep_votes": 60,
                "other_votes": 0,
                "certified_on": "2026-11-20",
            }
        ]
    )
    out = r26.to_actual(ledger, state_fips={"AK": "02"})
    assert out["geography_id"].iloc[0] == "state:02"
    assert out["actual_dem_share"].iloc[0] == pytest.approx(0.40)


def test_the_office_decides_the_key_not_the_presence_of_a_district_number():
    assert r26.geography_id("51", 11, "us_house") == "state:51|district:cong_11"
    assert r26.geography_id("02", None, "us_senate") == "state:02"
    assert r26.geography_id("02", 1, "us_senate") == "state:02", "office wins over a stray number"
