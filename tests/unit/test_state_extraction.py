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


def test_north_carolina_sums_every_row_including_county_batches(tmp_path: Path) -> None:
    import zipfile

    header = (
        "County\tElection Date\tPrecinct\tContest Group ID\tContest Type\tContest Name\tChoice\t"
        "Choice Party\tVote For\tElection Day\tEarly Voting\tAbsentee by Mail\tProvisional\t"
        "Total Votes\tReal Precinct"
    )
    house = "US HOUSE OF REPRESENTATIVES DISTRICT 02"
    rows = [
        "WAKE\t11/03/2026\t01-01\t1\tC\tUS SENATE\tAnn A\tDEM\t1\t1\t1\t1\t0\t100\tY",
        "WAKE\t11/03/2026\tABSENTEE\t1\tC\tUS SENATE\tAnn A\tDEM\t1\t0\t0\t20\t0\t20\tN",
        "WAKE\t11/03/2026\t01-01\t1\tC\tUS SENATE\tBob B\tREP\t1\t1\t1\t1\t0\t90\tY",
        "WAKE\t11/03/2026\t01-01\t2\tC\t" + house + "\tCal C\tREP\t1\t1\t1\t1\t0\t40\tY",
        "WAKE\t11/03/2026\t01-01\t2\tC\t" + house + "\tWrite-In\t\t1\t0\t0\t0\t0\t3\tY",
        "WAKE\t11/03/2026\t01-01\t3\tC\tNC GOVERNOR\tDee D\tDEM\t1\t1\t1\t1\t0\t70\tY",
    ]
    f = tmp_path / "results_pct_20261103.zip"
    with zipfile.ZipFile(f, "w") as zf:
        zf.writestr("results_pct_20261103.txt", "\n".join([header, *rows]) + "\n")
    out = se.extract("NC", [f]).set_index("office")
    assert (out.loc["us_senate", "dem_votes"], out.loc["us_senate", "rep_votes"]) == (120, 90)
    assert out.loc["us_house", "district_num"] == 2 and out.loc["us_house", "other_votes"] == 3
    assert len(out) == 2  # the governor contest is not a federal race


def test_louisiana_first_round_needs_a_majority(tmp_path: Path) -> None:
    head = 'Office,Parish,"Ann A (DEM)","Bob B (REP)","Cal C (REP)"\n'
    office = '"U. S. Representative -- 5th Congressional District"'
    split = tmp_path / "ByParish_1.csv"
    split.write_text(head + f'{office},"Winn","40","35","25"\n')
    majority = tmp_path / "ByParish_2.csv"
    majority.write_text(
        head.replace("5th", "4th") + office.replace("5th", "4th") + ',"Winn","20","70","10"\n'
    )
    out = se.extract("LA", [split, majority]).set_index("district_num")
    assert not out.loc[5, "outcome_resolved"] and pd.isna(out.loc[5, "winner_party"])
    assert out.loc[4, "outcome_resolved"] and out.loc[4, "winner_party"] == "REPUBLICAN"
    assert set(out["election_round"]) == {"first_round"}


def test_vermont_excludes_the_state_total_row_and_checks_it(tmp_path: Path) -> None:
    import json

    def town(tid: int, d: int, r: int) -> dict:
        return {
            "tid": tid,
            "rc": [{"cn": "A", "pn": "DEMOCRATIC", "vc": d}, {"cn": "B", "pn": "REP/LBRT", "vc": r}],
            "wc": [],
        }

    office = {"on": "REPRESENTATIVE TO CONGRESS", "cs": [town(1, 10, 5), town(2, 20, 5), town(0, 30, 10)]}
    f = tmp_path / "VT_f.json"
    f.write_text(json.dumps({"d": [{"pid": 0, "o": [office]}]}))
    row = se.extract("VT", [f]).iloc[0]
    assert (row.dem_votes, row.rep_votes) == (30, 10)  # fusion label read as its first party
    office["cs"][2] = town(0, 31, 10)
    f.write_text(json.dumps({"d": [{"pid": 0, "o": [office]}]}))
    with pytest.raises(ValueError, match="state total"):
        se.extract("VT", [f])


def test_delaware_drops_verbatim_duplicate_rows(tmp_path: Path) -> None:
    f = tmp_path / "de.csv"
    f.write_text(
        '"office","candidatename","partyname","totalvotessum"\n'
        '"U.S. Senator","A","Democratic Party","100"\n'
        '"U.S. Senator","A","Democratic Party","100"\n'
        '"U.S. Senator","B","Republican Party","90"\n'
    )
    row = se.extract("DE", [f]).iloc[0]
    assert (row.dem_votes, row.rep_votes) == (100, 90)


def test_hawaii_reads_utf16_with_a_trailing_delimiter(tmp_path: Path) -> None:
    header = "#Contest ID,Contest Title,Candidate Name,Total Votes"
    rows = [
        '"30","U.S. Representative, Dist II","(D) X, A","70",',
        '"30","U.S. Representative, Dist II","(R) Y, B","30",',
    ]
    f = tmp_path / "summary.txt"
    f.write_bytes("\n".join(["Format#1", header, *rows]).encode("utf-16"))
    row = se.extract("HI", [f]).iloc[0]
    assert (row.district_num, row.dem_votes, row.rep_votes) == (2, 70, 30)


def test_indiana_ordinal_districts_and_locality_rows(tmp_path: Path) -> None:
    f = tmp_path / "AllOfficeResults.csv"
    off = "United States Representative, Seventh District"
    f.write_text(
        '"Office","DataEntryLevelName","NameonBallot","PoliticalParty","TotalVotes"\n'
        f'"{off}","Precinct","A","Democratic","10"\n'
        f'"{off}","Locality","A","Democratic","5"\n'
        f'"{off}","Precinct","B","Republican","12"\n'
    )
    row = se.extract("IN", [f]).iloc[0]
    assert (row.district_num, row.dem_votes, row.rep_votes) == (7, 15, 12)


def _clarity_zip(path: Path, rows: list[tuple[str, str, str, int]]) -> Path:
    import zipfile

    lines = ['"line number","contest name","choice name","party name","total votes"']
    lines += [f'{i},"{c}","{n}","{p}",{v}' for i, (c, n, p, v) in enumerate(rows, 1)]
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("summary.csv", "\n".join(lines) + "\n")
    return path


def test_south_carolina_recount_replaces_the_general_race(tmp_path: Path) -> None:
    cd = "U.S.  House of Representatives, District  2 (Vote For 1)"
    general = _clarity_zip(tmp_path / "SC_general.zip", [(cd, "D", "DEM", 100), (cd, "R", "REP", 99)])
    recount = _clarity_zip(tmp_path / "SC_recount.zip", [(cd, "D", "DEM", 98), (cd, "R", "REP", 101)])
    row = se.extract("SC", [general, recount]).iloc[0]
    assert (row.dem_votes, row.rep_votes, row.winner_party) == (98, 101, "REPUBLICAN")
