"""Presidential baseline by congressional district, derived from precinct files."""

from __future__ import annotations

import pandas as pd
import pytest

from election_prediction.features import cd_baseline as cb


def _precinct_rows(rows: list[dict]) -> pd.DataFrame:
    base = {
        "year": "2024",
        "state_po": "VA",
        "state_fips": "51",
        "county_fips": "51001",
        "county_name": "A",
        "jurisdiction_fips": "51001",
        "precinct": "P1",
        "stage": "gen",
        "special": "FALSE",
        "writein": "FALSE",
        "mode": "TOTAL",
        "party_detailed": "DEMOCRAT",
        "party_simplified": "DEMOCRAT",
        "district": "",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_precinct_is_assigned_to_the_district_its_house_rows_name(tmp_path):
    df = _precinct_rows(
        [
            {"office": "US HOUSE", "candidate": "H1", "votes": 10, "district": "11"},
            {
                "office": "US PRESIDENT",
                "candidate": "D",
                "votes": 60,
                "party_detailed": "DEMOCRAT",
                "party_simplified": "DEMOCRAT",
            },
            {
                "office": "US PRESIDENT",
                "candidate": "R",
                "votes": 40,
                "party_detailed": "REPUBLICAN",
                "party_simplified": "REPUBLICAN",
            },
        ]
    )
    f = tmp_path / "2024-va-precinct-general.csv"
    df.to_csv(f, index=False)
    out, stats = cb.presidential_by_cd(f)

    assert stats["status"] == "ok"
    assert len(out) == 1
    assert int(out.iloc[0]["district_num"]) == 11
    assert out.iloc[0]["baseline_dem_share"] == pytest.approx(0.60)


def test_precincts_spanning_two_districts_are_excluded_not_allocated(tmp_path):
    """Splitting a precinct's vote would need a crosswalk this project does not have."""
    rows = [
        # P1 is clean, in CD 11.
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "11", "precinct": "P1"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 60, "precinct": "P1"},
        # P2 straddles CD 11 and CD 8 -> ambiguous.
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "11", "precinct": "P2"},
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "8", "precinct": "P2"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 999, "precinct": "P2"},
    ]
    f = tmp_path / "2024-va-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, stats = cb.presidential_by_cd(f)

    assert stats["precincts_ambiguous_excluded"] == 1
    assert stats["precincts_used"] == 1
    assert int(out["dem_votes"].sum()) == 60, "the straddling precinct's 999 votes must not be counted"


def test_under_covered_districts_are_flagged_against_the_state_median(tmp_path):
    """Districts are equal in population, so a district far below median is suspect."""
    rows = []
    for cd, votes in ((1, 400_000), (2, 400_000), (3, 40_000)):
        rows += [
            {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": str(cd), "precinct": f"P{cd}"},
            {
                "office": "US PRESIDENT",
                "candidate": "D",
                "votes": votes // 2,
                "precinct": f"P{cd}",
                "party_simplified": "DEMOCRAT",
            },
            {
                "office": "US PRESIDENT",
                "candidate": "R",
                "votes": votes // 2,
                "precinct": f"P{cd}",
                "party_detailed": "REPUBLICAN",
                "party_simplified": "REPUBLICAN",
            },
        ]
    f = tmp_path / "2024-az-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, stats = cb.presidential_by_cd(f)

    q = out.set_index("district_num")["baseline_quality"]
    assert q.loc[1] == "ok" and q.loc[2] == "ok"
    assert q.loc[3] == "under_covered"
    assert stats["districts_under_covered"] == 1
