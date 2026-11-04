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


def test_third_party_winner_is_not_inferred_from_two_party_share():
    ledger = _rows([("VA", 1, 600, 400)])
    ledger["other_votes"] = 700
    ledger["certified_on"] = "2026-11-20"
    with pytest.raises(r26.SnapshotRejected, match="winner_party"):
        r26.to_actual(ledger, state_fips={"VA": "51"})
    ledger["winner_party"] = "OTHER"
    actual = r26.to_actual(ledger, state_fips={"VA": "51"})
    assert actual.actual_dem_share.iloc[0] == 0.6
    assert not actual.actual_dem_win.iloc[0]


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
                "winner_party": "OTHER",
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


def test_capture_reload_actual_and_score_preserves_both_chambers(tmp_path):
    from election_prediction import build_results_2026 as cli
    from election_prediction.evaluation import score_preregistration as scoring

    rows = _rows([("VA", 11, 70, 30), ("AK", None, 40, 60)], retrieved="2026-11-12")
    rows.loc[1, "office"] = "us_senate"
    incoming = tmp_path / "incoming.csv"
    rows.to_csv(incoming, index=False)
    directory = tmp_path / "snapshots"
    assert (
        cli.main(
            [
                "capture",
                "--snapshot",
                str(incoming),
                "--directory",
                str(directory),
                "--observed-on",
                "2026-11-12",
            ]
        )
        == 0
    )
    output = tmp_path / "actual.csv"
    assert (
        cli.main(["actual", "--directory", str(directory), "--out", str(output), "--as-of", "2026-11-12"])
        == 0
    )
    actual = pd.read_csv(output)
    assert set(actual["geography_id"]) == {"state:51|district:cong_11", "state:02"}
    registration = scoring.load_registration("reports/preregistration_2026-11-03.json")
    report = scoring.score(scoring.ScoringInputs(registration, actual, "2026-11-12", {}))
    assert report["audit"]["scored"] == 2
    assert report["registration"]["seal_verified"]
    assert report["failure_condition"]["triggered"] is None
    assert report["chamber"]["complete"] is False


def test_as_of_replay_excludes_later_votes_and_later_certification(tmp_path):
    from election_prediction import build_results_2026 as cli

    for observed, votes, certified in [
        ("2026-11-05", 100, False),
        ("2026-11-12", 101, True),
        ("2026-11-20", 150, True),
    ]:
        r26.write_snapshot(
            _rows([("VA", 11, votes, 90)], certified=certified), observed_on=observed, directory=tmp_path
        )
    snapshots = r26.read_snapshots(tmp_path)
    early = r26.certification_ledger(snapshots, as_of="2026-11-06")
    assert pd.isna(early.iloc[0]["certified_on"])
    assert int(early.iloc[0]["dem_votes"]) == 100
    assert r26.certification_ledger(snapshots, as_of="2026-11-01").empty
    output = tmp_path / "actual.csv"
    assert (
        cli.main(["actual", "--directory", str(tmp_path), "--out", str(output), "--as-of", "2026-11-13"]) == 0
    )
    assert pd.read_csv(output).iloc[0]["actual_dem_share"] == pytest.approx(101 / 191)


@pytest.mark.parametrize(
    "column,value",
    [("other_votes", -1), ("dem_votes", 1.5), ("certified", "probably"), ("district_num", "bad")],
)
def test_malformed_snapshot_fields_are_rejected(column, value):
    rows = _rows([("VA", 11, 100, 90)]).astype(object)
    rows.loc[0, column] = value
    with pytest.raises(r26.SnapshotRejected):
        r26.validate_snapshot(rows)


def test_revocation_and_recertification_are_replayed_as_observed(tmp_path):
    for observed, certified in [("2026-11-05", True), ("2026-11-12", False), ("2026-11-20", True)]:
        r26.write_snapshot(
            _rows([("VA", 1, 100, 90)], certified=certified, retrieved=observed),
            observed_on=observed,
            directory=tmp_path,
        )
    snapshots = r26.read_snapshots(tmp_path)
    assert r26.certification_ledger(snapshots, as_of="2026-11-06").iloc[0].certified_on == "2026-11-05"
    assert pd.isna(r26.certification_ledger(snapshots, as_of="2026-11-13").iloc[0].certified_on)
    assert r26.certification_ledger(snapshots).iloc[0].certified_on == "2026-11-20"


def test_certified_first_round_is_not_a_resolved_runoff(tmp_path):
    first = _rows([("LA", 1, 45, 40)], retrieved="2026-11-12")
    with pytest.raises(r26.SnapshotRejected, match="Louisiana"):
        r26.validate_snapshot(first)
    first["election_round"], first["outcome_resolved"] = "first_round", False
    r26.write_snapshot(first, observed_on="2026-11-12", directory=tmp_path)
    assert pd.isna(r26.certification_ledger(r26.read_snapshots(tmp_path)).iloc[0].certified_on)
    runoff = first.assign(retrieved_on="2026-12-20", election_round="runoff", outcome_resolved=True)
    r26.write_snapshot(runoff, observed_on="2026-12-20", directory=tmp_path)
    assert r26.certification_ledger(r26.read_snapshots(tmp_path)).iloc[0].certified_on == "2026-12-20"


def test_partial_snapshot_preserves_an_unchanged_seat(tmp_path):
    r26.write_snapshot(
        _rows([("VA", 1, 100, 90), ("VA", 2, 40, 60)]), observed_on="2026-11-05", directory=tmp_path
    )
    r26.write_snapshot(
        _rows([("VA", 1, 101, 90)], retrieved="2026-11-12"), observed_on="2026-11-12", directory=tmp_path
    )
    ledger = r26.certification_ledger(r26.read_snapshots(tmp_path))
    assert len(ledger) == 2 and ledger.certified_on.eq("2026-11-05").all()


@pytest.mark.parametrize(
    "column,value",
    [
        ("state_po", "XX"),
        ("office", "state_senate"),
        ("source_url", "not a url"),
        ("retrieved_on", "2026-11-05T23:59:00-08:00"),
        ("election_round", "primary"),
        ("outcome_resolved", "maybe"),
    ],
)
def test_capture_identity_and_date_fields_fail_closed(column, value):
    rows = _rows([("VA", 1, 100, 90)]).astype(object)
    rows[column] = value
    with pytest.raises(r26.SnapshotRejected):
        r26.validate_snapshot(rows)


def test_zero_major_party_votes_preserve_explicit_other_winner(tmp_path):
    rows = _rows([("VA", 1, 0, 0)])
    rows["other_votes"], rows["winner_party"] = 100, "OTHER"
    r26.write_snapshot(rows, observed_on="2026-11-05", directory=tmp_path)
    actual = r26.to_actual(r26.certification_ledger(r26.read_snapshots(tmp_path)), state_fips={"VA": "51"})
    assert pd.isna(actual.iloc[0].actual_dem_share) and not actual.iloc[0].actual_dem_win


def test_interrupted_csv_write_does_not_publish_partial_observation(tmp_path, monkeypatch):
    original = pd.DataFrame.to_csv

    def interrupted(frame, handle, **kwargs):
        handle.write("partial")
        raise OSError("synthetic interrupted write")

    monkeypatch.setattr(pd.DataFrame, "to_csv", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        r26.write_snapshot(_rows([("VA", 1, 100, 90)]), observed_on="2026-11-05", directory=tmp_path)
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(pd.DataFrame, "to_csv", original)
    r26.write_snapshot(_rows([("VA", 1, 100, 90)]), observed_on="2026-11-05", directory=tmp_path)
    assert len(r26.read_snapshots(tmp_path)) == 1
