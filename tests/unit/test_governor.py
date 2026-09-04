"""Gubernatorial ingestion: office labels, vote modes, fusion, and the coattails table."""

from __future__ import annotations

import pathlib

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
def test_find_precinct_files_takes_every_data_file_regardless_of_name(tmp_path):
    """Filenames cannot be pattern-matched — MEDSL 2022 ships six conventions at once.

    Requiring a ``YYYY-xx-`` prefix matched only 5 of that release's 53 files.
    """
    d = tmp_path / "source=medsl/dataset=precinct_by_state/vintage=2022"
    d.mkdir(parents=True)
    data = [
        "2022-id-local-precinct-general.csv",
        "ak22_cleaned.csv",
        "AR_final.csv",
        "AZ-cleaned.csv",
        "CA_2022_final.csv",
        "colorado_cleaned.csv",
        "louisiana_20240306.csv",
        "2020_in_precinct_general.csv",
    ]
    for n in data + ["codebook.md", "README.md", "notes.txt"]:
        (d / n).write_text("x")

    found = {p.name for p in gov.find_precinct_files(tmp_path, 2022)}
    assert found == set(data), "every data file must be picked up, whatever it is called"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("2020-nc-precinct-general.csv", "NC"),
        ("2020_in_precinct_general.csv", "IN"),
        ("ak22_cleaned.csv", "AK"),
        ("AR_final.csv", "AR"),
        ("AZ-cleaned.csv", "AZ"),
        ("CA_2022_final.csv", "CA"),
        ("colorado_cleaned.csv", None),
    ],
)
def test_state_from_filename_is_best_effort_only(filename, expected):
    """Full-state names like colorado_cleaned.csv are unparseable — hence state_of()."""
    assert gov.state_from_filename(pathlib.Path(filename)) == expected


def test_state_is_read_from_file_contents_not_its_name():
    """`colorado_cleaned.csv` has no parseable code; the data itself knows the state."""
    df = pd.DataFrame([{"state_po": "CO", "office": "GOVERNOR"}] * 3)
    assert gov.state_of(df, pathlib.Path("colorado_cleaned.csv")) == "CO"
    only_name = pd.DataFrame({"office": ["GOVERNOR"]})
    assert gov.state_of(only_name, pathlib.Path("ak22_cleaned.csv")) == "AK"


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


def test_state_cycle_with_an_unrecognised_major_party_is_flagged():
    """Minnesota's DFL and New Mexico 2022 read as OTHER; two-party share is meaningless."""
    from election_prediction.build_governor import _state_level

    county = pd.DataFrame(
        [
            # MN 2022: Walz's DFL line is not recognised as DEMOCRAT.
            {
                "cycle": 2022,
                "state_po": "MN",
                "state_fips": "27",
                "office": "governor",
                "candidate": "WALZ",
                "party_simplified": "OTHER",
                "votes": 1_312_349,
                "county_fips": "27001",
                "county_name": "A",
            },
            {
                "cycle": 2022,
                "state_po": "MN",
                "state_fips": "27",
                "office": "governor",
                "candidate": "JENSEN",
                "party_simplified": "REPUBLICAN",
                "votes": 1_119_941,
                "county_fips": "27001",
                "county_name": "A",
            },
            # A clean state-cycle for contrast.
            {
                "cycle": 2022,
                "state_po": "CO",
                "state_fips": "08",
                "office": "governor",
                "candidate": "POLIS",
                "party_simplified": "DEMOCRAT",
                "votes": 1_468_481,
                "county_fips": "08001",
                "county_name": "B",
            },
            {
                "cycle": 2022,
                "state_po": "CO",
                "state_fips": "08",
                "office": "governor",
                "candidate": "GANAHL",
                "party_simplified": "REPUBLICAN",
                "votes": 1_000_000,
                "county_fips": "08001",
                "county_name": "B",
            },
        ]
    )
    out = _state_level(county)
    flagged = out.set_index(["cycle", "state_po"])["two_party_suspect"]
    assert flagged.loc[(2022, "MN")].all(), "a zero major party must be flagged"
    assert not flagged.loc[(2022, "CO")].any()
