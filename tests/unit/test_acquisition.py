"""Tests for governed acquisition and the MEDSL live-schema transforms.

These cover the failure modes that let a build report success while modelling the
wrong data: error bodies served with HTTP 200, gated sources, primaries mixed in with
generals, per-mode vote rows, and fusion-voting candidate lines.
"""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.data import acquire, medsl


# ------------------------------------------------------------------ body sniffing
def test_html_error_page_is_rejected():
    """The Census API answers a keyless request with HTTP 200 + an HTML page."""
    body = b"<html><head><title>Missing Key</title></head><body>...</body></html>"
    with pytest.raises(acquire.InvalidResponse, match="Missing Key"):
        acquire._validate_body(body, expect="json", url="https://api.census.gov/data")


def test_dataverse_error_envelope_is_rejected():
    body = (
        b'{"status":"ERROR","message":"You may not download this file without '
        b'the required Guestbook response for guestbookID 458."}'
    )
    with pytest.raises(acquire.InvalidResponse, match="Guestbook"):
        acquire._validate_body(body, expect="csv", url="https://dataverse.harvard.edu/x")


def test_empty_body_is_rejected():
    with pytest.raises(acquire.InvalidResponse, match="Empty"):
        acquire._validate_body(b"   ", expect="csv", url="u")


def test_zip_magic_number_checked():
    with pytest.raises(acquire.InvalidResponse, match="zip"):
        acquire._validate_body(b"not a zip", expect="zip", url="u")
    acquire._validate_body(b"PK\x03\x04rest", expect="zip", url="u")  # no raise


def test_real_csv_passes():
    acquire._validate_body(b"year,state,candidatevotes\n2024,VA,100\n", expect="csv", url="u")


# --------------------------------------------------------------------- checksums
def test_verify_file_rejects_bad_checksum(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n")
    acquire.verify_file(f, expected_md5=acquire.md5_file(f))  # no raise
    with pytest.raises(acquire.AcquisitionError, match="Checksum mismatch"):
        acquire.verify_file(f, expected_md5="0" * 32)


def test_verify_file_rejects_wrong_size(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n")
    with pytest.raises(acquire.AcquisitionError, match="Size mismatch"):
        acquire.verify_file(f, expected_size=10_000_000)


# ------------------------------------------------------------- gated MEDSL source
def test_guestbook_source_raises_with_instructions(tmp_path):
    """President/House are gated; the build must say what a human should do."""
    with pytest.raises(acquire.ManualAcquisitionRequired) as excinfo:
        medsl.download_medsl("president", tmp_path)
    text = excinfo.value.instructions()
    assert "guestbook" in str(excinfo.value).lower()
    assert medsl.MEDSL_SOURCES["president"].filename in text
    assert "405af83db7625cb35d8c19a5ebe029ff" in text  # published checksum to verify against


def test_manual_snapshot_is_checksum_verified(tmp_path):
    """A manually-placed file that fails verification must not be used."""
    drop = medsl.manual_drop_dir("president", tmp_path)
    drop.mkdir(parents=True)
    (drop / medsl.MEDSL_SOURCES["president"].filename).write_text("year,state\n2024,VA\n")
    with pytest.raises(acquire.AcquisitionError, match="Size mismatch|Checksum mismatch"):
        medsl.find_manual_snapshot("president", tmp_path)


def test_source_urls_use_datafile_ids_not_dataset_dois():
    """Dataset DOIs are not datafile PIDs — using them returns HTTP 404."""
    for src in medsl.MEDSL_SOURCES.values():
        assert str(src.datafile_id).isdigit()
        assert src.url.endswith("?format=original")
        assert "persistentId" not in src.url
        assert src.election_cycle.endswith("2024")


# -------------------------------------------------------- live-schema transforms
def _bronze(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["snapshot_date"] = "2026-07-31"
    return df


def test_primaries_are_dropped():
    b = _bronze(
        [
            {
                "year": "2024",
                "state_po": "VA",
                "state": "VIRGINIA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "candidatevotes": "10",
                "totalvotes": "10",
                "stage": "gen",
            },
            {
                "year": "2024",
                "state_po": "VA",
                "state": "VIRGINIA",
                "office": "US SENATE",
                "candidate": "B",
                "party_detailed": "DEMOCRAT",
                "candidatevotes": "5",
                "totalvotes": "5",
                "stage": "pre",
            },
            # MEDSL mixes case; 'GEN' must survive the filter.
            {
                "year": "2024",
                "state_po": "VA",
                "state": "VIRGINIA",
                "office": "US SENATE",
                "candidate": "C",
                "party_detailed": "REPUBLICAN",
                "candidatevotes": "8",
                "totalvotes": "8",
                "stage": "GEN",
            },
        ]
    )
    kept, stats = medsl.filter_general_election(b)
    assert stats["dropped_non_general"] == 1
    assert set(kept["candidate"]) == {"A", "C"}


def test_vote_modes_prefer_published_total():
    b = _bronze(
        [
            {
                "year": "2024",
                "state_po": "VA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "stage": "gen",
                "special": "False",
                "writein": "False",
                "mode": "total",
                "candidatevotes": "100",
                "totalvotes": "100",
            },
            {
                "year": "2024",
                "state_po": "VA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "stage": "gen",
                "special": "False",
                "writein": "False",
                "mode": "election day",
                "candidatevotes": "60",
                "totalvotes": "100",
            },
            {
                "year": "2024",
                "state_po": "VA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "stage": "gen",
                "special": "False",
                "writein": "False",
                "mode": "absentee",
                "candidatevotes": "40",
                "totalvotes": "100",
            },
        ]
    )
    out, stats = medsl.collapse_vote_modes(b)
    assert len(out) == 1
    assert out["candidatevotes"].iloc[0] == 100  # not 200
    assert stats["mode_rows_collapsed"] == 2


def test_vote_modes_summed_when_no_total_row():
    b = _bronze(
        [
            {
                "year": "2024",
                "state_po": "VA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "stage": "gen",
                "special": "False",
                "writein": "False",
                "mode": "election day",
                "candidatevotes": "60",
                "totalvotes": "100",
            },
            {
                "year": "2024",
                "state_po": "VA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "stage": "gen",
                "special": "False",
                "writein": "False",
                "mode": "absentee",
                "candidatevotes": "40",
                "totalvotes": "100",
            },
        ]
    )
    out, _ = medsl.collapse_vote_modes(b)
    assert len(out) == 1
    assert out["candidatevotes"].iloc[0] == 100


def test_fusion_lines_are_summed_per_candidate():
    """NY-style fusion: one candidate on two party lines is still one candidate."""
    b = _bronze(
        [
            {
                "year": "1976",
                "state_po": "NY",
                "state": "NEW YORK",
                "office": "US SENATE",
                "candidate": "DANIEL PATRICK MOYNIHAN",
                "party_detailed": "DEMOCRAT",
                "party_simplified": "DEMOCRAT",
                "candidatevotes": "3238511",
                "totalvotes": "6666875",
                "stage": "gen",
                "writein": "False",
            },
            {
                "year": "1976",
                "state_po": "NY",
                "state": "NEW YORK",
                "office": "US SENATE",
                "candidate": "DANIEL PATRICK MOYNIHAN",
                "party_detailed": "LIBERAL",
                "party_simplified": "OTHER",
                "candidatevotes": "184083",
                "totalvotes": "6666875",
                "stage": "gen",
                "writein": "False",
            },
            {
                "year": "1976",
                "state_po": "NY",
                "state": "NEW YORK",
                "office": "US SENATE",
                "candidate": "JAMES L. BUCKLEY",
                "party_detailed": "REPUBLICAN",
                "party_simplified": "REPUBLICAN",
                "candidatevotes": "2836633",
                "totalvotes": "6666875",
                "stage": "gen",
                "writein": "False",
            },
        ]
    )
    silver, stats = medsl.standardize_silver_with_stats(b, "us_senate")
    assert stats["fusion_candidates_merged"] == 1

    moynihan = silver[silver["candidate"] == "DANIEL PATRICK MOYNIHAN"]
    assert len(moynihan) == 1
    assert moynihan["candidatevotes"].iloc[0] == 3238511 + 184083
    # The major-party label wins over the minor line it also ran on.
    assert moynihan["party_simplified"].iloc[0] == "DEMOCRAT"
    assert bool(moynihan["fusion_flag"].iloc[0])
    # Winner is decided on combined votes, so shares still sum to 1.
    assert abs(silver["vote_share"].sum() - 1.0) < 1e-9


def test_specials_do_not_collide_with_regular_races():
    b = _bronze(
        [
            {
                "year": "2024",
                "state_po": "VA",
                "state": "VIRGINIA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "candidatevotes": "10",
                "totalvotes": "10",
                "stage": "gen",
                "special": "False",
            },
            {
                "year": "2024",
                "state_po": "VA",
                "state": "VIRGINIA",
                "office": "US SENATE",
                "candidate": "B",
                "party_detailed": "DEMOCRAT",
                "candidatevotes": "7",
                "totalvotes": "7",
                "stage": "gen",
                "special": "True",
            },
        ]
    )
    silver = medsl.standardize_silver(b, "us_senate")
    assert silver["race_id"].nunique() == 2


def test_writeins_excluded_from_contender_count():
    b = _bronze(
        [
            {
                "year": "2024",
                "state_po": "VA",
                "state": "VIRGINIA",
                "office": "US SENATE",
                "candidate": "A",
                "party_detailed": "DEMOCRAT",
                "candidatevotes": "1000",
                "totalvotes": "1005",
                "stage": "gen",
                "writein": "False",
            },
            {
                "year": "2024",
                "state_po": "VA",
                "state": "VIRGINIA",
                "office": "US SENATE",
                "candidate": "SCATTERING",
                "party_detailed": "",
                "candidatevotes": "5",
                "totalvotes": "1005",
                "stage": "gen",
                "writein": "True",
            },
        ]
    )
    silver = medsl.standardize_silver(b, "us_senate")
    # A lone candidate plus write-ins is still an uncontested race.
    assert silver["uncontested_flag"].all()


def test_parse_bronze_rejects_wrong_delimiter(tmp_path):
    """House ships tab-separated; reading it as CSV yields one useless column."""
    f = tmp_path / "1976-2024-house.tab"
    f.write_text("year,state_po,candidate\n2024,VA,A\n")  # comma-delimited, wrong for house
    with pytest.raises(ValueError, match="single column"):
        medsl.parse_bronze(f, "us_house", source_id="s", snapshot_date="2026-07-31")
