"""North Dakota layouts: 2024 legacy CSV export and 2026 tally-enr JSON (synthetic fixtures)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.state_layouts import nd

HEADER = (
    "ContestName,PartyCode,AreaNum,CandidateName,VoteFor,"
    "CandidateVotes,CandidatePercentage,PrecinctsReporting"
)


def _csv(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "ND_2024_AllStatewide.csv"
    path.write_text("\r\n".join([HEADER, *lines]) + "\r\n")
    return path


def _row(contest: str, party: str, name: str, votes: int, county: str) -> str:
    return f'"{contest}","{party}","","{name}",1,{votes},50.00%,1/1,"{county}",'


def test_2024_sums_counties_and_skips_other_and_unexpired_contests(tmp_path: Path) -> None:
    lines = []
    for county, (rep, dem, lib, write_in) in {"Adams": (900, 200, 30, 4), "Cass": (100, 300, 5, 1)}.items():
        lines += [
            _row("Representative in Congress", "REP", "Julie  Fedorchak ", rep, county),
            _row("Representative in Congress", "DEM", "Trygve  Hammer ", dem, county),
            _row("Representative in Congress", "LIB", "Some  Body ", lib, county),
            _row("Representative in Congress", "NON", "write-in ", write_in, county),
            _row("United States Senator", "REP", "A  B ", rep + 1, county),
            _row("United States Senator", "DEM", "C  D ", dem + 1, county),
            _row("United States Senator Unexpired 2-Year Term", "DEM", "E  F ", 99999, county),
            _row("Governor and Lt. Governor", "DEM", "G and H", 77777, county),
        ]
    out = se.extract_historical("ND", [_csv(tmp_path, lines)])
    house = out[out["office"] == "us_house"].iloc[0]
    assert (house["district_num"], house["dem_votes"], house["rep_votes"], house["other_votes"]) == (
        0,
        500,
        1000,
        40,
    )
    senate = out[out["office"] == "us_senate"].iloc[0]
    assert (senate["dem_votes"], senate["rep_votes"], senate["winner_party"]) == (502, 1002, "REPUBLICAN")


def test_2024_refuses_rows_without_the_county_field_and_repeated_counties(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected 8 fields, county"):
        nd.north_dakota_2024([_csv(tmp_path, ['"Representative in Congress","REP","","X",1,5,1%,1/1'])])
    twice = [_row("Representative in Congress", "REP", "X", 5, "Adams")] * 2
    with pytest.raises(ValueError, match="repeated county rows"):
        nd.north_dakota_2024([_csv(tmp_path, twice)])
    with pytest.raises(ValueError, match="unrecognized federal contest"):
        nd.north_dakota_2024(
            [_csv(tmp_path, [_row("Representative in Congress District 2", "REP", "X", 5, "A")])]
        )


def _choice(choice_id: str, party: str, votes: int) -> dict:
    return {"choiceID": choice_id, "totalVotes": votes, "partyID": party}


def _json_2026() -> tuple[dict, dict]:
    contest_list = {
        "response": {
            "contests": {
                "10": {
                    "contestName": "Representative in Congress",
                    "choices": {
                        "1": {"name": "Julie  Fedorchak ", "partyID": "REP"},
                        "2": {"name": "Trygve  Hammer ", "partyID": "DEM"},
                        "3": {"name": "Charles  Tuttle ", "partyID": "IND"},
                        "9901": {"name": "  write-in ", "partyID": "NON"},
                    },
                },
                "11": {"contestName": "Attorney General", "choices": {"5": {"partyID": "REP"}}},
                "12": {
                    "contestName": "United States Senator Unexpired 2-Year Term",
                    "choices": {"6": {"partyID": "DEM"}},
                },
            }
        }
    }
    results = {
        "isOfficial": False,
        "response": {
            "contests": {
                "10": {
                    "totalVotes": 1545,
                    "choices": [_choice("1", "REP", 1000), _choice("2", "DEM", 500), _choice("3", "IND", 40)],
                    "writeInChoices": [_choice("9901", "NON", 5)],
                    "locations": {
                        "38001": {
                            "choices": [
                                _choice("1", "REP", 900),
                                _choice("2", "DEM", 200),
                                _choice("3", "IND", 30),
                            ],
                            "writeinChoices": [_choice("9901", "NON", 4)],
                        },
                        "38017": {
                            "choices": [
                                _choice("1", "REP", 100),
                                _choice("2", "DEM", 300),
                                _choice("3", "IND", 10),
                            ],
                            "writeinChoices": [_choice("9901", "NON", 1)],
                        },
                    },
                },
                "11": {"totalVotes": 7, "choices": [_choice("5", "REP", 7)], "locations": {}},
                "12": {"totalVotes": 9, "choices": [_choice("6", "DEM", 9)], "locations": {}},
            }
        },
    }
    return contest_list, results


def _write(tmp_path: Path, contest_list: dict, results: dict) -> list[Path]:
    paths = [tmp_path / "ND_2026GE_statewide_results.json", tmp_path / "ND_2026GE_contestlist.json"]
    paths[0].write_text(json.dumps(results))
    paths[1].write_text(json.dumps(contest_list))
    return paths


def test_2026_reads_party_from_party_id_and_numbers_the_at_large_seat_zero(tmp_path: Path) -> None:
    out = se.extract("ND", _write(tmp_path, *_json_2026()))
    assert len(out) == 1  # the unexpired-term Senate contest and other offices are skipped
    row = out.iloc[0]
    assert (row["office"], row["district_num"]) == ("us_house", 0)
    assert (row["dem_votes"], row["rep_votes"], row["other_votes"]) == (500, 1000, 45)
    assert row["winner_party"] == "REPUBLICAN"


def test_2026_refuses_totals_that_do_not_add_up(tmp_path: Path) -> None:
    contest_list, results = _json_2026()
    wrong_total = copy.deepcopy(results)
    wrong_total["response"]["contests"]["10"]["totalVotes"] = 1546
    with pytest.raises(ValueError, match="contest total 1546"):
        nd.north_dakota(_write(tmp_path, contest_list, wrong_total))
    wrong_county = copy.deepcopy(results)
    wrong_county["response"]["contests"]["10"]["locations"]["38001"]["choices"][0]["totalVotes"] = 901
    with pytest.raises(ValueError, match="county votes do not add up"):
        nd.north_dakota(_write(tmp_path, contest_list, wrong_county))


def test_2026_refuses_unknown_choices_missing_files_and_new_federal_names(tmp_path: Path) -> None:
    contest_list, results = _json_2026()
    stranger = copy.deepcopy(results)
    stranger["response"]["contests"]["10"]["choices"][1]["partyID"] = "REP"
    with pytest.raises(ValueError, match="does not match the contest list"):
        nd.north_dakota(_write(tmp_path, contest_list, stranger))
    with pytest.raises(ValueError, match="missing"):
        nd.north_dakota(_write(tmp_path, contest_list, results)[:1])
    renamed = copy.deepcopy(contest_list)
    renamed["response"]["contests"]["10"]["contestName"] = "Representative in Congress District 1"
    with pytest.raises(ValueError, match="unrecognized federal contest"):
        nd.north_dakota(_write(tmp_path, renamed, results))
