"""Idaho layouts: 2024 raw_races table and the 2026 ballot-items JSON (synthetic)."""

import json

import pandas as pd
import pytest

from election_prediction.data import state_extraction as se
from election_prediction.data.state_layouts import id as idaho

CD1 = "United States Representative District 1"


def _raw(rows: list[tuple[str, str, str, object, str, int]]) -> pd.DataFrame:
    cols = ["County", "Precinct", "Race", "Party", "Candidate", "Votes"]
    return pd.DataFrame([dict(zip(cols, r, strict=True)) for r in rows]).assign(RaceType="Federal")


def test_raw_races_sums_precincts_and_drops_over_and_undervotes():
    table = _raw(
        [
            ("Ada County", "1001", CD1, "Democratic", "Dee", 10),
            ("Ada County", "1001", CD1, "Republican", "Arr", 20),
            ("Ada County", "1001", CD1, "Independent", "W (Write-In)", 1),
            ("Ada County", "1001", CD1, None, "Overvotes", 4),
            ("Ada County", "1001", CD1, float("nan"), "Undervotes", 6),
            ("Ada County", "1002", CD1, "Democratic", "Dee", 5),
            ("Ada County", "1002", CD1, "Republican", "Arr", 7),
            ("Ada County", "1001", "United States President", "Democratic", "P", 99),
            ("Ada County", "1001", "State Senator District 1", "Republican", "S", 99),
        ]
    )
    out = se.validate_extracted(idaho.raw_races(table, source="x"))
    assert out[["office", "district_num", "dem_votes", "rep_votes", "other_votes"]].values.tolist() == [
        ["us_house", 1, 15, 27, 1]
    ]


def test_raw_races_fails_loudly():
    with pytest.raises(ValueError, match="without a party"):
        idaho.raw_races(_raw([("Ada County", "1", CD1, None, "Mystery", 4)]), source="x")
    row = ("Ada County", "1", CD1, "Democratic", "Dee", 4)
    with pytest.raises(ValueError, match="repeated precinct/race/candidate"):
        idaho.raw_races(_raw([row, row]), source="x")
    with pytest.raises(ValueError, match="unrecognized federal contest"):
        idaho.raw_races(
            _raw([("Ada County", "1", "United States Representative", "Democratic", "D", 4)]), source="x"
        )
    with pytest.raises(ValueError, match="missing columns"):
        idaho.raw_races(_raw([row]).drop(columns="Party"), source="x")


def _option(name: str, votes: object, party: str | None, write_in: bool = False) -> dict:
    return {
        "name": [{"languageId": "es", "text": "otro"}, {"languageId": "en", "text": name}],
        "voteCount": votes,
        "party": {"abbreviation": party} if party else None,
        "isWriteIn": write_in,
    }


def _item(name: str, options: list[dict], total: int | None, kind: str = "Candidate") -> dict:
    return {
        "name": [{"languageId": "en", "text": name}],
        "contestType": kind,
        "voteTotal": total,
        "summaryResults": {"ballotOptions": options},
    }


def _payload(items: list[dict]) -> dict:
    return {"data": items, "limit": 0, "offset": 0, "totalRecordCount": len(items)}


def test_ballot_items_reads_contest_totals_and_ignores_the_election_record(tmp_path):
    items = [
        _item("United States Senator", [_option("R", 400, "REP"), _option("I", 250, "IND")], 650),
        _item(CD1, [_option("R", 30, "REP"), _option("D", 20, "DEM"), _option("W", 2, None, True)], 52),
        _item("Governor", [_option("R", 1, "REP")], 1),
        _item("United States Senator - Special Unexpired Term", [_option("D", 9, "DEM")], 9),
        _item("Proposition 1", [], None, kind="Referendum"),
    ]
    results, meta = tmp_path / "items.json", tmp_path / "election.json"
    results.write_text(json.dumps(_payload(items)))
    meta.write_text(json.dumps({"isOfficialResults": False, "jurisdictionId": "j"}))
    out = se.extract("ID", [results, meta])
    assert out[["office", "dem_votes", "rep_votes", "other_votes"]].values.tolist() == [
        ["us_house", 20, 30, 2],
        ["us_senate", 0, 400, 250],
    ]
    assert out["district_num"].tolist()[0] == 1
    with pytest.raises(ValueError, match="exactly one ballot-items file"):
        se.extract("ID", [meta])


def test_ballot_items_fails_loudly():
    good = [_option("R", 30, "REP"), _option("D", 20, "DEM")]
    with pytest.raises(ValueError, match="do not add up to voteTotal"):
        idaho.ballot_item_races(_payload([_item(CD1, good, 51)]), source="x")
    truncated = {**_payload([_item(CD1, good, 50)]), "totalRecordCount": 145}
    with pytest.raises(ValueError, match="holds 1 of 145"):
        idaho.ballot_item_races(truncated, source="x")
    with pytest.raises(ValueError, match="has no party"):
        idaho.ballot_item_races(_payload([_item(CD1, [_option("X", 5, None)], 5)]), source="x")
    with pytest.raises(ValueError, match="not a whole number"):
        idaho.ballot_item_races(_payload([_item(CD1, [_option("X", "5", "DEM")], 5)]), source="x")
    with pytest.raises(ValueError, match="no candidate results"):
        idaho.ballot_item_races(_payload([_item(CD1, [], None)]), source="x")
    with pytest.raises(ValueError, match="no U.S. House or Senate"):
        idaho.ballot_item_races(_payload([_item("Governor", good, 50)]), source="x")
    with pytest.raises(ValueError, match="'data' list"):
        idaho.ballot_item_races([], source="x")


def test_summary_report_totals_buckets_inconsistent_county_party_labels():
    table = pd.DataFrame(
        [
            ("Ada County", CD1, "Ballots Cast", None, 100),
            ("Ada County", CD1, "Dee", "Democratic Party", 40),
            ("Ada County", CD1, "Arr", "Republican Party", 50),
            ("Ada County", CD1, "Over Votes", None, 3),
            ("Adams County", CD1, "Dee", "Democratic", 4),
            ("Adams County", CD1, "Arr", "Republican", 5),
            ("Adams County", CD1, "Eye", "Independent", 1),
            ("Ada County", "Governor", "Gee", "Republican", 77),
        ],
        columns=["County", "Office Name", "Ballot Name", "Party", "Total"],
    )
    assert idaho.summary_report_totals(table).to_dict("records") == [
        {"office": "us_house", "district_num": 1, "dem_votes": 44, "rep_votes": 55}
    ]
