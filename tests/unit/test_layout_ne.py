"""Nebraska layouts: 2024 Canvass Book text layer and 2026 CSV exports (synthetic fixtures)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.state_layouts import ne

PAGE = "General Election – November 5, 2024  Page | {} "

CANVASS = [
    PAGE.format(3),
    "Member of the United States Senate – Six Year Term ........ 16",  # table of contents: not a heading
    PAGE.format(13),
    "President and Vice President of the United States",
    "Congressional District 1",  # presidential by-district table: no term, before the House section
    "County",
    "Some One✔",
    "(Republican)",
    "Total 9 ",
    "Adams 9 ",
    PAGE.format(16),
    "Member of the United States Senate – Six Year Term ",
    " ",
    "County ",
    "Deb Fischer✔ ",
    "(Republican) ",
    "Dan Osborn ",
    "(By Petition) ",
    "Write-In ",
    "Scatterings ",
    "Total 1,300 1,150 7 ",
    "Adams 1,000 400 5 ",
    "Keya Paha 200 50 0 ",
    "County ",  # header repeated at a column / page break
    "Deb Fischer✔ ",
    "(Republican) ",
    "Dan Osborn ",
    "(By Petition) ",
    "Write-In ",
    "Scatterings ",
    PAGE.format(17),
    "Sarpy (57 precincts) 100 700 2 ",
    "Member of the United States Senate – Two Year Term ",  # unexpired term: skipped
    "County ",
    "Pete Ricketts✔ ",
    "(Republican) ",
    "Preston Love Jr. ",
    "(Democratic) ",
    "Total 50 40 ",
    "Adams 50 40 ",
    PAGE.format(18),
    "Member of the U.S. House of Representatives ",
    "Congressional District 1 – Two Year Term ",
    "County ",
    "Mike Flood✔ ",
    "(Republican) ",
    "Carol Blood ",
    "(Democratic) ",
    "Total 300 250 ",
    "Butler 100 50 ",
    "Polk (3 precincts) 200 200 ",
    "Congressional District 2 – Two Year Term ",
    "County ",
    "Don Bacon ",
    "(Republican) ",
    "Tony Vargas✔ ",
    "(Democratic) ",
    "A Third ",
    "(Legal Marijuana ",
    "NOW) ",
    "Total 10 20 3 ",
    "Douglas 10 20 3 ",
    PAGE.format(20),
    "State Offices ",
    "District 1 ",
    "County ",
    "Dan Watermeier✔ ",
    "(Republican) ",
    "Total 5 ",
    "Cass 5 ",
]


def test_canvass_reads_tables_checked_against_the_printed_total() -> None:
    rows = pd.DataFrame(ne.canvass_lines(CANVASS)).set_index(["office", "district_num"], drop=False)
    assert len(rows) == 3  # six-year Senate + two House districts; the two-year Senate seat is skipped
    senate = rows[rows["office"] == "us_senate"].iloc[0]
    assert (senate["dem_votes"], senate["rep_votes"], senate["other_votes"]) == (0, 1300, 1157)
    cd1 = rows[rows["district_num"] == 1].iloc[0]
    assert (cd1["dem_votes"], cd1["rep_votes"], cd1["winner_party"]) == (250, 300, "REPUBLICAN")
    cd2 = rows[rows["district_num"] == 2].iloc[0]
    assert (cd2["dem_votes"], cd2["rep_votes"], cd2["other_votes"]) == (20, 10, 3)


def test_canvass_refuses_a_table_whose_counties_do_not_sum_to_the_total() -> None:
    broken = [ln.replace("Butler 100 50", "Butler 100 51") for ln in CANVASS]
    with pytest.raises(ValueError, match="printed Total"):
        ne.canvass_lines(broken, source="book.pdf")
    dropped = [ln for ln in CANVASS if not ln.startswith("Keya Paha")]
    with pytest.raises(ValueError, match="county rows sum to"):
        ne.canvass_lines(dropped)
    lost_column = [ln for ln in CANVASS if ln.strip() != "(By Petition)"]
    with pytest.raises(ValueError, match="candidate columns"):
        ne.canvass_lines(lost_column)


HEADER = (
    "RaceID,RaceName,PartyCode,AreaType,AreaNum,OfficeSeqNo,BallotOrder,CandidateID,CandidateName,"
    "CurrentDateTime,VoteFor,CandidateVotes,CandidatePercentage,PrecinctsReporting"
)
HOUSE = "For Representative in Congress - 2  Year Term"
SENATE = "For United States Senator - 6  Year Term"


def _line(race_id: int, race: str, party: str, area_type: str, area: str, cand: int, votes: int) -> str:
    return (
        f'{race_id},"{race}","{party}","{area_type}","{area}",103,,{cand},"Some  Name ",'
        f'11/12/2026 4:51:26 AM,1,{votes},0.5,="438/438",'
    )


def _csv(tmp_path: Path, name: str, lines: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\r\n".join([HEADER, *lines]) + "\r\n")
    return path


def test_2026_csv_districts_senate_and_skipped_contests(tmp_path: Path) -> None:
    cg = _csv(
        tmp_path,
        "NE_2026GE_resultsCSV_CG.csv",
        [
            _line(1, HOUSE, "REP", "CG", "District 01", 11, 127001),
            _line(1, HOUSE, "DEM", "CG", "District 01", 12, 118135),
            _line(1, HOUSE, "LIB", "CG", "District 01", 13, 4611),
            _line(2, HOUSE, "DEM", "CG", "District 02", 21, 143785),
            _line(2, HOUSE, "REP", "CG", "District 02", 22, 103494),
        ],
    )
    sw = _csv(
        tmp_path,
        "NE_2026GE_resultsCSV_SW.csv",
        [
            _line(5, SENATE, "REP", "SW", "", 51, 378244),
            _line(5, SENATE, "PET", "SW", "", 52, 331250),
            _line(6, "For United States Senator - 2  Year Term", "DEM", "SW", "", 61, 999),
            _line(7, "For Governor and Lt. Governor", "DEM", "SW", "", 71, 321145),
        ],
    )
    out = se.extract("NE", [cg, sw])
    assert [
        (o, None if pd.isna(d) else int(d)) for o, d in zip(out["office"], out["district_num"], strict=True)
    ] == [
        ("us_house", 1),
        ("us_house", 2),
        ("us_senate", None),
    ]
    cd1 = out.iloc[0]
    assert (cd1["dem_votes"], cd1["rep_votes"], cd1["other_votes"]) == (118135, 127001, 4611)
    assert out.iloc[1]["winner_party"] == "DEMOCRAT"
    senate = out.iloc[2]  # petition candidate is other; no Democrat on the ballot
    assert (senate["dem_votes"], senate["rep_votes"], senate["other_votes"]) == (0, 378244, 331250)
    assert len(se.extract("NE", [sw])) == 1  # each file also extracts on its own (daily capture)


def test_2026_csv_refuses_county_rows_and_unexpected_structure(tmp_path: Path) -> None:
    county_rows = [_line(5, SENATE, "REP", "SW", "", 51, 10), _line(5, SENATE, "REP", "SW", "", 51, 20)]
    with pytest.raises(ValueError, match="more than once"):
        ne.nebraska([_csv(tmp_path, "a.csv", county_rows)])
    with pytest.raises(ValueError, match="not a statewide total"):
        ne.nebraska([_csv(tmp_path, "b.csv", [_line(5, SENATE, "REP", "CTY", "Adams", 51, 10)])])
    with pytest.raises(ValueError, match="not a district total"):
        ne.nebraska([_csv(tmp_path, "c.csv", [_line(1, HOUSE, "REP", "CG", "Lancaster", 11, 10)])])
    with pytest.raises(ValueError, match="unrecognized federal contest"):
        ne.nebraska([_csv(tmp_path, "d.csv", [_line(1, "For Congress", "REP", "CG", "District 01", 11, 1)])])
    with pytest.raises(ValueError, match="no U.S. House or Senate"):
        ne.nebraska([_csv(tmp_path, "e.csv", [_line(7, "For Governor", "DEM", "SW", "", 71, 5)])])
    bad_header = tmp_path / "f.csv"
    bad_header.write_text("RaceID,RaceName\r\n1,x\r\n")
    with pytest.raises(ValueError, match="unexpected header"):
        ne.nebraska([bad_header])


def test_banner_label() -> None:
    assert ne.banner_label("<h2> Unofficial Results </h2>") == "unofficial"
    assert ne.banner_label("<h2>Official Results</h2>") == "official"
    assert ne.banner_label("<h2>Results</h2>") == "unknown"
    assert ne.banner_label("<p>Unofficial Results</p><p>Official Results</p>") == "unknown"
