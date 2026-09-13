"""OpenFEC client: the governance gate, parsing, and the fields that must not be filtered.

No test here touches the network. Snapshots are written in the module's own envelope
format so parsing is exercised end-to-end from disk.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from election_prediction.data.privacy import GovernanceError
from election_prediction.data import acquire, fec


def _write(tmp_path, rows: list[dict], *, endpoint="/candidates/", cycle=2024):
    path = tmp_path / "snap.json"
    path.write_text(
        json.dumps(
            {
                "endpoint": endpoint,
                "query": {"cycle": cycle, "office": "H"},
                "retrieved_at": "2026-09-08T12:00:00+00:00",
                "row_count": len(rows),
                "results": rows,
            }
        )
    )
    return path


def _cand(**over) -> dict:
    base = {
        "candidate_id": "H4GA01001",
        "name": "DOE, JANE",
        "office": "H",
        "state": "GA",
        "district": "01",
        "district_number": 1,
        "party": "DEM",
        "party_full": "DEMOCRATIC PARTY",
        "incumbent_challenge": "I",
        "candidate_status": "C",
        "candidate_inactive": False,
        "election_years": [2020, 2024, 2022],
        "first_file_date": "2019-01-01",
        "last_file_date": "2024-10-01",
        "has_raised_funds": True,
    }
    return {**base, **over}


def _total(**over) -> dict:
    base = {
        "candidate_id": "H4GA01001",
        "name": "DOE, JANE",
        "office": "H",
        "state": "GA",
        "district": "01",
        "district_number": 1,
        "party": "DEM",
        "election_year": 2024,
        "is_election": True,
        "coverage_start_date": "2023-01-01T00:00:00+00:00",
        "coverage_end_date": "2024-09-30T00:00:00+00:00",
        "receipts": 1_500_000.0,
        "disbursements": 1_400_000.0,
        "cash_on_hand_end_period": 100_000.0,
        "debts_owed_by_committee": 0.0,
        "individual_itemized_contributions": 900_000.0,
        "other_political_committee_contributions": 400_000.0,
        "incumbent_challenge": "I",
        "candidate_status": "C",
    }
    return {**base, **over}


# ------------------------------------------------------------------ governance gate
@pytest.mark.parametrize("path", sorted(fec.PERMITTED_ENDPOINTS))
def test_the_allowlisted_endpoints_pass(path):
    fec.assert_endpoint_permitted(path)


@pytest.mark.parametrize(
    "path",
    [
        "/schedules/schedule_a/",  # itemized contributor records: Tier 2, names and addresses
        "/schedules/schedule_b/",
        "/committee/C00000001/schedules/schedule_a/",
    ],
)
def test_an_itemized_contributor_endpoint_is_refused(path):
    """Schedule A is aggregate-only by governance; the allowlist is what enforces it."""
    with pytest.raises(GovernanceError):
        fec.assert_endpoint_permitted(path)


def test_an_unlisted_endpoint_is_refused_rather_than_allowed_by_default():
    """An allowlist, not a denylist: a new endpoint is off until it is reviewed."""
    with pytest.raises(GovernanceError):
        fec.assert_endpoint_permitted("/elections/")


def test_the_source_is_declared_public_aggregate():
    assert fec.PRIVACY_TIER == 0
    assert "Federal Election Commission" in fec.ATTRIBUTION


# ------------------------------------------------------------------------- privacy
def test_candidate_mailing_addresses_never_reach_the_frame(tmp_path):
    """FEC returns a candidate's street address; it must not land on disk."""
    row = _cand(address_street_1="100 MAIN ST", address_city="ATLANTA", address_zip="30301")
    df = fec.parse_candidates(_write(tmp_path, [row]))
    assert not [c for c in fec.DROPPED_PERSONAL_FIELDS if c in df.columns]
    assert not df.astype(str).apply(lambda s: s.str.contains("MAIN ST")).any().any()
    assert fec.validate_candidates(df)["privacy.no_address_fields"]


def test_addresses_are_dropped_from_totals_too(tmp_path):
    df = fec.parse_candidate_totals(_write(tmp_path, [_total(address_street_1="100 MAIN ST")]))
    assert fec.validate_candidate_totals(df)["privacy.no_address_fields"]


# ------------------------------------------------------------------------ parsing
def test_a_candidate_snapshot_parses_into_the_project_vocabulary(tmp_path):
    df = fec.parse_candidates(_write(tmp_path, [_cand()]))
    row = df.iloc[0]
    assert row["office"] == "us_house", "FEC files 'H'; the project says us_house"
    assert row["district_num"] == 1
    assert row["election_years"] == "2020,2022,2024", "sorted, so a prior run is greppable"
    assert row["snapshot_date"] == "2026-09-08"
    assert fec.validate_candidates(df)["ok"]


def test_an_at_large_house_seat_parses_as_district_zero(tmp_path):
    df = fec.parse_candidates(_write(tmp_path, [_cand(district="00", district_number=0, state="WY")]))
    assert df.iloc[0]["district_num"] == 0


def test_a_senate_row_has_no_district_number(tmp_path):
    df = fec.parse_candidates(_write(tmp_path, [_cand(office="S", district="00", district_number=None)]))
    assert df.iloc[0]["office"] == "us_senate"
    assert pd.isna(df.iloc[0]["district_num"])


def test_a_totals_snapshot_parses_money_as_numbers(tmp_path):
    df = fec.parse_candidate_totals(_write(tmp_path, [_total()], endpoint="/candidates/totals/"))
    row = df.iloc[0]
    assert row["receipts"] == 1_500_000.0
    assert row["coverage_end_date"] == "2024-09-30", "truncated to a date, not a timestamp"
    assert fec.validate_candidate_totals(df)["ok"]


def test_the_query_is_stored_inside_the_snapshot(tmp_path):
    """An FEC pull is not reproducible without the query that produced it."""
    _, envelope = fec.read_snapshot(_write(tmp_path, [_cand()]))
    assert envelope["query"] == {"cycle": 2024, "office": "H"}
    assert envelope["endpoint"] == "/candidates/"


# --------------------------------------------------- the fields that are current-state
def test_a_null_party_is_counted_not_rejected(tmp_path):
    """2 of 3,656 rows in the real 2024 roster carry no party. The pull is still correct."""
    df = fec.parse_candidates(_write(tmp_path, [_cand(), _cand(candidate_id="H4GA02001", party=None)]))
    rep = fec.validate_candidates(df)
    assert rep["ok"], "a real FEC condition must not fail an otherwise-clean roster"
    assert rep["party.rows_without_party"] == 1


def test_a_null_candidate_status_is_counted_not_rejected(tmp_path):
    df = fec.parse_candidates(_write(tmp_path, [_cand(candidate_status=None)]))
    rep = fec.validate_candidates(df)
    assert rep["ok"] and rep["filing.rows_without_status"] == 1


def test_an_unknown_candidate_status_code_still_fails(tmp_path):
    df = fec.parse_candidates(_write(tmp_path, [_cand(candidate_status="Z")]))
    assert not fec.validate_candidates(df)["filing.status_known"]


def test_a_status_n_candidate_is_kept_because_status_is_a_present_tense_field(tmp_path):
    """Grijalva's status became N when he died in 2025 -- for an election he won in 2024."""
    df = fec.parse_candidates(_write(tmp_path, [_cand(name="GRIJALVA, RAUL M", candidate_status="N")]))
    assert len(df) == 1 and fec.validate_candidates(df)["ok"]


def test_the_roster_pull_does_not_filter_on_candidate_status_by_default():
    """candidate_status="C" returned 1,028 of 3,044 real 2024 House candidates."""
    import inspect

    assert inspect.signature(fec.download_candidates).parameters["candidate_status"].default is None


def test_a_zero_receipt_filer_without_a_coverage_date_is_counted_not_rejected(tmp_path):
    """550 of 1,840 rows in the real 1988 totals; every one raised nothing."""
    rows = [_total(), _total(candidate_id="H8GA02001", receipts=0.0, coverage_end_date=None)]
    rep = fec.validate_candidate_totals(fec.parse_candidate_totals(_write(tmp_path, rows)))
    assert rep["ok"]
    assert rep["coverage.rows_without_end_date"] == 1
    assert rep["coverage.funded_rows_without_end_date"] == 0


def test_a_funded_row_without_a_coverage_date_is_a_contradiction(tmp_path):
    """Money with no reporting window cannot be pinned to a deadline; that is a real defect."""
    rows = [_total(receipts=750_000.0, coverage_end_date=None)]
    rep = fec.validate_candidate_totals(fec.parse_candidate_totals(_write(tmp_path, rows)))
    assert not rep["ok"]
    assert not rep["coverage.end_date_present_when_funded"]


def test_a_duplicated_candidate_id_fails(tmp_path):
    df = fec.parse_candidates(_write(tmp_path, [_cand(), _cand()]))
    assert not fec.validate_candidates(df)["keys.candidate_id_unique"]


def test_an_empty_snapshot_parses_to_an_empty_typed_frame(tmp_path):
    df = fec.parse_candidates(_write(tmp_path, []))
    assert len(df) == 0 and list(df.columns) == fec.CANDIDATE_COLUMNS
    assert fec.validate_candidates(df)["ok"]


# ------------------------------------------------------------------------ api key
def test_a_missing_api_key_is_an_operator_problem_with_instructions(monkeypatch):
    """Distinguished from a bad response because the fix is configuration, not code."""
    monkeypatch.delenv(fec.FEC_KEY_ENV, raising=False)
    with pytest.raises(acquire.CredentialRequired) as exc:
        fec.resolve_api_key(None)
    steps = exc.value.instructions()
    assert fec.FEC_KEY_ENV in steps and fec.FEC_KEY_SIGNUP in steps


def test_a_resolved_key_is_never_echoed_in_an_error(monkeypatch):
    """The key must not reach a log or a traceback."""
    monkeypatch.setenv(fec.FEC_KEY_ENV, "SECRETKEY123")
    assert fec.resolve_api_key(None) == "SECRETKEY123"
    with pytest.raises(GovernanceError) as exc:
        fec.assert_endpoint_permitted("/schedules/schedule_a/")
    assert "SECRETKEY123" not in str(exc.value)
