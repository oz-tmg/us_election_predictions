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


def test_precincts_spanning_two_districts_are_allocated_within_their_county(tmp_path):
    """Excluding them discarded 29.7% of Virginia's 2020 vote, and not neutrally.

    P2 is a county-aggregate block. Its 300 votes go to CD 11 and CD 8 in proportion to
    the presidential turnout the county's resolvable precincts recorded in each: 600 and
    200, so 3:1.
    """
    rows = [
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "11", "precinct": "P1"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 600, "precinct": "P1"},
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "8", "precinct": "P3"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 200, "precinct": "P3"},
        # P2 is the county's absentee block and straddles both districts.
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "11", "precinct": "P2"},
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "8", "precinct": "P2"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 300, "precinct": "P2"},
    ]
    f = tmp_path / "2024-va-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, stats = cb.presidential_by_cd(f)

    assert stats["precincts_ambiguous"] == 1
    assert stats["votes_unallocatable"] == 0
    assert int(out["dem_votes"].sum()) == 1100, "no vote may be lost"
    by_cd = out.set_index("district_num")["dem_votes"]
    assert by_cd[11] == pytest.approx(600 + 225)
    assert by_cd[8] == pytest.approx(200 + 75)


def test_allocation_preserves_each_party_separately(tmp_path):
    """Weighting by turnout, not by party share, is what keeps absentee's own lean."""
    rows = [
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "1", "precinct": "P1"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 50, "precinct": "P1"},
        {
            "office": "US PRESIDENT",
            "candidate": "R",
            "votes": 50,
            "precinct": "P1",
            "party_detailed": "REPUBLICAN",
            "party_simplified": "REPUBLICAN",
        },
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "2", "precinct": "P3"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 50, "precinct": "P3"},
        {
            "office": "US PRESIDENT",
            "candidate": "R",
            "votes": 50,
            "precinct": "P3",
            "party_detailed": "REPUBLICAN",
            "party_simplified": "REPUBLICAN",
        },
        # An absentee block that is 90% Democratic splits 50/50 by turnout, but stays 90%
        # Democratic in both halves -- it is not re-shaped to the election-day 50/50.
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "1", "precinct": "AB"},
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "2", "precinct": "AB"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 180, "precinct": "AB"},
        {
            "office": "US PRESIDENT",
            "candidate": "R",
            "votes": 20,
            "precinct": "AB",
            "party_detailed": "REPUBLICAN",
            "party_simplified": "REPUBLICAN",
        },
    ]
    f = tmp_path / "2024-va-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, _ = cb.presidential_by_cd(f)
    assert out["baseline_dem_share"].tolist() == pytest.approx([(50 + 90) / 200] * 2)
    assert out["allocated_share"].tolist() == pytest.approx([0.5, 0.5])


def test_a_zero_vote_district_row_does_not_make_a_precinct_ambiguous(tmp_path):
    """Alabama lists every district touching a county on every precinct row, at zero."""
    rows = [
        {"office": "US HOUSE", "candidate": "H", "votes": 1200, "district": "7", "precinct": "P1"},
        {"office": "US HOUSE", "candidate": "H2", "votes": 0, "district": "6", "precinct": "P1"},
        {"office": "US HOUSE", "candidate": "H3", "votes": 0, "district": "2", "precinct": "P1"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 900, "precinct": "P1"},
    ]
    f = tmp_path / "2020-al-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, stats = cb.presidential_by_cd(f)
    assert stats["precincts_ambiguous"] == 0
    assert out["district_num"].tolist() == [7]
    assert int(out["dem_votes"].iloc[0]) == 900


def test_a_county_with_no_precinct_level_vote_falls_back_to_its_house_vote(tmp_path):
    """King County, WA reported 2020 countywide only -- 1.21m votes with no finer grain."""
    rows = [
        # Only a countywide row exists, and it names four districts with real House votes.
        {"office": "US HOUSE", "candidate": "A", "votes": 300, "district": "7", "precinct": "COUNTYWIDE"},
        {"office": "US HOUSE", "candidate": "B", "votes": 100, "district": "9", "precinct": "COUNTYWIDE"},
        {"office": "US PRESIDENT", "candidate": "D", "votes": 800, "precinct": "COUNTYWIDE"},
    ]
    f = tmp_path / "2020-wa-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, stats = cb.presidential_by_cd(f)

    assert stats["votes_unallocatable"] == 0
    assert stats["votes_allocated_on_house_weights"] == pytest.approx(800)
    assert out.set_index("district_num")["dem_votes"].to_dict() == pytest.approx({7: 600.0, 9: 200.0})


def test_a_county_with_no_weight_at_all_is_reported_not_spread_over_the_state(tmp_path):
    """Unallocatable must be a number someone can see, not a quiet omission."""
    rows = [
        {
            "office": "US HOUSE",
            "candidate": "H",
            "votes": 10,
            "district": "1",
            "precinct": "P1",
            "county_fips": "51001",
            "county_name": "A",
        },
        {
            "office": "US PRESIDENT",
            "candidate": "D",
            "votes": 100,
            "precinct": "P1",
            "county_fips": "51001",
            "county_name": "A",
        },
        # County B has presidential vote and no House rows anywhere in it.
        {
            "office": "US PRESIDENT",
            "candidate": "D",
            "votes": 70,
            "precinct": "P9",
            "county_fips": "51003",
            "county_name": "B",
        },
    ]
    f = tmp_path / "2024-va-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, stats = cb.presidential_by_cd(f)
    assert stats["votes_unallocatable"] == pytest.approx(70)
    assert int(out["dem_votes"].sum()) == 100


def test_the_state_median_ratio_is_reported_but_no_longer_decides_quality(tmp_path):
    """It produced four false positives in 2020 and missed two real holes.

    AZ-07, CA-21, TX-29 and TX-33 all sat below 0.6 of their state median and all recover
    99-102% of their own certified House vote: majority-Hispanic seats with large
    non-citizen populations cast fewer ballots, and nothing was missing. Meanwhile NY-07
    (0.838 of its certified House vote) and NJ-04 (0.663) passed the median test. The column
    stays because it is cheap and informative; the flag moved to a measurement against
    certified House returns in ``build_cd_baselines.flag_under_covered``.
    """
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
    out, _ = cb.presidential_by_cd(f)

    ratios = out.set_index("district_num")["vote_share_of_state_median"]
    assert ratios.loc[3] < cb.MIN_VOTE_SHARE_OF_STATE_MEDIAN
    assert set(out["baseline_quality"]) == {cb.QUALITY_OK}, (
        "a low median ratio must not condemn a district on its own"
    )


def test_a_candidates_fusion_lines_are_counted_as_that_candidates_votes(tmp_path):
    """New York 2020: Biden carried 386,627 on WORKING FAMILIES, Trump 296,360 on CONSERVATIVE.

    Classifying by party label alone made both third-party, which put New York's recovered
    two-party vote at 92.2% of certified. The *share* moved only +0.0046 — the two fusion
    blocks were of similar size — which is why the vote-total check is the one that caught
    it, and why this module has both.
    """
    rows = [
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "1"},
        {
            "office": "US PRESIDENT",
            "candidate": "JOSEPH R BIDEN",
            "votes": 800,
            "party_detailed": "DEMOCRAT",
            "party_simplified": "DEMOCRAT",
        },
        {
            "office": "US PRESIDENT",
            "candidate": "JOSEPH R BIDEN",
            "votes": 100,
            "party_detailed": "WORKING FAMILIES",
            "party_simplified": "OTHER",
        },
        {
            "office": "US PRESIDENT",
            "candidate": "DONALD J TRUMP",
            "votes": 500,
            "party_detailed": "REPUBLICAN",
            "party_simplified": "REPUBLICAN",
        },
        {
            "office": "US PRESIDENT",
            "candidate": "DONALD J TRUMP",
            "votes": 100,
            "party_detailed": "CONSERVATIVE",
            "party_simplified": "OTHER",
        },
        # A genuine third party stays third party.
        {
            "office": "US PRESIDENT",
            "candidate": "JO JORGENSEN",
            "votes": 50,
            "party_detailed": "LIBERTARIAN",
            "party_simplified": "LIBERTARIAN",
        },
    ]
    f = tmp_path / "2020-ny-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, _ = cb.presidential_by_cd(f)

    assert int(out["dem_votes"].iloc[0]) == 900
    assert int(out["rep_votes"].iloc[0]) == 600
    assert int(out["two_party_votes"].iloc[0]) == 1500, "the Libertarian must stay out"
    assert out["baseline_dem_share"].iloc[0] == pytest.approx(0.6)


def test_fusion_resolution_never_merges_two_different_candidates(tmp_path):
    """Propagating by party instead of by candidate would pool distinct people."""
    rows = [
        {"office": "US HOUSE", "candidate": "H", "votes": 10, "district": "1"},
        {
            "office": "US PRESIDENT",
            "candidate": "A",
            "votes": 100,
            "party_detailed": "DEMOCRAT",
            "party_simplified": "DEMOCRAT",
        },
        {
            "office": "US PRESIDENT",
            "candidate": "B",
            "votes": 70,
            "party_detailed": "GREEN",
            "party_simplified": "OTHER",
        },
    ]
    f = tmp_path / "2020-ny-precinct-general.csv"
    _precinct_rows(rows).to_csv(f, index=False)
    out, _ = cb.presidential_by_cd(f)
    assert int(out["dem_votes"].iloc[0]) == 100
    assert int(out["two_party_votes"].iloc[0]) == 100, "B is a different candidate, not a Dem line"
