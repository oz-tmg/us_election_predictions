"""Synthetic archived toplines only; no respondent records or network access."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from election_prediction.data import candidate_polls, polling_archive
from election_prediction.polling import lean


@pytest.fixture
def inputs():
    return {
        "races": pd.DataFrame(
            [
                {
                    "race_id": "canonical",
                    "cycle": 2022,
                    "office": "us_senate",
                    "state_po": "OH",
                    "district_num": np.nan,
                    "two_party_dem_share": 0.45,
                    "certified_flag": True,
                    "uncontested_flag": False,
                    "winner_party": "REPUBLICAN",
                }
            ]
        ),
        "presidential": pd.DataFrame(
            [
                {
                    "cycle": 2020,
                    "state_po": "OH",
                    "two_party_dem_share": 0.45,
                    "national_dem_share": 0.5,
                }
            ]
        ),
        "fundamentals": pd.DataFrame(
            [
                {
                    "race_id": "canonical",
                    "pred_dem_share": 0.46,
                    "resid_sigma": 0.06,
                    "train_through": 2020,
                }
            ]
        ),
        "house_panel": pd.DataFrame(columns=["race_id", "district_lean", "lag_dem_share"]),
    }


def _answers():
    common = {
        "question_id": "101",
        "poll_id": "10",
        "cycle": "2022",
        "state": "Ohio",
        "office_type": "U.S. Senate",
        "seat_number": "2",
        "election_date": "11/8/22",
        "stage": "general",
        "start_date": "10/19/22",
        "end_date": "10/21/22",
        "created_at": "10/22/22 15:00",
        "pollster": "Synthetic",
        "methodology": "Phone",
        "partisan": None,
        "sample_size": "900",
        "ranked_choice_reallocated": "false",
        "source_file": "senate_polls_historical.csv",
    }
    return pd.DataFrame(
        [
            {**common, "candidate_id": "1", "candidate_name": "Example D", "party": "DEM", "pct": "48"},
            {**common, "candidate_id": "2", "candidate_name": "Example R", "party": "REP", "pct": "50"},
        ]
    )


def test_pair_normalization_metadata_and_no_fabricated_archive_outcome(inputs):
    polls, report = candidate_polls.prepare_candidates([_answers()], **inputs)
    assert polls.race_id.tolist() == ["canonical"]
    assert polls.poll_dem_share.iloc[0] == pytest.approx(48 / 98)
    assert polls.actual_dem_share.iloc[0] == 0.45
    assert polls.lean_reference_cycle.iloc[0] == 2020
    assert polls.field_end_verified.all()
    assert not polls.publication_verified.any()
    assert "archive_actual" not in polls
    assert not report["promotion_eligible"]
    lean.validate_panel(polls)


def test_identical_answer_overlap_is_collapsed(inputs):
    raw = _answers()
    other = raw.assign(source_file="senate_polls.csv")
    polls, report = candidate_polls.prepare_candidates([raw, other], **inputs)
    assert len(polls) == 1
    assert report["duplicate_answer_rows_collapsed"] == 2


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("duplicate_party", "not_unique_dem_rep_pair"),
        ("conflict", "conflicting_question_metadata"),
        ("percent", "invalid_topline"),
        ("sample", "invalid_sample_or_zero_major_party_total"),
        ("pollster", "missing_pollster"),
        ("round", "ranked_choice_round_not_verified"),
        ("hypothetical", "hypothetical_or_unknown_matchup"),
        ("reversed_dates", "invalid_field_or_entry_date"),
        ("special", "not_november_general"),
    ],
)
def test_bad_question_excluded_without_losing_valid_question(inputs, fault, reason):
    good = _answers()
    bad = good.assign(question_id="102").copy()
    if fault == "duplicate_party":
        bad["party"] = "REP"
    elif fault == "conflict":
        bad.loc[0, "end_date"] = "10/22/22"
    elif fault == "percent":
        bad["pct"] = "60"
    elif fault == "sample":
        bad["sample_size"] = None
    elif fault == "pollster":
        bad["pollster"] = " "
    elif fault == "round":
        bad["ranked_choice_reallocated"] = "true"
    elif fault == "hypothetical":
        bad["hypothetical"] = "true"
    elif fault == "reversed_dates":
        bad["start_date"] = "10/24/22"
    else:
        bad["election_date"] = "8/2/22"
    polls, report = candidate_polls.prepare_candidates([pd.concat([good, bad])], **inputs)
    assert polls.question_id.tolist() == ["101"]
    assert report["exclusions"][reason] == 1


def test_candidate_answer_conflict_is_not_summed(inputs):
    good = _answers()
    bad = good.assign(question_id="102")
    conflict = bad.iloc[[0]].assign(pct="49")
    polls, report = candidate_polls.prepare_candidates([pd.concat([good, bad, conflict])], **inputs)
    assert len(polls) == 1
    assert report["exclusions"]["not_unique_dem_rep_pair"] == 1


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("ambiguous", "missing_or_ambiguous_canonical_race"),
        ("future", "missing_or_nonchronological_fundamentals"),
    ],
)
def test_structural_ambiguity_and_future_fundamentals_fail_closed(inputs, fault, reason):
    if fault == "ambiguous":
        inputs["races"] = pd.concat([inputs["races"], inputs["races"].assign(race_id="special")])
    else:
        inputs["fundamentals"]["train_through"] = 2022
    polls, report = candidate_polls.prepare_candidates([_answers()], **inputs)
    assert polls.empty
    assert report["exclusions"][reason] == 1


def test_invalid_at_large_number_is_not_silently_corrected(inputs):
    raw = _answers().assign(office_type="U.S. House", seat_number="2")
    inputs["races"] = inputs["races"].assign(office="us_house", district_num=0)
    good = raw.assign(question_id="102", seat_number="1")
    polls, report = candidate_polls.prepare_candidates([pd.concat([raw, good])], **inputs)
    assert polls.empty  # Valid at-large question still lacks a historical House feature.
    assert report["exclusions"]["invalid_at_large_district"] == 1


def test_known_late_entry_and_field_end_cannot_enter_window(inputs):
    polls, _ = candidate_polls.prepare_candidates([_answers()], **inputs)
    assert lean.aggregate_races(polls, lean.Design())[1]["eligible_poll_rows"] == 1
    polls["database_created_at"] = pd.Timestamp("2022-11-02")
    assert lean.aggregate_races(polls, lean.Design())[1]["eligible_poll_rows"] == 0
    polls["database_created_at"] = pd.Timestamp("2022-10-22")
    polls["field_end"] = pd.Timestamp("2022-11-02")
    assert lean.aggregate_races(polls, lean.Design())[1]["eligible_poll_rows"] == 0


def test_cycle_replacement_never_backfills_rejected_questions(inputs):
    candidate, report = candidate_polls.prepare_candidates([_answers()], **inputs)
    ratings = pd.concat(
        [
            candidate.assign(question_id="old-same-cycle"),
            candidate.assign(question_id="old-earlier-cycle", cycle=2020),
        ],
        ignore_index=True,
    )
    combined, replaced = candidate_polls.replace_overlapping_cycles(
        ratings, candidate, report["replacement_office_cycles"]
    )
    assert replaced == 1
    assert set(combined.question_id) == {"101", "old-earlier-cycle"}


def test_old_schema_and_import_provenance_are_honest_and_immutable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "senate_polls.csv"
    _answers().rename(columns={"party": "candidate_party"}).to_csv(path, index=False)
    url = "https://web.archive.org/web/20241129175756if_/" + polling_archive.POLL_URLS[path.name]
    receipt = candidate_polls.preserve_manual_file(path, archive_url=url)
    assert receipt["browser_retrieved_at"] is None
    assert receipt["archive_capture_at"] == "2024-11-29T17:57:56+00:00"
    assert receipt["project_ingested_at"] != receipt["archive_capture_at"]
    assert not receipt["independently_refetched"]
    saved = pd.read_csv(receipt["raw_path"])
    assert "candidate_party" in saved
    assert "party" not in saved
    manifest = json.loads(Path(receipt["manifest"]).read_text())
    assert "project ingestion" in manifest["acquisition_method"]
    assert candidate_polls.preserve_manual_file(path, archive_url=url) == receipt
    Path(receipt["raw_path"]).write_text("tampered")
    with pytest.raises(ValueError, match="immutable"):
        candidate_polls.preserve_manual_file(path, archive_url=url)


def test_wrong_office_and_unregistered_archive_rejected(tmp_path):
    path = tmp_path / "house_polls.csv"
    _answers().to_csv(path, index=False)
    with pytest.raises(ValueError, match="office"):
        candidate_polls.read_candidate_file(path)
    with pytest.raises(ValueError, match="registered"):
        candidate_polls.preserve_manual_file(path, archive_url="https://example.com/polls.csv")
