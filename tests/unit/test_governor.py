"""Gubernatorial ingestion: office labels, vote modes, fusion, and the coattails table."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.data import governor as gov


# ------------------------------------------------------------ office labels
@pytest.mark.parametrize(
    ("office", "expected"),
    [
        ("GOVERNOR", True),
        ("Governor", True),
        ("GOVERNOR AND LIEUTENANT GOVERNOR", True),  # North Dakota joint ticket
        ("  governor  and   lieutenant governor ", True),  # whitespace normalised
        ("LIEUTENANT GOVERNOR", False),  # a different race entirely
        ("GOVERNOR'S COUNCIL", False),
        ("STATE REPRESENTATIVE", False),
    ],
)
def test_governor_office_matching_excludes_lieutenant_governor(office, expected):
    """A substring match on 'GOVERNOR' would wrongly sweep in the Lt. Gov. race."""
    assert gov.is_governor(office) is expected


# ------------------------------------------------------------ file discovery
def test_find_precinct_files_accepts_both_name_separators(tmp_path):
    """MEDSL's 2020 release mixes '2020-xx-' and '2020_in_'; matching one loses Indiana."""
    d = tmp_path / "source=medsl/dataset=precinct_by_state/vintage=2020"
    d.mkdir(parents=True)
    for name in (
        "2020-nc-precinct-general.csv",
        "2020_in_precinct_general.csv",
        "2020-precincts-codebook.md",
        "README.md",
    ):
        (d / name).write_text("x")

    found = {p.name for p in gov.find_precinct_files(tmp_path, 2020)}
    assert found == {"2020-nc-precinct-general.csv", "2020_in_precinct_general.csv"}
    assert (
        gov.state_from_filename(next(p for p in gov.find_precinct_files(tmp_path, 2020) if "_in_" in p.name))
        == "IN"
    )


# ------------------------------------------------------------- vote modes
def _precinct_rows(rows: list[dict]) -> pd.DataFrame:
    base = {
        "year": "2024",
        "state_po": "XX",
        "state_fips": "01",
        "county_fips": "01001",
        "county_name": "A",
        "precinct": "P1",
        "office": "governor",
        "stage": "gen",
        "special": "FALSE",
        "writein": "FALSE",
        "district": "",
        "party_detailed": "DEMOCRAT",
        "party_simplified": "DEMOCRAT",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_total_row_wins_over_mode_breakdowns():
    """Delaware and Indiana 2024 ship TOTAL *and* breakdowns; summing both doubles them."""
    df = _precinct_rows(
        [
            {"candidate": "A", "mode": "TOTAL", "candidatevotes": 100},
            {"candidate": "A", "mode": "EARLY VOTING", "candidatevotes": 60},
            {"candidate": "A", "mode": "ELECTION DAY", "candidatevotes": 40},
        ]
    )
    out, stats = gov.collapse_precinct_modes(df)
    assert out["candidatevotes"].sum() == 100, "must keep the published total, not 200"
    assert stats["mode_rows_collapsed"] == 2


def test_breakdowns_are_summed_when_no_total_row():
    """North Carolina publishes disjoint modes with no TOTAL, so they must be added."""
    df = _precinct_rows(
        [
            {"candidate": "A", "mode": "ELECTION DAY", "candidatevotes": 40},
            {"candidate": "A", "mode": "EARLY VOTING", "candidatevotes": 60},
            {"candidate": "A", "mode": "PROVISIONAL", "candidatevotes": 5},
        ]
    )
    out, _ = gov.collapse_precinct_modes(df)
    assert out["candidatevotes"].sum() == 105


def test_modes_collapse_within_precinct_not_across_them():
    """Without precinct in the key, every precinct in a state would merge into one."""
    df = _precinct_rows(
        [
            {"candidate": "A", "precinct": "P1", "mode": "TOTAL", "candidatevotes": 10},
            {"candidate": "A", "precinct": "P2", "mode": "TOTAL", "candidatevotes": 20},
        ]
    )
    out, _ = gov.collapse_precinct_modes(df)
    assert len(out) == 2
    assert out["candidatevotes"].sum() == 30


# ---------------------------------------------------------------- fusion
def test_fusion_lines_are_summed_and_keep_the_major_party_label():
    """Vermont's Zuckerman ran on Democratic and Progressive lines in 2020."""
    df = _precinct_rows(
        [
            {
                "candidate": "ZUCKERMAN",
                "mode": "TOTAL",
                "candidatevotes": 70,
                "party_detailed": "DEMOCRATIC",
                "party_simplified": "DEMOCRAT",
            },
            {
                "candidate": "ZUCKERMAN",
                "mode": "TOTAL",
                "candidatevotes": 30,
                "party_detailed": "PROGRESSIVE",
                "party_simplified": "OTHER",
            },
        ]
    )
    county = gov.aggregate_to_county(df)
    row = county[county["candidate"] == "ZUCKERMAN"]
    assert len(row) == 1, "one candidate, not one row per party line"
    assert int(row.iloc[0]["votes"]) == 100
    assert row.iloc[0]["party_simplified"] == "DEMOCRAT"


# ------------------------------------------------------------- coattails
def _county_rows(office: str, dem: int, rep: int, county="01001") -> list[dict]:
    return [
        {
            "cycle": 2024,
            "state_po": "XX",
            "state_fips": "01",
            "county_name": "A",
            "county_fips": county,
            "office": office,
            "candidate": f"{office[:1].upper()}D",
            "party_simplified": "DEMOCRAT",
            "votes": dem,
        },
        {
            "cycle": 2024,
            "state_po": "XX",
            "state_fips": "01",
            "county_name": "A",
            "county_fips": county,
            "office": office,
            "candidate": f"{office[:1].upper()}R",
            "party_simplified": "REPUBLICAN",
            "votes": rep,
        },
    ]


def test_coattails_measures_ticket_split_and_roll_off():
    county = pd.DataFrame(_county_rows("governor", 60, 40) + _county_rows("president", 45, 55))
    ct = gov.build_coattails_table(county)

    assert len(ct) == 1
    row = ct.iloc[0]
    assert row["gov_two_party_dem"] == pytest.approx(0.60)
    assert row["pres_two_party_dem"] == pytest.approx(0.45)
    # Governor ran 15 points ahead of the president in the same county.
    assert row["ticket_split"] == pytest.approx(0.15)
    # 100 governor votes against 100 presidential votes: no roll-off.
    assert row["roll_off"] == pytest.approx(0.0)


def test_roll_off_is_positive_when_voters_skip_the_governor_race():
    county = pd.DataFrame(_county_rows("governor", 45, 45) + _county_rows("president", 50, 50))
    ct = gov.build_coattails_table(county)
    assert ct.iloc[0]["roll_off"] == pytest.approx(0.10), "90 of 100 presidential voters voted for governor"


def test_coattails_is_empty_without_a_presidential_race():
    """Midterm cycles have no president, so there is nothing to compare against."""
    ct = gov.build_coattails_table(pd.DataFrame(_county_rows("governor", 60, 40)))
    assert ct.empty
    assert list(ct.columns) == gov.COATTAILS_COLUMNS


@pytest.mark.parametrize(
    ("office", "expected"),
    [
        # MEDSL writes the same joint ticket both ways across its own releases.
        ("GOVERNOR AND LT. GOVERNOR", True),  # 2016 state-office file (MT, ND, UT)
        ("GOVERNOR AND LT GOVERNOR", True),
        ("GOVERNOR AND LIEUTENANT GOVERNOR", True),  # precinct files
        ("LT. GOVERNOR", False),  # still a different race after expansion
        ("LT GOVERNOR", False),
    ],
)
def test_lieutenant_abbreviation_is_normalised(office, expected):
    """Matching only the long spelling silently dropped Montana, North Dakota and Utah."""
    assert gov.is_governor(office) is expected


def test_missing_major_party_is_flagged_not_silently_scored():
    """VT/ND fusion tickets read as OTHER, so their two-party share is an artefact."""
    county = pd.DataFrame(
        # Governor race where the Democrat is labelled OTHER (fusion ticket).
        [
            {
                "cycle": 2024,
                "state_po": "VT",
                "state_fips": "50",
                "county_name": "A",
                "county_fips": "50001",
                "office": "governor",
                "candidate": "SCOTT",
                "party_simplified": "REPUBLICAN",
                "votes": 60,
            },
            {
                "cycle": 2024,
                "state_po": "VT",
                "state_fips": "50",
                "county_name": "A",
                "county_fips": "50001",
                "office": "governor",
                "candidate": "CHARLESTIN",
                "party_simplified": "OTHER",
                "votes": 40,
            },
        ]
        + _county_rows("president", 45, 55, county="50001")
    )
    county.loc[county["office"] == "president", "state_po"] = "VT"
    ct = gov.build_coattails_table(county)
    assert ct.iloc[0]["two_party_suspect"], "a major party at zero votes must be flagged"


def test_normal_race_is_not_flagged_suspect():
    county = pd.DataFrame(_county_rows("governor", 60, 40) + _county_rows("president", 45, 55))
    ct = gov.build_coattails_table(county)
    assert not ct.iloc[0]["two_party_suspect"]
