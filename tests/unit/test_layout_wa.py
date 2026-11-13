"""Washington layouts: 2024 legacy CSV export and 2026 Summary Results sheet (synthetic fixtures)."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.state_layouts import wa

HEADER = ("Office Name", "Contest ID", "Ballot Name", "Choice ID", "Party", "Total")
CD = "Congressional District {} - U.S. Representative"


def _contest(name: str, contest_id: str, candidates: list[tuple[str, str, str | None, int]]) -> list[tuple]:
    return [
        (name, contest_id, "Ballots Cast", "", None, 999_999),
        *[(name, contest_id, *c) for c in candidates],
        (name, contest_id, "Over Votes", "", None, 11),
        (name, contest_id, "Under Votes", "", None, 2222),
    ]


def _sheet() -> list[tuple]:
    return [
        HEADER,
        *_contest("Initiative Measure No. 1", "7", [("Yes", "Yes-1-", None, 5), ("No", "No-2-", None, 6)]),
        *_contest(
            CD.format(1),
            "101",
            [
                ("A", "1", "(Prefers Democratic Party)", 196859),
                ("B", "2", "(Prefers Republican Party)", 94350),
                ("Write-in", "9910", None, 889),
            ],
        ),
        *_contest(  # top-two general between two Republicans
            CD.format(4),
            "104",
            [
                ("C", "3", "(Prefers Republican Party)", 136175),
                ("D", "4", "(Prefers GOP Party)", 153477),
                ("Write-in", "9910", None, 5400),
            ],
        ),
        *_contest(
            CD.format(10),
            "110",
            [
                ("E", "5", "(Prefers Democratic Party)", 300),
                ("F", "6", "(States No Party Preference)", 200),
                ("Write-in", "9910", None, 1),
            ],
        ),
        *_contest(
            "Legislative District 6 - State Senator", "206", [("G", "7", "(Prefers Democratic Party)", 9)]
        ),
        *_contest("U.S. Senator - Short Term", "300", [("H", "8", "(Prefers Democratic Party)", 77)]),
    ]


def test_2026_summary_drops_non_vote_lines_and_handles_same_party_generals() -> None:
    out = wa.summary_rows(_sheet()).set_index("district_num")
    assert sorted(out.index) == [1, 4, 10]  # measure, legislature and short-term Senate skipped
    assert (out.loc[1, "dem_votes"], out.loc[1, "rep_votes"], out.loc[1, "other_votes"]) == (
        196859,
        94350,
        889,
    )
    assert (out.loc[4, "dem_votes"], out.loc[4, "rep_votes"], out.loc[4, "other_votes"]) == (0, 289652, 5400)
    assert out.loc[4, "winner_party"] == "REPUBLICAN"
    assert (out.loc[10, "dem_votes"], out.loc[10, "rep_votes"], out.loc[10, "other_votes"]) == (300, 0, 201)


def test_2026_workbook_round_trip(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    summary = workbook.active
    summary.title = "Summary Results"
    for row in _sheet():
        summary.append(row)
    precinct = workbook.create_sheet("Precinct Results")
    precinct.append(("Precinct", *HEADER))
    precinct.append(("Adams County", CD.format(1), "101", "A", "1", "(Prefers Democratic Party)", 1))
    path = tmp_path / "WA_2026GE_AllResults.xlsx"
    workbook.save(path)
    out = se.extract("WA", [path])
    assert list(out["district_num"]) == [1, 4, 10]
    assert (
        int(out.loc[out["district_num"] == 1, "dem_votes"].iloc[0]) == 196859
    )  # the precinct sheet is not read
    workbook.remove(summary)
    workbook.save(path)
    with pytest.raises(ValueError, match="no 'Summary Results' sheet"):
        wa.washington([path])


def test_2026_summary_refuses_unexpected_structure() -> None:
    with pytest.raises(ValueError, match="unexpected Summary Results header"):
        wa.summary_rows([("Office", "Contest ID", "Ballot Name", "Choice ID", "Party", "Total")])
    unlabelled = [HEADER, (CD.format(1), "101", "A", "1", None, 5)]
    with pytest.raises(ValueError, match="with party None"):
        wa.summary_rows(unlabelled)
    no_choice = [HEADER, (CD.format(1), "101", "A", "", "(Prefers Democratic Party)", 5)]
    with pytest.raises(ValueError, match="without contest, name or choice ID"):
        wa.summary_rows(no_choice)
    text_total = [HEADER, (CD.format(1), "101", "A", "1", "(Prefers Democratic Party)", "5")]
    with pytest.raises(ValueError, match="bad vote total"):
        wa.summary_rows(text_total)
    odd_label = [HEADER, (CD.format(1), "101", "A", "1", "Democratic", 5)]
    with pytest.raises(ValueError, match="unrecognized party label"):
        wa.summary_rows(odd_label)
    renamed = [HEADER, ("U.S. Representative District 1", "101", "A", "1", "(Prefers Democratic Party)", 5)]
    with pytest.raises(ValueError, match="unrecognized federal contest"):
        wa.summary_rows(renamed)
    split = [*_sheet(), (CD.format(1), "999", "Z", "77", "(Prefers Republican Party)", 5)]
    with pytest.raises(ValueError, match="more than one contest"):
        wa.summary_rows(split)
    with pytest.raises(ValueError, match="no U.S. House or Senate"):
        wa.summary_rows(_sheet()[:6])


@pytest.mark.parametrize(
    ("label", "bucket"),
    [
        ("(Prefers Democratic Party)", "DEM"),
        ("(Prefers Democrat Party)", "DEM"),
        ("(Prefers Republican Party)", "REP"),
        ("(Prefers GOP Party)", "REP"),
        ("(Prefers MAGA Republican Party)", "REP"),
        ("(Prefers Libertarian Party)", "OTHER"),
        ("(States No Party Preference)", "OTHER"),
        (" ", "OTHER"),
        (None, "OTHER"),
    ],
)
def test_party_preference(label: str | None, bucket: str) -> None:
    assert wa.party_preference(label) == bucket


def test_party_preference_refuses_ambiguous_labels() -> None:
    with pytest.raises(ValueError, match="both major parties"):
        wa.party_preference("(Prefers Democratic Republican Party)")
    with pytest.raises(ValueError, match="unrecognized party label"):
        wa.party_preference("Democratic Party Nominees")


def test_2024_csv_mixed_case_contests_write_ins_and_senate(tmp_path: Path) -> None:
    rows = [
        ("President/Vice President", "X / Y", "Democratic Party Nominees", 2245849),
        ("U.S. Senator", "Maria Cantwell", "(Prefers Democratic Party)", 2252577),
        ("U.S. Senator", "Dr Raul Garcia", "(Prefers GOP Party)", 1549187),
        ("U.S. Senator", "WRITE-IN", " ", 10627),
        ("CONGRESSIONAL DISTRICT 3 - U.S. Representative", "M", "(Prefers Democratic Party)", 215177),
        ("CONGRESSIONAL DISTRICT 3 - U.S. Representative", "J", "(Prefers Republican Party)", 199054),
        ("CONGRESSIONAL DISTRICT 3 - U.S. Representative", "WRITE-IN", " ", 1673),
        (
            "Congressional District 9 - U.S. Representative",
            "Adam Smith",
            "(Prefers Democratic Party)",
            182780,
        ),
        ("Congressional District 9 - U.S. Representative", "M C", "(Prefers Democratic Party)", 90601),
        ("Congressional District 9 - U.S. Representative", "WRITE-IN", " ", 5917),
    ]
    frame = pd.DataFrame(rows, columns=["Race", "Candidate", "Party", "Votes"])
    frame["PercentageOfTotalVotes"] = 1.0
    frame["JurisdictionName"] = "Congressional"
    path = tmp_path / "20241105_Congressional.csv"
    frame.to_csv(path, index=False, quoting=1)
    out = se.extract_historical("WA", [path])
    senate = out[out["office"] == "us_senate"].iloc[0]
    assert (senate["dem_votes"], senate["rep_votes"], senate["other_votes"]) == (2252577, 1549187, 10627)
    cd3 = out[out["district_num"] == 3].iloc[0]
    assert (cd3["dem_votes"], cd3["rep_votes"]) == (215177, 199054)
    cd9 = out[out["district_num"] == 9].iloc[0]  # two Democrats: summed, no Republican
    assert (cd9["dem_votes"], cd9["rep_votes"], cd9["other_votes"]) == (273381, 0, 5917)
    path.write_text("Race,Candidate\nx,y\n")
    with pytest.raises(ValueError, match="unexpected header"):
        wa.washington_2024([path])
