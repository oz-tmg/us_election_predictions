"""Alabama layouts: 2024 precinct sheets and the 2026 election-night export (synthetic)."""

import pandas as pd
import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.state_layouts import al

HOUSE6 = "UNITED STATES REPRESENTATIVE, 6TH CONGRESSIONAL DISTRICT"


def _sheet(rows: list[list[object]]) -> pd.DataFrame:
    head = ["Contest Title", "Party", "Candidate", "1 TOWN HALL", "ABSENTEE", "PROVISIONAL"]
    return pd.DataFrame([head, *rows]).astype(str)


def test_precinct_sheet_sums_precinct_columns_and_drops_over_under_votes():
    sheet = _sheet(
        [
            ["BALLOTS CAST - TOTAL", "", "Ballots Cast - Total", 500, 40, 2],
            ["PRESIDENT AND VICE PRESIDENT OF THE UNITED STATES", "DEM", "A", 1, 1, 1],
            [HOUSE6 + "   ", "DEM", "Dee", 100, 20, 1],
            [HOUSE6, "REP", "Arr", 200, 10, 0],
            [HOUSE6, "NON", "Write-In", 3, 0, 0],
            [HOUSE6, "", "Over Votes", 9, 9, 9],
            [HOUSE6, "nan", "Under Votes", 7, 7, 7],
        ]
    )
    got = al.precinct_sheet_candidates(sheet, source="x.xls")
    assert [(r["district"], r["party"], r["votes"]) for r in got] == [
        (6, "DEM", 121),
        (6, "REP", 210),
        (6, "NON", 3),
    ]
    race = al._races(pd.DataFrame(got), source="x").iloc[0]
    assert (race["dem_votes"], race["rep_votes"], race["other_votes"]) == (121, 210, 3)


def test_precinct_sheet_refuses_unknown_layout_and_partyless_candidate():
    with pytest.raises(ValueError, match="Contest Title/Party/Candidate"):
        al.precinct_sheet_candidates(pd.DataFrame([["Contest", "Party", "Candidate", "P1"]]), source="x")
    with pytest.raises(ValueError, match="no party code"):
        al.precinct_sheet_candidates(_sheet([[HOUSE6, "", "Somebody", 1, 0, 0]]), source="x")
    with pytest.raises(ValueError, match="not a non-negative whole number"):
        al.precinct_sheet_candidates(_sheet([[HOUSE6, "DEM", "Dee", "1.5", 0, 0]]), source="x")


def _export(rows: list[tuple[str, str, str, str, int, str]]) -> pd.DataFrame:
    cols = ["County Code", "Contest Code", "Contest Title", "Candidate Number", "Votes", "Party Code"]
    frame = pd.DataFrame([dict(zip(cols, r, strict=True)) for r in rows]).astype(str)
    return frame.assign(**{"Election Title": "2026 GENERAL ELECTION", "Candidate Name": "n"})


def test_export_sums_counties_and_skips_special_contests(tmp_path):
    senate = "UNITED STATES SENATOR" + " " * 30
    table = _export(
        [
            ("01", "100", senate, "001", 10, "DEM"),
            ("01", "100", senate, "002", 20, "REP"),
            ("01", "100", senate, "003", 1, "NON"),
            ("02", "100", senate, "001", 5, "DEM"),
            ("02", "100", senate, "002", 7, "REP"),
            ("02", "100", senate, "004", 2, "IND"),
            ("01", "200", "UNITED STATES REPRESENTATIVE, 2ND CONGRESSIONAL DISTRICT", "001", 4, "DEM"),
            ("01", "300", "UNITED STATES SENATOR (SPECIAL ELECTION, UNEXPIRED TERM)", "001", 99, "DEM"),
            ("01", "400", "GOVERNOR", "001", 50, "REP"),
        ]
    )
    path = tmp_path / "export.xlsx"
    with pd.ExcelWriter(path) as writer:
        table.to_excel(writer, sheet_name="AllResults", index=False)
        pd.DataFrame({"County Code": ["01"]}).to_excel(writer, sheet_name="Statistics", index=False)
    out = se.extract("AL", [path])
    senate_row = out[out["office"] == "us_senate"].iloc[0]
    assert (senate_row["dem_votes"], senate_row["rep_votes"], senate_row["other_votes"]) == (15, 27, 3)
    assert senate_row["winner_party"] == "REPUBLICAN"
    assert out[out["office"] == "us_house"]["district_num"].tolist() == [2]


def test_export_fails_loudly_on_unexpected_structure():
    good = ("01", "100", "UNITED STATES SENATOR", "001", 10, "DEM")
    with pytest.raises(ValueError, match="repeated county/contest/candidate"):
        al.export_candidates(_export([good, good]), source="x")
    with pytest.raises(ValueError, match="unrecognized federal contest"):
        al.export_candidates(
            _export([("01", "1", "UNITED STATES REPRESENTATIVE AT LARGE", "1", 1, "DEM")]), source="x"
        )
    with pytest.raises(ValueError, match="missing columns"):
        al.export_candidates(_export([good]).drop(columns="Party Code"), source="x")
    with pytest.raises(ValueError, match="expected one general election"):
        al.export_candidates(
            _export([good]).assign(**{"Election Title": "2026 PRIMARY ELECTION"}), source="x"
        )
    with pytest.raises(ValueError, match="several contest codes"):
        al.export_candidates(
            _export([good, ("02", "101", "UNITED STATES SENATOR", "001", 10, "DEM")]), source="x"
        )


PAGE = """
<h2>Unofficial Election Night Results</h2>
<td class="enrContestHeader">GOVERNOR   </td>
<td class="enrCandidateListItemCol enrCandNameCol" style="text-align: left;">A B   (DEM)</td>
<td class="enrCandidateListItemCol enrCandVoteNumCol"><div class="numberValue">9</div></td>
<td class="enrContestHeader">UNITED STATES REPRESENTATIVE, 1ST CONGRESSIONAL DISTRICT   </td>
<td class="enrCandidateListItemCol enrCandNameCol" style="text-align: left;">Dee Em        (DEM)</td>
<td class="x enrCandVotePerCol"><div class="numberValue"><span>40.0%</span></div></td>
<td class="enrCandidateListItemCol enrCandVoteNumCol"><div class="numberValue">1,234</div></td>
<td class="enrAltCandidateListItemCol enrCandNameCol" style="text-align: left;">Arr Ee   (REP)</td>
<td class="enrAltCandidateListItemCol enrCandVoteNumCol"><div class="numberValue">2,000</div></td>
<td class="enrCandidateListItemCol enrCandNameCol" style="text-align: left;">Write-In   (NON)</td>
<td class="enrCandidateListItemCol enrCandVoteNumCol"><div class="numberValue">7</div></td>
"""


def test_results_page_totals_and_label():
    totals = al.page_totals(PAGE)
    assert totals.to_dict("records") == [
        {"office": "us_house", "district_num": 1, "dem_votes": 1234, "rep_votes": 2000}
    ]
    assert al.page_label(PAGE) == "unofficial"
    assert al.page_label("<h2>Official Election Results</h2>") == "official"
    assert al.page_label("<h2>Welcome</h2>") == "unknown"
