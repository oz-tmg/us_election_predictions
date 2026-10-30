"""Per-state extraction harness: party bucketing, contest collapse, reconciliation."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.results_2026 import SNAPSHOT_COLUMNS


def _certified() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "race_id": ["2024_us_house_xx_1_gen", "2024_us_house_xx_2_gen", "2024_us_senate_xx_gen"],
            "cycle": [2024, 2024, 2024],
            "office": ["us_house", "us_house", "us_senate"],
            "state_po": ["XX"] * 3,
            "district_num": [1.0, 2.0, None],
            "dem_votes": [100_000, 50_000, 400_000],
            "rep_votes": [90_000, 0, 380_000],
            "uncontested_flag": [False, False, False],
        }
    )


def _extracted(**over: int) -> pd.DataFrame:
    rows = [
        se.from_candidates(
            pd.DataFrame(
                {"party": ["DEM", "REP", "LIB"], "votes": [100_000, over.get("rep1", 90_000), 5_000]}
            ),
            state_po="XX",
            office="us_house",
            district_num=1,
        ),
        se.from_candidates(
            pd.DataFrame({"party": ["Democratic", "Write-in"], "votes": [50_000, 30]}),
            state_po="XX",
            office="us_house",
            district_num=2,
        ),
        se.from_candidates(
            pd.DataFrame({"party": ["D", "R"], "votes": [400_000, 380_000]}),
            state_po="XX",
            office="us_senate",
            district_num=None,
        ),
    ]
    return se.validate_extracted(pd.DataFrame(rows))


def test_party_bucket() -> None:
    assert se.party_bucket("Democratic") == "DEMOCRAT"
    assert se.party_bucket("R.") == "REPUBLICAN"
    assert se.party_bucket("Libertarian") == "OTHER"
    assert se.party_bucket(None) == "OTHER"


def test_from_candidates_sums_parties_and_picks_top_candidate() -> None:
    row = se.from_candidates(
        pd.DataFrame({"party": ["DEM", "DEM", "REP"], "votes": [40, 30, 60]}),
        state_po="XX",
        office="us_house",
        district_num=3,
    )
    assert (row["dem_votes"], row["rep_votes"], row["winner_party"]) == (70, 60, "REPUBLICAN")


def test_exact_extraction_passes() -> None:
    rec = se.reconcile(_extracted(), _certified(), state="XX", cycle=2024)
    assert set(rec["status"]) == {"exact"}
    assert se.summarize(rec)["passed"]


def test_small_difference_is_within_tolerance_large_is_mismatch() -> None:
    near = se.reconcile(_extracted(rep1=90_050), _certified(), state="XX", cycle=2024)
    assert near.loc[0, "status"] == "within_tolerance"
    far = se.reconcile(_extracted(rep1=91_000), _certified(), state="XX", cycle=2024)
    assert far.loc[0, "status"] == "mismatch"
    assert not se.summarize(far)["passed"]


def test_missing_and_extra_races_fail() -> None:
    ext = _extracted().iloc[[0, 2]]
    rec = se.reconcile(ext, _certified(), state="XX", cycle=2024)
    assert "missing_in_extract" in set(rec["status"])
    assert not se.summarize(rec)["passed"]


def test_validate_rejects_duplicates_and_bad_offices() -> None:
    dup = pd.concat([_extracted(), _extracted().iloc[[0]]])
    with pytest.raises(ValueError, match="duplicate"):
        se.validate_extracted(dup)
    bad = _extracted().assign(office="governor")
    with pytest.raises(ValueError, match="office"):
        se.validate_extracted(bad)


def test_snapshot_takes_certification_from_the_operator() -> None:
    snap = se.to_snapshot(
        _extracted(), source_url="https://sos.example/r.csv", retrieved_on="2026-11-04", certified=False
    )
    assert list(snap.columns[: len(SNAPSHOT_COLUMNS)]) == SNAPSHOT_COLUMNS
    assert not snap["certified"].any()


# --- state parsers (synthetic layouts; real files are tested by reconciliation) -----------

from pathlib import Path  # noqa: E402

from election_prediction.data import state_parsers  # noqa: E402


def test_contest_token_is_required_in_file_names() -> None:
    assert state_parsers.contest_from_name(Path("MA_2026GE_CD4_1_by_town.csv")) == ("us_house", 4)
    assert state_parsers.contest_from_name(Path("MA_2026GE_SEN_1.csv")) == ("us_senate", None)
    with pytest.raises(ValueError, match="contest token"):
        state_parsers.contest_from_name(Path("results.csv"))


def test_massachusetts_reads_the_totals_row_and_drops_blanks(tmp_path: Path) -> None:
    f = tmp_path / "MA_2026GE_CD9_1_by_town.csv"
    f.write_text(
        'City/Town,,,"Ann A","Bob B","All Others",Blanks,"Total Votes Cast"\n'
        ",,,Democratic,Republican\n"
        'Abington,,,"1,000",900,3,50,"1,953"\n'
        'TOTALS,,,"251,931","193,822",120,"9,000","454,873"\n'
    )
    row = state_parsers.massachusetts([f]).iloc[0]
    assert (row.office, row.district_num, row.dem_votes, row.rep_votes, row.other_votes) == (
        "us_house",
        9,
        251_931,
        193_822,
        120,
    )


def test_missouri_lines_handles_wrapped_names_and_checks_totals() -> None:
    lines = [
        "U.S. Representative - District 3 (325 of 325 Precincts Reported)",
        "Bob Onder Republican 240,620 61.3%",
        "Bethany E. Mann With A Very Long",
        "Name Democratic 138,532 35.3%",
        "Jane Doe Libertarian 13,000 3.3%",
        "Total Votes 392,152",
        "Governor (3572 of 3572 Precincts Reported)",
    ]
    row = state_parsers.missouri_lines(lines)[0]
    assert (row["district_num"], row["dem_votes"], row["rep_votes"], row["other_votes"]) == (
        3,
        138_532,
        240_620,
        13_000,
    )
    with pytest.raises(ValueError, match="do not sum"):
        state_parsers.missouri_lines([*lines[:5], "Total Votes 1"])
