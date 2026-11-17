"""California layouts: Statement of Vote table and the media us-rep.json (synthetic)."""

import json

import pandas as pd
import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.state_layouts import ca


def _sov(rows: list[tuple[str, str, str, str, str, int]]) -> pd.DataFrame:
    cols = ["County Id", "Contest ID", "Contest Name", "Candidate ID", "Party Name", "Vote Total"]
    frame = pd.DataFrame([dict(zip(cols, r, strict=True)) for r in rows]).astype(str)
    return frame.assign(**{"Election Name": "November 5, 2024, General Election"})


def test_sov_sums_counties_handles_same_party_generals_and_skips_partial_term():
    cd12, cd20 = "United States Representative District 12", "United States Representative District 20"
    table = _sov(
        [
            ("1", "110000120000", cd12, "10", "Democratic", 100),
            ("1", "110000120000", cd12, "11", "Democratic", 60),
            ("38", "110000120000", cd12, "10", "Democratic", 5),
            ("38", "110000120000", cd12, "11", "Democratic", 50),
            ("10", "110000200000", cd20, "20", "Republican", 70),
            ("10", "110000200000", cd20, "21", "Republican", 30),
            ("1", "100000000002", "US Senate - 2", "30", "Democratic", 900),
            ("1", "100000000002", "US Senate - 2", "31", "Republican", 600),
            ("1", "100100000003", "US Senate - 3 Partial/Unexpired Term", "30", "Democratic", 1),
            ("1", "120000010000", "State Senate District 1", "40", "Republican", 5),
            ("1", "010000000000", "President", "50", "No Party Preference", 5),
        ]
    )
    out = se.validate_extracted(ca.sov_races(table, source="x"))
    by = {
        (r["office"], None if pd.isna(r["district_num"]) else int(r["district_num"])): r
        for r in out.to_dict("records")
    }
    assert set(by) == {("us_house", 12), ("us_house", 20), ("us_senate", None)}
    assert (by["us_house", 12]["dem_votes"], by["us_house", 12]["rep_votes"]) == (215, 0)
    assert by["us_house", 12]["winner_party"] == "DEMOCRAT"
    assert (by["us_house", 20]["dem_votes"], by["us_house", 20]["rep_votes"]) == (0, 100)
    assert (by["us_senate", None]["dem_votes"], by["us_senate", None]["rep_votes"]) == (900, 600)


def test_sov_fails_loudly():
    row = ("1", "110000010000", "United States Representative District 1", "1", "Democratic", 5)
    with pytest.raises(ValueError, match="repeated county/contest/candidate"):
        ca.sov_races(_sov([row, row]), source="x")
    with pytest.raises(ValueError, match="unrecognized federal contest"):
        ca.sov_races(
            _sov([("1", "1", "United States Representative At Large", "1", "Democratic", 5)]), source="x"
        )
    with pytest.raises(ValueError, match="expected one general election"):
        ca.sov_races(_sov([row]).assign(**{"Election Name": "March 5, 2024, Primary Election"}), source="x")
    with pytest.raises(ValueError, match="no U.S. House or Senate"):
        ca.sov_races(_sov([("1", "1", "President", "1", "Democratic", 5)]), source="x")


def _entry(district: int, scope: str, *candidates: tuple[str, str, str]) -> dict:
    return {
        "raceTitle": f"United States Representative District {district} - {scope} Results",
        "Reporting": "100%",
        "ReportingTime": "November 11, 2026, 6:51 p.m.",
        "candidates": [{"Name": n, "Party": p, "Votes": v, "Percent": "0"} for n, p, v in candidates],
    }


def test_media_json_uses_districtwide_totals_checked_against_counties(tmp_path):
    records = [
        _entry(1, "Districtwide", ("A", "Dem", "1,200"), ("B", "Rep", "900")),
        _entry(1, "Butte County", ("A", "Dem", "200"), ("B", "Rep", "500")),
        _entry(1, "Shasta County", ("A", "Dem", "1,000"), ("B", "Rep", "400")),
        _entry(6, "Districtwide", ("C", "Dem", "50"), ("D", "NPP", "40")),
        _entry(7, "Districtwide", ("E", "Dem", "30"), ("F", "Dem", "20")),
    ]
    path = tmp_path / "us-rep.json"
    path.write_text(json.dumps(records))
    out = se.extract("CA", [path])
    assert out[["district_num", "dem_votes", "rep_votes", "other_votes"]].values.tolist() == [
        [1, 1200, 900, 0],
        [6, 50, 0, 40],
        [7, 50, 0, 0],
    ]


def test_media_json_fails_loudly():
    total = _entry(1, "Districtwide", ("A", "Dem", "1,200"), ("B", "Rep", "900"))
    with pytest.raises(ValueError, match="do not add up"):
        ca.media_races([total, _entry(1, "Butte County", ("A", "Dem", "1"), ("B", "Rep", "900"))], source="x")
    with pytest.raises(ValueError, match="two districtwide"):
        ca.media_races([total, total], source="x")
    with pytest.raises(ValueError, match="unexpected contest entry"):
        ca.media_races(
            [{"raceTitle": "State Senate District 1 - Districtwide Results", "candidates": []}], source="x"
        )
    with pytest.raises(ValueError, match="unknown party label"):
        ca.media_races([_entry(1, "Districtwide", ("A", "Whig", "1"))], source="x")
    with pytest.raises(ValueError, match="not a whole number"):
        ca.media_races([_entry(1, "Districtwide", ("A", "Dem", "n/a"))], source="x")
    with pytest.raises(ValueError, match="without a districtwide"):
        ca.media_races([total, _entry(2, "Butte County", ("A", "Dem", "1"))], source="x")
    with pytest.raises(ValueError, match="non-empty JSON list"):
        ca.media_races({}, source="x")


def test_ascii_totals_reads_statewide_messages_with_party_codes():
    votes = "\r\n".join(
        [
            "[B|CAS|1|20261111|2328206]",
            "[A|CAS|2|1|U|0|0|627|627|100.0|5|9|57.3|202611032051|202611091703]",
            "[V|CAS|3|110000010000|59|788|788|F|3791|1200|100.0|57.1|3800|900|100.0|42.9]",
            "[V|CAS|4|110000010000|4|137|137|U|3791|200|100.0|28.6|3800|500|100.0|71.4]",
            "[V|CAS|5|110000070000|59|10|10|F|11|30|60.0|60.0|12|20|40.0|40.0]",
            "[V|CAS|6|190000000045|59|23|23|U|YES|13013|57.6|NO|9573|42.4]",
        ]
    )
    candidates = "\n".join(
        [
            "[C|CAS|2|110000010000|3791||Gee|Mike||01|Mike Gee|]",
            "[C|CAS|3|110000010000|3800||Aitch|Jim||02|Jim Aitch|]",
            "[C|CAS|4|110000070000|11||X|A||01|A X|]",
            "[C|CAS|5|110000070000|12||Y|B||01|B Y|]",
        ]
    )
    assert ca.ascii_totals(votes, candidates).to_dict("records") == [
        {"office": "us_house", "district_num": 1, "dem_votes": 1200, "rep_votes": 900},
        {"office": "us_house", "district_num": 7, "dem_votes": 50, "rep_votes": 0},
    ]
    with pytest.raises(ValueError, match="not in the candidate file"):
        ca.ascii_totals(votes, "[C|CAS|2|110000010000|3791||Gee|Mike||01|Mike Gee|]")
